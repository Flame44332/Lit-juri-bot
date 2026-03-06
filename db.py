import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterable

from config import DB_PATH


DEFAULT_CRITERIA = [
    {
        "name": "Вокал: Живое исполнение (или записана своя фонограмма)",
        "min_score": 0,
        "max_score": 2,
        "group_key": "vocal",
    },
    {
        "name": "Вокал: Техника",
        "min_score": 0,
        "max_score": 2,
        "group_key": "vocal",
    },
    {
        "name": "Вокал: Артистизм",
        "min_score": 1,
        "max_score": 3,
        "group_key": "vocal",
    },
    {
        "name": "Видео-визитка: Наличие видео-визитки",
        "min_score": 0,
        "max_score": 1,
        "group_key": "video",
    },
    {
        "name": "Видео-визитка: Сюжет",
        "min_score": 0,
        "max_score": 2,
        "group_key": "video",
    },
    {
        "name": "Видео-визитка: Качество",
        "min_score": 1,
        "max_score": 3,
        "group_key": "video",
    },
    {
        "name": "Яркость: Сюжет (соответствует тематике)",
        "min_score": 1,
        "max_score": 3,
        "group_key": "performance",
    },
    {
        "name": "Яркость: Танец",
        "min_score": 1,
        "max_score": 3,
        "group_key": "performance",
    },
    {
        "name": "Яркость: Декорации и/или костюмы",
        "min_score": 1,
        "max_score": 3,
        "group_key": "performance",
    },
    {
        "name": "Яркость: Артистизм",
        "min_score": 1,
        "max_score": 3,
        "group_key": "performance",
    },
    {
        "name": "Бонусный балл (по желанию)",
        "min_score": 0,
        "max_score": 1,
        "group_key": "performance",
    },
]

OLD_DEFAULT_CRITERIA = ["Вокал", "Сценический образ", "Произношение"]


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def now_ts() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def normalize_code(code: str) -> str:
    return (code or "").strip().upper()


