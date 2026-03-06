import json

import db
from config import LOG_CHANNEL_ID


def _normalize_meta(meta):
    if meta is None:
        return None, None
    if isinstance(meta, dict):
        return json.dumps(meta, ensure_ascii=False), meta
    if isinstance(meta, str):
        text = meta.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                obj = json.loads(text)
                return text, obj
            except json.JSONDecodeError:
                return text, None
        return text, None
    return str(meta), None


def _resolve_actor(actor_id: int | None, meta_actor: dict | None):
    if meta_actor is None:
        meta_actor = {}
    name = meta_actor.get("name")
    username = meta_actor.get("username")
    if (not name or not username) and actor_id:
        user = db.get_user(actor_id)
        if user:
            name = name or user["tg_name"]
            username = username or user["tg_username"]
    return {
        "id": actor_id,
        "name": name,
        "username": username,
    }


def _format_message(action: str, actor_id: int | None, meta_obj: dict | None, meta_str: str | None) -> str:
    meta_obj = meta_obj or {}
    actor = _resolve_actor(actor_id, meta_obj.get("actor"))

    lines = [f"action: {action}"]
    if actor["id"] is not None:
        label = actor["name"] or "—"
        if actor["username"]:
            label = f"{label} (@{actor['username']})"
        lines.append(f"actor: {label} | id: {actor['id']}")

    cls = meta_obj.get("class")
    if isinstance(cls, dict):
        class_id = cls.get("class_id") or "—"
        song = cls.get("song_title") or "—"
        lines.append(f"class: {class_id} — {song}")

    crit = meta_obj.get("criterion")
    if isinstance(crit, dict):
        crit_id = crit.get("id")
        crit_name = crit.get("name") or "—"
        min_score = crit.get("min_score")
        max_score = crit.get("max_score")
        if min_score is not None and max_score is not None:
            lines.append(f"criterion: {crit_id} — {crit_name} ({min_score}-{max_score})")
        else:
            lines.append(f"criterion: {crit_id} — {crit_name}")

    if "score" in meta_obj:
        lines.append(f"score: {meta_obj.get('score')}")

    extra_keys = [k for k in meta_obj.keys() if k not in ("actor", "class", "criterion", "score")]
    for key in sorted(extra_keys):
        value = meta_obj.get(key)
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        lines.append(f"{key}: {value}")

    if meta_str and not meta_obj:
        lines.append(f"meta: {meta_str}")

    return "\n".join(lines)


def log_action(bot, actor_telegram_id: int | None, action: str, meta=None) -> None:
    meta_str, meta_obj = _normalize_meta(meta)
    db.add_audit(actor_telegram_id, action, meta_str)
    if not LOG_CHANNEL_ID or bot is None:
        return
    chat_id = LOG_CHANNEL_ID
    if isinstance(chat_id, str) and chat_id.lstrip("-").isdigit():
        chat_id = int(chat_id)
    text = _format_message(action, actor_telegram_id, meta_obj, meta_str)
    try:
        bot.send_message(chat_id, text)
    except Exception:
        return
