import json
import logging
from datetime import datetime, timedelta

from telebot import types

import db
from config import SESSION_TTL_SECONDS, SUPERADMIN_TELEGRAM_ID
from keyboards import admin_main_menu, jury_main_menu
from services import auth

logger = logging.getLogger(__name__)


def _user_name(user: types.User) -> str:
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return name or user.username or ""


def sync_user(user: types.User) -> None:
    auth.sync_user(user.id, user.username, _user_name(user))


def ensure_superadmin() -> None:
    auth.ensure_superadmin(SUPERADMIN_TELEGRAM_ID)


def send_admin_menu(bot, chat_id: int) -> None:
    text = "Админ-панель. Выберите раздел:"
    bot.send_message(chat_id, text, reply_markup=admin_main_menu())


def send_jury_menu(bot, chat_id: int) -> None:
    text = "Меню жюри. Выберите действие:"
    bot.send_message(chat_id, text, reply_markup=jury_main_menu())


def get_session(telegram_id: int):
    row = db.get_session(telegram_id)
    if not row:
        return None
    updated_at = row["updated_at"]
    if updated_at:
        try:
            ts = datetime.fromisoformat(updated_at)
            if datetime.utcnow() - ts > timedelta(seconds=SESSION_TTL_SECONDS):
                db.clear_session(telegram_id)
                return None
        except ValueError:
            db.clear_session(telegram_id)
            return None
    data = {}
    if row["data"]:
        try:
            data = json.loads(row["data"])
        except json.JSONDecodeError:
            data = {}
    return row["state"], data


def set_session(telegram_id: int, state: str, data: dict) -> None:
    db.set_session(telegram_id, state, json.dumps(data, ensure_ascii=False))


def clear_session(telegram_id: int) -> None:
    db.clear_session(telegram_id)