def jury_id_from_code(code: str) -> int:
    normalized = normalize_code(code)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    num = int(digest[:12], 16)
    return -(10_000_000_000 + num)


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS classes(
                class_id TEXT PRIMARY KEY,
                parallel INT,
                number INT,
                song_title TEXT,
                performance_order INT,
                is_open INT DEFAULT 0,
                is_finished INT DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS criteria(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                min_score INT DEFAULT 1,
                max_score INT DEFAULT 10,
                group_key TEXT
            );
            CREATE TABLE IF NOT EXISTS users(
                telegram_id INTEGER PRIMARY KEY,
                role TEXT,
                tg_username TEXT,
                tg_name TEXT,
                created_at TEXT,
                jury_code TEXT
            );
            CREATE TABLE IF NOT EXISTS admin_accounts(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                telegram_id INTEGER NULL
            );
            CREATE TABLE IF NOT EXISTS jury_invites(
                code TEXT PRIMARY KEY,
                is_active INT,
                created_at TEXT,
                expires_at TEXT NULL,
                max_uses INT NULL,
                uses INT DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS votes(
                telegram_id INTEGER,
                class_id TEXT,
                criterion_id INTEGER,
                score INT,
                updated_at TEXT,
                PRIMARY KEY(telegram_id, class_id, criterion_id)
            );
            CREATE TABLE IF NOT EXISTS audit(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                at TEXT,
                actor_telegram_id INTEGER,
                action TEXT,
                meta TEXT
            );
            CREATE TABLE IF NOT EXISTS sessions(
                telegram_id INTEGER PRIMARY KEY,
                state TEXT,
                data TEXT,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS settings(
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_votes_class ON votes(class_id);
            CREATE INDEX IF NOT EXISTS idx_votes_user ON votes(telegram_id);
            """
        )
    ensure_criteria_columns()
    ensure_user_columns()
    ensure_defaults()
    migrate_votes_to_jury_code()


def ensure_criteria_columns() -> None:
    with get_conn() as conn:
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(criteria)").fetchall()]
        if "min_score" not in columns:
            conn.execute("ALTER TABLE criteria ADD COLUMN min_score INT DEFAULT 1")
        if "max_score" not in columns:
            conn.execute("ALTER TABLE criteria ADD COLUMN max_score INT DEFAULT 10")
        if "group_key" not in columns:
            conn.execute("ALTER TABLE criteria ADD COLUMN group_key TEXT")


def ensure_user_columns() -> None:
    with get_conn() as conn:
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "jury_code" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN jury_code TEXT")


def ensure_defaults() -> None:
    ensure_default_classes()
    ensure_default_criteria()
    set_setting_if_absent("active_class_id", "")
    set_setting_if_absent("final_forced", "0")
    set_setting_if_absent("final_sent", "0")


def ensure_default_classes() -> None:
    classes = []
    order = 1
    for parallel in (9, 10, 11):
        for number in range(1, 7):
            class_id = f"{parallel}.{number}"
            classes.append((class_id, parallel, number, "", order))
            order += 1

    with get_conn() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO classes(class_id, parallel, number, song_title, performance_order)
            VALUES(?, ?, ?, ?, ?)
            """,
            classes,
        )


def ensure_default_criteria() -> None:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, min_score, max_score, group_key FROM criteria ORDER BY id"
        ).fetchall()
        if not rows:
            conn.executemany(
                "INSERT INTO criteria(name, min_score, max_score, group_key) VALUES(?,?,?,?)",
                [
                    (c["name"], c["min_score"], c["max_score"], c["group_key"])
                    for c in DEFAULT_CRITERIA
                ],
            )
            return

        # Ensure min/max defaults for existing rows
        conn.execute(
            "UPDATE criteria SET min_score=COALESCE(min_score, 1), max_score=COALESCE(max_score, 10)"
        )

        existing_names = [r["name"] for r in rows]
        old_bonus = "Яркость: Бонусный балл"
        new_bonus = "Бонусный балл (по желанию)"
        if old_bonus in existing_names and new_bonus not in existing_names:
            conn.execute("UPDATE criteria SET name=? WHERE name=?", (new_bonus, old_bonus))
            rows = conn.execute(
                "SELECT id, name, min_score, max_score, group_key FROM criteria ORDER BY id"
            ).fetchall()
            existing_names = [r["name"] for r in rows]
        default_names = [c["name"] for c in DEFAULT_CRITERIA]
        if len(existing_names) == 3 and set(existing_names) == set(OLD_DEFAULT_CRITERIA):
            votes_cnt = conn.execute("SELECT COUNT(1) AS cnt FROM votes").fetchone()["cnt"]
            if votes_cnt == 0:
                conn.execute("DELETE FROM criteria")
                conn.executemany(
                    "INSERT INTO criteria(name, min_score, max_score, group_key) VALUES(?,?,?,?)",
                    [
                        (c["name"], c["min_score"], c["max_score"], c["group_key"])
                        for c in DEFAULT_CRITERIA
                    ],
                )
            return

        if set(existing_names) == set(default_names):
            by_name = {c["name"]: c for c in DEFAULT_CRITERIA}
            for row in rows:
                data = by_name.get(row["name"])
                if not data:
                    continue
                conn.execute(
                    "UPDATE criteria SET min_score=?, max_score=?, group_key=? WHERE id=?",
                    (data["min_score"], data["max_score"], data["group_key"], row["id"]),
                )


# Settings

def set_setting(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def set_setting_if_absent(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
            (key, value),
        )


def get_setting(key: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None


# Users

def upsert_user(telegram_id: int, role: str | None, tg_username: str | None, tg_name: str | None) -> None:
    created_at = now_ts()
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT role, jury_code FROM users WHERE telegram_id=?",
            (telegram_id,),
        ).fetchone()
        if existing:
            new_role = role or existing["role"]
            conn.execute(
                "UPDATE users SET role=?, tg_username=?, tg_name=? WHERE telegram_id=?",
                (new_role, tg_username, tg_name, telegram_id),
            )
        else:
            conn.execute(
                "INSERT INTO users(telegram_id, role, tg_username, tg_name, created_at, jury_code) VALUES(?,?,?,?,?,?)",
                (telegram_id, role or "guest", tg_username, tg_name, created_at, None),
            )


def get_user(telegram_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()


def set_user_role(telegram_id: int, role: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET role=? WHERE telegram_id=?", (role, telegram_id))


def set_user_jury_code(telegram_id: int, code: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET jury_code=? WHERE telegram_id=?", (normalize_code(code), telegram_id))


def get_user_jury_code(telegram_id: int) -> str | None:
    with get_conn() as conn:
        row = conn.execute("SELECT jury_code FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()
        return row["jury_code"] if row and row["jury_code"] else None


def find_user_by_jury_code(code: str):
    normalized = normalize_code(code)
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE jury_code=? ORDER BY telegram_id DESC",
            (normalized,),
        ).fetchone()


def list_jury() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE role='jury' ORDER BY created_at").fetchall()


def list_jury_profiles() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE role='jury' AND telegram_id < 0 ORDER BY created_at",
        ).fetchall()


def list_admin_users() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE role IN ('admin','superadmin') ORDER BY created_at").fetchall()


def count_jury() -> int:
    return len(set(list_jury_ids()))


def list_jury_ids() -> list[int]:
    with get_conn() as conn:
        rows = conn.execute("SELECT telegram_id, jury_code FROM users WHERE role='jury'").fetchall()
    ids: list[int] = []
    seen_codes: set[str] = set()
    for row in rows:
        code = row["jury_code"]
        if code:
            normalized = normalize_code(code)
            if normalized in seen_codes:
                continue
            seen_codes.add(normalized)
            ids.append(jury_id_from_code(normalized))
            continue
        ids.append(int(row["telegram_id"]))
    return ids


def list_jury_telegram_ids() -> list[int]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT telegram_id FROM users WHERE role='jury' AND telegram_id > 0 ORDER BY created_at"
        ).fetchall()
        return [int(r["telegram_id"]) for r in rows]


# Admin accounts

def create_admin_account(username: str, password: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO admin_accounts(username, password) VALUES(?, ?)",
            (username, password),
        )


def list_admin_accounts() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM admin_accounts ORDER BY id").fetchall()


def verify_admin_account(username: str, password: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM admin_accounts WHERE username=? AND password=?",
            (username, password),
        ).fetchone()


def link_admin_account(username: str, password: str, telegram_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM admin_accounts WHERE username=? AND password=?",
            (username, password),
        ).fetchone()
        if not row:
            return False
        if row["telegram_id"] and int(row["telegram_id"]) != telegram_id:
            return False
        conn.execute(
            "UPDATE admin_accounts SET telegram_id=? WHERE id=?",
            (telegram_id, row["id"]),
        )
        return True


# Jury invites

def create_invite(code: str, max_uses: int | None) -> None:
    code = normalize_code(code)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO jury_invites(code, is_active, created_at, max_uses) VALUES(?,1,?,?)",
            (code, now_ts(), max_uses),
        )


def list_invites() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM jury_invites ORDER BY created_at DESC").fetchall()


def get_invite(code: str):
    normalized = normalize_code(code)
    with get_conn() as conn:
        return conn.execute("SELECT * FROM jury_invites WHERE code=?", (normalized,)).fetchone()


def deactivate_invite(code: str) -> None:
    code = normalize_code(code)
    with get_conn() as conn:
        conn.execute("UPDATE jury_invites SET is_active=0 WHERE code=?", (code,))


def set_invite_active(code: str, is_active: int) -> None:
    code = normalize_code(code)
    with get_conn() as conn:
        conn.execute("UPDATE jury_invites SET is_active=? WHERE code=?", (is_active, code))


def use_invite(code: str) -> bool:
    code = normalize_code(code)
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jury_invites WHERE code=?", (code,)).fetchone()
        if not row:
            return False
        if row["is_active"] != 1:
            return False
        max_uses = row["max_uses"]
        uses = row["uses"]
        if max_uses is not None and uses >= max_uses:
            return False
        conn.execute("UPDATE jury_invites SET uses=uses+1 WHERE code=?", (code,))
        return True


def touch_invite(code: str) -> bool:
    code = normalize_code(code)
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jury_invites WHERE code=?", (code,)).fetchone()
        if not row:
            return False
        if row["is_active"] != 1:
            return False
        uses = row["uses"] or 0
        if uses == 0:
            conn.execute("UPDATE jury_invites SET uses=uses+1 WHERE code=?", (code,))
        return True


# Classes

def list_classes_by_parallel(parallel: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM classes WHERE parallel=? ORDER BY number",
            (parallel,),
        ).fetchall()


def list_classes_ordered() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM classes ORDER BY performance_order",
        ).fetchall()


def get_class(class_id: str):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM classes WHERE class_id=?", (class_id,)).fetchone()


def update_class_song(class_id: str, song_title: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE classes SET song_title=? WHERE class_id=?",
            (song_title, class_id),
        )


def update_class_order(class_id: str, order: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE classes SET performance_order=? WHERE class_id=?",
            (order, class_id),
        )


def swap_class_order(class_id_a: str, class_id_b: str) -> None:
    with get_conn() as conn:
        row_a = conn.execute("SELECT performance_order FROM classes WHERE class_id=?", (class_id_a,)).fetchone()
        row_b = conn.execute("SELECT performance_order FROM classes WHERE class_id=?", (class_id_b,)).fetchone()
        if not row_a or not row_b:
            return
        order_a = row_a["performance_order"]
        order_b = row_b["performance_order"]
        conn.execute("UPDATE classes SET performance_order=? WHERE class_id=?", (order_b, class_id_a))
        conn.execute("UPDATE classes SET performance_order=? WHERE class_id=?", (order_a, class_id_b))


def set_class_state(class_id: str, is_open: int, is_finished: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE classes SET is_open=?, is_finished=? WHERE class_id=?",
            (is_open, is_finished, class_id),
        )


def close_all_classes() -> None:
    with get_conn() as conn:
        conn.execute("UPDATE classes SET is_open=0")


def reset_classes_state() -> None:
    with get_conn() as conn:
        conn.execute("UPDATE classes SET is_open=0, is_finished=0")


# Criteria

def list_criteria() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM criteria ORDER BY id").fetchall()


def get_criterion(criterion_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM criteria WHERE id=?", (criterion_id,)).fetchone()


def add_criterion(name: str, min_score: int = 1, max_score: int = 10, group_key: str | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO criteria(name, min_score, max_score, group_key) VALUES(?,?,?,?)",
            (name, min_score, max_score, group_key),
        )


def rename_criterion(criterion_id: int, name: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE criteria SET name=? WHERE id=?", (name, criterion_id))


def delete_criterion(criterion_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM criteria WHERE id=?", (criterion_id,))


def count_votes_for_criterion(criterion_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(1) AS cnt FROM votes WHERE criterion_id=?",
            (criterion_id,),
        ).fetchone()
        return int(row["cnt"])


def migrate_votes_to_jury_code() -> None:
    with get_conn() as conn:
        users = conn.execute(
            "SELECT telegram_id, jury_code FROM users WHERE role='jury' AND jury_code IS NOT NULL"
        ).fetchall()
        for user in users:
            code = user["jury_code"]
            if not code:
                continue
            new_id = jury_id_from_code(code)
            old_id = int(user["telegram_id"])
            if new_id == old_id:
                continue
            rows = conn.execute(
                "SELECT class_id, criterion_id, score, updated_at FROM votes WHERE telegram_id=?",
                (old_id,),
            ).fetchall()
            for row in rows:
                conn.execute(
                    """
                    INSERT INTO votes(telegram_id, class_id, criterion_id, score, updated_at)
                    VALUES(?,?,?,?,?)
                    ON CONFLICT(telegram_id, class_id, criterion_id)
                    DO UPDATE SET score=excluded.score, updated_at=excluded.updated_at
                    """,
                    (new_id, row["class_id"], row["criterion_id"], row["score"], row["updated_at"]),
                )
            if rows:
                conn.execute("DELETE FROM votes WHERE telegram_id=?", (old_id,))


def count_criteria() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(1) AS cnt FROM criteria").fetchone()
        return int(row["cnt"])


# Votes

def upsert_vote(telegram_id: int, class_id: str, criterion_id: int, score: int) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO votes(telegram_id, class_id, criterion_id, score, updated_at)
            VALUES(?,?,?,?,?)
            ON CONFLICT(telegram_id, class_id, criterion_id)
            DO UPDATE SET score=excluded.score, updated_at=excluded.updated_at
            """,
            (telegram_id, class_id, criterion_id, score, now_ts()),
        )


def get_votes_for_user_class(telegram_id: int, class_id: str) -> dict[int, int]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT criterion_id, score FROM votes WHERE telegram_id=? AND class_id=?",
            (telegram_id, class_id),
        ).fetchall()
        return {int(r["criterion_id"]): int(r["score"]) for r in rows}


def count_votes_for_user_class(telegram_id: int, class_id: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(1) AS cnt FROM votes WHERE telegram_id=? AND class_id=?",
            (telegram_id, class_id),
        ).fetchone()
        return int(row["cnt"])


def total_scores_by_class() -> dict[str, int]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT class_id, SUM(score) AS total FROM votes GROUP BY class_id"
        ).fetchall()
        return {r["class_id"]: int(r["total"]) for r in rows}


def total_scores_by_class_for_criterion(criterion_id: int) -> dict[str, int]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT class_id, SUM(score) AS total FROM votes WHERE criterion_id=? GROUP BY class_id",
            (criterion_id,),
        ).fetchall()
        return {r["class_id"]: int(r["total"]) for r in rows}


def total_scores_by_class_for_criteria(criterion_ids: Iterable[int]) -> dict[str, int]:
    ids = [int(cid) for cid in criterion_ids]
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT class_id, SUM(score) AS total FROM votes WHERE criterion_id IN ({placeholders}) GROUP BY class_id",
            ids,
        ).fetchall()
        return {r["class_id"]: int(r["total"]) for r in rows}


def total_scores_by_class_and_criterion() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT v.class_id,
                   v.criterion_id,
                   c.name AS criterion_name,
                   c.group_key AS group_key,
                   SUM(v.score) AS total
            FROM votes v
            JOIN criteria c ON c.id = v.criterion_id
            GROUP BY v.class_id, v.criterion_id
            ORDER BY v.class_id, v.criterion_id
            """
        ).fetchall()


def count_votes_any() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(1) AS cnt FROM votes").fetchone()
        return int(row["cnt"])


def list_votes() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM votes ORDER BY updated_at DESC").fetchall()


def delete_votes() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM votes")


# Sessions

def get_session(telegram_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM sessions WHERE telegram_id=?",
            (telegram_id,),
        ).fetchone()


def set_session(telegram_id: int, state: str, data: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions(telegram_id, state, data, updated_at) VALUES(?,?,?,?)"
            " ON CONFLICT(telegram_id) DO UPDATE SET state=excluded.state, data=excluded.data, updated_at=excluded.updated_at",
            (telegram_id, state, data, now_ts()),
        )


def clear_session(telegram_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE telegram_id=?", (telegram_id,))


# Audit

def add_audit(actor_telegram_id: int | None, action: str, meta: str | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit(at, actor_telegram_id, action, meta) VALUES(?,?,?,?)",
            (now_ts(), actor_telegram_id, action, meta),
        )


def list_audit(limit: int = 20) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM audit ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
