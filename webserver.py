import json
import logging
import os
import secrets
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import db
from config import WEB_RESULTS_PATH
from services import audit, results, voting, utils

logger = logging.getLogger(__name__)


ADMIN_SESSION_TTL = 12 * 60 * 60
ADMIN_SESSIONS: dict[str, dict] = {}
ADMIN_SESSIONS_LOCK = threading.Lock()


def _create_admin_session(admin_row: dict) -> str:
    token = secrets.token_hex(16)
    with ADMIN_SESSIONS_LOCK:
        ADMIN_SESSIONS[token] = {
            "username": admin_row.get("username"),
            "telegram_id": admin_row.get("telegram_id"),
            "created_at": time.time(),
        }
    return token


def _get_admin_session(token: str | None) -> dict | None:
    if not token:
        return None
    now = time.time()
    with ADMIN_SESSIONS_LOCK:
        session = ADMIN_SESSIONS.get(token)
        if not session:
            return None
        if now - session.get("created_at", now) > ADMIN_SESSION_TTL:
            ADMIN_SESSIONS.pop(token, None)
            return None
        return session


def _delete_admin_session(token: str | None) -> None:
    if not token:
        return
    with ADMIN_SESSIONS_LOCK:
        ADMIN_SESSIONS.pop(token, None)


def _ensure_jury_user(code: str, name: str | None) -> tuple[int, str | None]:
    jury_id = db.jury_id_from_code(code)
    existing = db.get_user(jury_id)
    if existing:
        if name:
            db.upsert_user(jury_id, "jury", existing["tg_username"], name)
            db.set_user_jury_code(jury_id, code)
            return jury_id, name
        if existing["role"] != "jury":
            db.set_user_role(jury_id, "jury")
        if not existing["jury_code"]:
            db.set_user_jury_code(jury_id, code)
        return jury_id, existing["tg_name"]
    if not name:
        name = f"WEB {code}"
    db.upsert_user(jury_id, "jury", None, name)
    db.set_user_jury_code(jury_id, code)
    return jury_id, name


class WebAppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def _send_json(self, payload: dict, status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict | None:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return None

    def _error(self, message: str, status: int = 400) -> None:
        self._send_json({"ok": False, "error": message}, status=status)

    def _admin_token(self) -> str | None:
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth.replace("Bearer ", "", 1).strip()
        return self.headers.get("X-Admin-Token")

    def _require_admin(self) -> dict | None:
        token = self._admin_token()
        session = _get_admin_session(token)
        if not session:
            self._error("unauthorized", status=401)
            return None
        return session

    def _resolve_jury(self, code: str | None, name: str | None) -> tuple[str, str | None, int] | None:
        code = db.normalize_code(code or "")
        if not code:
            self._error("jury_code_required", status=400)
            return None
        invite = db.get_invite(code)
        if not invite or invite["is_active"] != 1:
            self._error("jury_code_invalid", status=403)
            return None
        db.touch_invite(code)
        jury_id, stored_name = _ensure_jury_user(code, name)
        return code, stored_name, jury_id

    def _handle_bootstrap(self, query: dict) -> None:
        code = (query.get("jury_code") or [""])[0]
        name = (query.get("jury_name") or [""])[0].strip() or None
        resolved = self._resolve_jury(code, name)
        if not resolved:
            return
        code, stored_name, jury_id = resolved

        classes = [
            {
                "class_id": c["class_id"],
                "parallel": int(c["parallel"]),
                "number": int(c["number"]),
                "song_title": c["song_title"] or "—",
                "performance_order": int(c["performance_order"] or 0),
                "is_open": int(c["is_open"] or 0),
                "is_finished": int(c["is_finished"] or 0),
            }
            for c in db.list_classes_ordered()
        ]
        criteria = [
            {
                "id": int(c["id"]),
                "name": c["name"],
                "min_score": int(c["min_score"] if c["min_score"] is not None else 1),
                "max_score": int(c["max_score"] if c["max_score"] is not None else 10),
            }
            for c in db.list_criteria()
        ]
        with db.get_conn() as conn:
            rows = conn.execute(
                "SELECT class_id, criterion_id, score FROM votes WHERE telegram_id=?",
                (jury_id,),
            ).fetchall()
        votes = [
            {
                "class_id": r["class_id"],
                "criterion_id": int(r["criterion_id"]),
                "score": int(r["score"]),
            }
            for r in rows
        ]
        payload = {
            "ok": True,
            "jury": {"code": code, "name": stored_name},
            "active_class_id": voting.get_active_class_id() or "",
            "classes": classes,
            "criteria": criteria,
            "votes": votes,
        }
        self._send_json(payload)

    def _handle_score(self, body: dict | None) -> None:
        if not body:
            self._error("invalid_json", status=400)
            return
        code = body.get("jury_code")
        name = (body.get("jury_name") or "").strip() or None
        resolved = self._resolve_jury(code, name)
        if not resolved:
            return
        _, stored_name, jury_id = resolved

        class_id = (body.get("class_id") or "").strip()
        if not class_id:
            self._error("class_id_required", status=400)
            return
        try:
            criterion_id = int(body.get("criterion_id"))
            score = int(body.get("score"))
        except (TypeError, ValueError):
            self._error("invalid_score", status=400)
            return

        cls = db.get_class(class_id)
        if not cls or cls["is_open"] != 1:
            self._error("voting_closed", status=409)
            return
        criterion = db.get_criterion(criterion_id)
        if not criterion:
            self._error("criterion_not_found", status=404)
            return
        min_score = criterion["min_score"] if criterion["min_score"] is not None else 1
        max_score = criterion["max_score"] if criterion["max_score"] is not None else 10
        if score < min_score or score > max_score:
            self._error("score_out_of_range", status=400)
            return

        db.upsert_vote(jury_id, class_id, criterion_id, score)
        meta = {
            "actor": {
                "name": stored_name,
                "username": None,
                "role": "jury",
            },
            "class": {
                "class_id": class_id,
                "song_title": cls["song_title"] or "—",
            },
            "criterion": {
                "id": criterion_id,
                "name": criterion["name"],
                "min_score": min_score,
                "max_score": max_score,
            },
            "score": score,
            "source": "web",
        }
        audit.log_action(None, jury_id, "vote", meta)
        results.export_results_json(WEB_RESULTS_PATH)
        self._send_json({"ok": True, "class_id": class_id, "criterion_id": criterion_id, "score": score})

    def _send_csv(self, filename: str, headers: list[str], rows: list[list]) -> None:
        data = utils.csv_bytes(headers, rows)
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_admin_login(self, body: dict | None) -> None:
        if not body:
            self._error("invalid_json", status=400)
            return
        username = (body.get("username") or "").strip()
        password = (body.get("password") or "").strip()
        if not username or not password:
            self._error("credentials_required", status=400)
            return
        admin = db.verify_admin_account(username, password)
        if not admin:
            self._error("invalid_credentials", status=403)
            return
        token = _create_admin_session(
            {"username": admin["username"], "telegram_id": admin["telegram_id"]}
        )
        self._send_json({"ok": True, "token": token, "admin": {"username": admin["username"]}})

    def _handle_admin_logout(self) -> None:
        token = self._admin_token()
        _delete_admin_session(token)
        self._send_json({"ok": True})

    def _handle_admin_bootstrap(self) -> None:
        session = self._require_admin()
        if not session:
            return
        classes = []
        for c in db.list_classes_ordered():
            voted, total = voting.get_class_progress(c["class_id"])
            classes.append(
                {
                    "class_id": c["class_id"],
                    "parallel": int(c["parallel"]),
                    "number": int(c["number"]),
                    "song_title": c["song_title"] or "",
                    "performance_order": int(c["performance_order"] or 0),
                    "is_open": int(c["is_open"] or 0),
                    "is_finished": int(c["is_finished"] or 0),
                    "progress_voted": int(voted),
                    "progress_total": int(total),
                }
            )
        criteria = [
            {
                "id": int(c["id"]),
                "name": c["name"],
                "min_score": int(c["min_score"] if c["min_score"] is not None else 1),
                "max_score": int(c["max_score"] if c["max_score"] is not None else 10),
                "group_key": c["group_key"],
            }
            for c in db.list_criteria()
        ]
        invites = [
            {
                "code": i["code"],
                "is_active": int(i["is_active"] or 0),
                "created_at": i["created_at"],
                "max_uses": i["max_uses"],
                "uses": int(i["uses"] or 0),
            }
            for i in db.list_invites()
        ]
        admins = [
            {
                "username": a["username"],
                "password": a["password"],
                "telegram_id": a["telegram_id"],
            }
            for a in db.list_admin_accounts()
        ]
        jury_profiles = [
            {
                "name": j["tg_name"] or "",
                "code": j["jury_code"] or "",
                "created_at": j["created_at"],
            }
            for j in db.list_jury_profiles()
        ]
        jury_rows = db.list_jury()
        jury = []
        seen_codes: set[str] = set()
        for j in jury_rows:
            code = j["jury_code"]
            if code:
                normalized = db.normalize_code(code)
                if normalized in seen_codes:
                    continue
                seen_codes.add(normalized)
            jury.append(
                {
                    "telegram_id": int(j["telegram_id"]),
                    "name": j["tg_name"] or "",
                    "username": j["tg_username"] or "",
                    "jury_code": j["jury_code"] or "",
                }
            )
        settings = {
            "active_class_id": voting.get_active_class_id() or "",
            "final_forced": db.get_setting("final_forced") or "0",
            "final_sent": db.get_setting("final_sent") or "0",
        }
        results_payload = results.build_results_payload(title="Итоги голосования")
        logs = [
            {
                "id": int(l["id"]),
                "at": l["at"],
                "actor_telegram_id": l["actor_telegram_id"],
                "action": l["action"],
                "meta": l["meta"] or "",
            }
            for l in db.list_audit(20)
        ]
        self._send_json(
            {
                "ok": True,
                "admin": {"username": session.get("username") or ""},
                "classes": classes,
                "criteria": criteria,
                "invites": invites,
                "admins": admins,
                "jury_profiles": jury_profiles,
                "jury": jury,
                "settings": settings,
                "results": results_payload,
                "logs": logs,
            }
        )

    def _admin_actor_meta(self, session: dict) -> dict:
        return {
            "actor": {
                "name": session.get("username"),
                "username": session.get("username"),
                "role": "admin",
            },
            "source": "web_admin",
        }

    def _handle_admin_action(self, path: str, body: dict | None) -> None:
        session = self._require_admin()
        if not session:
            return
        if not body:
            body = {}

        if path == "/api/admin/class/song":
            class_id = (body.get("class_id") or "").strip()
            song_title = (body.get("song_title") or "").strip()
            if not class_id:
                self._error("class_id_required", status=400)
                return
            db.update_class_song(class_id, song_title)
            meta = {"class": {"class_id": class_id, "song_title": song_title or "—"}}
            meta.update(self._admin_actor_meta(session))
            audit.log_action(None, session.get("telegram_id"), "edit_song", meta)
            results.export_results_json(WEB_RESULTS_PATH)
            self._send_json({"ok": True})
            return

        if path == "/api/admin/class/order":
            class_id = (body.get("class_id") or "").strip()
            if not class_id:
                self._error("class_id_required", status=400)
                return
            try:
                order = int(body.get("order"))
            except (TypeError, ValueError):
                self._error("order_required", status=400)
                return
            db.update_class_order(class_id, order)
            meta = {"class": {"class_id": class_id, "order": order}}
            meta.update(self._admin_actor_meta(session))
            audit.log_action(None, session.get("telegram_id"), "set_order", meta)
            results.export_results_json(WEB_RESULTS_PATH)
            self._send_json({"ok": True})
            return

        if path == "/api/admin/queue/swap":
            class_a = (body.get("class_id_a") or "").strip()
            class_b = (body.get("class_id_b") or "").strip()
            if not class_a or not class_b:
                self._error("class_id_required", status=400)
                return
            db.swap_class_order(class_a, class_b)
            meta = {"class_a": class_a, "class_b": class_b}
            meta.update(self._admin_actor_meta(session))
            audit.log_action(None, session.get("telegram_id"), "swap_order", meta)
            results.export_results_json(WEB_RESULTS_PATH)
            self._send_json({"ok": True})
            return

        if path == "/api/admin/criteria/add":
            name = (body.get("name") or "").strip()
            if not name:
                self._error("name_required", status=400)
                return
            min_score = int(body.get("min_score") or 1)
            max_score = int(body.get("max_score") or 10)
            group_key = (body.get("group_key") or "").strip() or None
            try:
                db.add_criterion(name, min_score=min_score, max_score=max_score, group_key=group_key)
            except Exception:
                self._error("criterion_exists", status=409)
                return
            meta = {"name": name, "min_score": min_score, "max_score": max_score, "group_key": group_key}
            meta.update(self._admin_actor_meta(session))
            audit.log_action(None, session.get("telegram_id"), "add_criterion", meta)
            results.export_results_json(WEB_RESULTS_PATH)
            self._send_json({"ok": True})
            return

        if path == "/api/admin/criteria/rename":
            try:
                criterion_id = int(body.get("id"))
            except (TypeError, ValueError):
                self._error("id_required", status=400)
                return
            name = (body.get("name") or "").strip()
            if not name:
                self._error("name_required", status=400)
                return
            db.rename_criterion(criterion_id, name)
            meta = {"id": criterion_id, "name": name}
            meta.update(self._admin_actor_meta(session))
            audit.log_action(None, session.get("telegram_id"), "rename_criterion", meta)
            results.export_results_json(WEB_RESULTS_PATH)
            self._send_json({"ok": True})
            return

        if path == "/api/admin/criteria/delete":
            try:
                criterion_id = int(body.get("id"))
            except (TypeError, ValueError):
                self._error("id_required", status=400)
                return
            if db.count_votes_for_criterion(criterion_id) > 0:
                self._error("criterion_has_votes", status=409)
                return
            db.delete_criterion(criterion_id)
            meta = {"id": criterion_id}
            meta.update(self._admin_actor_meta(session))
            audit.log_action(None, session.get("telegram_id"), "delete_criterion", meta)
            results.export_results_json(WEB_RESULTS_PATH)
            self._send_json({"ok": True})
            return

        if path == "/api/admin/admins/create":
            username = (body.get("username") or "").strip()
            if not username:
                self._error("username_required", status=400)
                return
            password = utils.generate_password(10)
            try:
                db.create_admin_account(username, password)
            except Exception:
                self._error("admin_exists", status=409)
                return
            meta = {"username": username}
            meta.update(self._admin_actor_meta(session))
            audit.log_action(None, session.get("telegram_id"), "create_admin", meta)
            self._send_json({"ok": True, "username": username, "password": password})
            return

        if path == "/api/admin/jury/create":
            name = (body.get("name") or "").strip()
            if not name:
                self._error("name_required", status=400)
                return
            code = None
            for _ in range(10):
                candidate = utils.generate_code(6)
                if db.get_invite(candidate):
                    continue
                code = candidate
                break
            if not code:
                self._error("code_generate_failed", status=500)
                return
            try:
                db.create_invite(code, max_uses=1)
                jury_id = db.jury_id_from_code(code)
                db.upsert_user(jury_id, "jury", None, name)
                db.set_user_jury_code(jury_id, code)
            except Exception:
                self._error("jury_create_failed", status=500)
                return
            meta = {"name": name, "code": code}
            meta.update(self._admin_actor_meta(session))
            audit.log_action(None, session.get("telegram_id"), "create_jury_account", meta)
            self._send_json({"ok": True, "name": name, "code": code})
            return

        if path == "/api/admin/invites/create":
            code = utils.generate_code(6)
            db.create_invite(code, max_uses=1)
            meta = {"code": code, "max_uses": 1}
            meta.update(self._admin_actor_meta(session))
            audit.log_action(None, session.get("telegram_id"), "create_invite", meta)
            self._send_json({"ok": True, "code": code})
            return

        if path == "/api/admin/invites/toggle":
            code = (body.get("code") or "").strip()
            if not code:
                self._error("code_required", status=400)
                return
            invite = db.get_invite(code)
            if not invite:
                self._error("not_found", status=404)
                return
            new_state = 0 if invite["is_active"] == 1 else 1
            db.set_invite_active(code, new_state)
            meta = {"code": code, "is_active": new_state}
            meta.update(self._admin_actor_meta(session))
            audit.log_action(None, session.get("telegram_id"), "toggle_invite", meta)
            self._send_json({"ok": True, "is_active": new_state})
            return

        if path == "/api/admin/voting/open":
            class_id = (body.get("class_id") or "").strip()
            if not class_id:
                self._error("class_id_required", status=400)
                return
            try:
                voting.open_class(class_id)
            except voting.VotingError as exc:
                self._error(str(exc), status=409)
                return
            cls = db.get_class(class_id)
            meta = {"class": {"class_id": class_id, "song_title": cls["song_title"] if cls else None}}
            meta.update(self._admin_actor_meta(session))
            audit.log_action(None, session.get("telegram_id"), "open_class", meta)
            self._send_json({"ok": True})
            return

        if path == "/api/admin/voting/close":
            class_id = (body.get("class_id") or "").strip()
            if not class_id:
                self._error("class_id_required", status=400)
                return
            voting.close_class(class_id)
            cls = db.get_class(class_id)
            meta = {"class": {"class_id": class_id, "song_title": cls["song_title"] if cls else None}}
            meta.update(self._admin_actor_meta(session))
            audit.log_action(None, session.get("telegram_id"), "close_class", meta)
            self._send_json({"ok": True})
            return

        if path == "/api/admin/voting/next":
            active = voting.get_active_class_id()
            if active:
                self._error(f"Сначала закройте {active}", status=409)
                return
            classes = [c for c in db.list_classes_ordered() if c["is_finished"] == 0]
            if not classes:
                self._error("Все классы завершены", status=409)
                return
            class_id = classes[0]["class_id"]
            try:
                voting.open_class(class_id)
            except voting.VotingError as exc:
                self._error(str(exc), status=409)
                return
            cls = db.get_class(class_id)
            meta = {"class": {"class_id": class_id, "song_title": cls["song_title"] if cls else None}}
            meta.update(self._admin_actor_meta(session))
            audit.log_action(None, session.get("telegram_id"), "open_class", meta)
            self._send_json({"ok": True, "class_id": class_id})
            return

        if path == "/api/admin/results/partial":
            payload = results.build_results_payload(title="Промежуточные итоги")
            self._send_json({"ok": True, "results": payload})
            return

        if path == "/api/admin/results/final":
            force = bool(body.get("force"))
            if voting.all_classes_complete() or db.get_setting("final_forced") == "1" or force:
                if force:
                    db.set_setting("final_forced", "1")
                db.set_setting("final_sent", "1")
                payload = results.build_results_payload(title="Финальные итоги")
                self._send_json({"ok": True, "results": payload})
                return
            self._error("final_not_ready", status=409)
            return

        if path == "/api/admin/settings/reset":
            db.delete_votes()
            db.reset_classes_state()
            db.set_setting("active_class_id", "")
            db.set_setting("final_forced", "0")
            db.set_setting("final_sent", "0")
            meta = {}
            meta.update(self._admin_actor_meta(session))
            audit.log_action(None, session.get("telegram_id"), "reset_votes", meta)
            results.export_results_json(WEB_RESULTS_PATH)
            self._send_json({"ok": True})
            return

        self._error("not_found", status=404)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/bootstrap":
            self._handle_bootstrap(parse_qs(parsed.query))
            return
        if parsed.path == "/api/admin/bootstrap":
            self._handle_admin_bootstrap()
            return
        if parsed.path == "/api/admin/export":
            session = self._require_admin()
            if not session:
                return
            query = parse_qs(parsed.query)
            export_type = (query.get("type") or [""])[0]
            if export_type == "classes":
                classes = db.list_classes_ordered()
                self._send_csv(
                    "classes.csv",
                    ["class_id", "parallel", "number", "song_title", "performance_order", "is_open", "is_finished"],
                    [
                        [
                            c["class_id"],
                            c["parallel"],
                            c["number"],
                            c["song_title"],
                            c["performance_order"],
                            c["is_open"],
                            c["is_finished"],
                        ]
                        for c in classes
                    ],
                )
                return
            if export_type == "criteria":
                criteria = db.list_criteria()
                self._send_csv(
                    "criteria.csv",
                    ["id", "name", "min_score", "max_score", "group_key"],
                    [[c["id"], c["name"], c["min_score"], c["max_score"], c["group_key"]] for c in criteria],
                )
                return
            if export_type == "votes":
                votes = db.list_votes()
                self._send_csv(
                    "votes.csv",
                    ["telegram_id", "class_id", "criterion_id", "score", "updated_at"],
                    [[v["telegram_id"], v["class_id"], v["criterion_id"], v["score"], v["updated_at"]] for v in votes],
                )
                return
            if export_type == "results":
                res = results.get_results()
                self._send_csv(
                    "results.csv",
                    ["class_id", "song_title", "total", "vocal_total", "video_total", "vocal_video_total", "performance_total"],
                    [
                        [
                            r.class_id,
                            r.song_title,
                            r.total,
                            r.vocal_total,
                            r.video_total,
                            r.vocal_video_total,
                            r.performance_total,
                        ]
                        for r in res
                    ],
                )
                return
            if export_type == "criteria_totals":
                rows = db.total_scores_by_class_and_criterion()
                self._send_csv(
                    "criteria_totals.csv",
                    ["class_id", "criterion_id", "criterion_name", "group_key", "total"],
                    [
                        [r["class_id"], r["criterion_id"], r["criterion_name"], r["group_key"], r["total"]]
                        for r in rows
                    ],
                )
                return
            self._error("unknown_export", status=400)
            return
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/score":
            payload = self._read_json()
            self._handle_score(payload)
            return
        if parsed.path == "/api/admin/login":
            payload = self._read_json()
            self._handle_admin_login(payload)
            return
        if parsed.path == "/api/admin/logout":
            self._handle_admin_logout()
            return
        if parsed.path.startswith("/api/admin/"):
            payload = self._read_json()
            self._handle_admin_action(parsed.path, payload)
            return
        self._error("not_found", status=404)
        return


def start_web_server(host: str, port: int, directory: str, enable_api: bool = True) -> ThreadingHTTPServer | None:
    if not os.path.isdir(directory):
        logger.warning("Web directory not found: %s", directory)
        return None

    handler_cls = WebAppHandler if enable_api else SimpleHTTPRequestHandler
    handler = partial(handler_cls, directory=directory)
    try:
        httpd = ThreadingHTTPServer((host, port), handler)
    except OSError as exc:
        logger.error("Failed to start web server: %s", exc)
        return None

    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    logger.info("Web server running on http://%s:%s", host, port)
    return httpd
