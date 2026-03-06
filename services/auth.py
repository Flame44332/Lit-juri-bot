from dataclasses import dataclass

import db


@dataclass
class UserRole:
    role: str | None


def ensure_superadmin(superadmin_id: int) -> None:
    user = db.get_user(superadmin_id)
    if not user:
        db.upsert_user(superadmin_id, "superadmin", None, None)
    elif user["role"] != "superadmin":
        db.set_user_role(superadmin_id, "superadmin")


def get_role(telegram_id: int) -> str | None:
    user = db.get_user(telegram_id)
    return user["role"] if user else None


def is_admin(role: str | None) -> bool:
    return role in ("admin", "superadmin")


def is_jury(role: str | None) -> bool:
    return role == "jury"


def join_with_code(telegram_id: int, username: str | None, name: str | None, code: str) -> bool:
    existing = db.get_user(telegram_id)
    if existing and existing["role"] in ("admin", "superadmin", "jury"):
        return False
    code = db.normalize_code(code)
    invite = db.get_invite(code)
    if not invite or invite["is_active"] != 1:
        return False
    linked = db.find_user_by_jury_code(code)
    if linked and int(linked["telegram_id"]) != telegram_id:
        if int(linked["telegram_id"]) > 0:
            return False
    db.upsert_user(telegram_id, "jury", username, name)
    db.set_user_jury_code(telegram_id, code)
    db.touch_invite(code)
    return True


def link_admin(telegram_id: int, username: str | None, name: str | None, login: str, password: str) -> bool:
    ok = db.link_admin_account(login, password, telegram_id)
    if not ok:
        return False
    db.upsert_user(telegram_id, "admin", username, name)
    return True


def sync_user(telegram_id: int, username: str | None, name: str | None) -> None:
    db.upsert_user(telegram_id, None, username, name)


def resolve_jury_id(telegram_id: int) -> int:
    code = db.get_user_jury_code(telegram_id)
    if code:
        return db.jury_id_from_code(code)
    return telegram_id
