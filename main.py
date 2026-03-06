import logging
import socket
from urllib.parse import urlparse, urlunparse

import telebot

import db
from config import (
    BOT_TOKEN,
    BOT_MODE,
    WEB_DIR,
    WEB_ENABLED,
    WEB_HOST,
    WEB_PORT,
    WEB_RESULTS_PATH,
    WEBHOOK_CERT,
    WEBHOOK_KEY,
    WEBHOOK_LISTEN,
    WEBHOOK_PATH,
    WEBHOOK_PORT,
    WEBHOOK_SECRET,
    WEBHOOK_URL,
)
from handlers import admin as admin_handlers
from handlers import common as common_handlers
from handlers import jury as jury_handlers
from services import auth, audit
from services import results
from webserver import start_web_server
from webhook_server import start_webhook_server


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


def main() -> None:
    db.init_db()
    common_handlers.ensure_superadmin()

    bot = telebot.TeleBot(BOT_TOKEN)

    register_common(bot)
    admin_handlers.register(bot)
    jury_handlers.register(bot)

    if WEB_ENABLED:
        results.export_results_json(WEB_RESULTS_PATH)
        start_web_server(WEB_HOST, WEB_PORT, WEB_DIR)

    logger.info("Bot started. mode=%s", BOT_MODE)
    if BOT_MODE == "webhook":
        start_webhook(bot)
    else:
        start_polling(bot)


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return True
        return False


def _find_free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _with_port(url: str, port: int) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    netloc = f"{host}:{port}"
    return urlunparse((parsed.scheme, netloc, parsed.path or "/", parsed.params, parsed.query, parsed.fragment))


def start_polling(bot: telebot.TeleBot) -> None:
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)


def start_webhook(bot: telebot.TeleBot) -> None:
    if not WEBHOOK_URL:
        raise RuntimeError("WEBHOOK_URL is required in webhook mode")

    listen_port = WEBHOOK_PORT
    parsed_url = urlparse(WEBHOOK_URL)
    if parsed_url.port is None and listen_port != 443:
        raise RuntimeError("WEBHOOK_URL must include port because WEBHOOK_PORT is not 443")
    if _port_in_use(WEBHOOK_LISTEN, listen_port):
        free_port = _find_free_port(WEBHOOK_LISTEN)
        if parsed_url.port is None and parsed_url.scheme == "https":
            raise RuntimeError(
                f"WEBHOOK_PORT {listen_port} is busy. Set WEBHOOK_PORT and WEBHOOK_URL with explicit port (suggested {free_port})."
            )
        logger.warning("WEBHOOK_PORT %s is busy, switching to %s", listen_port, free_port)
        listen_port = free_port
    webhook_url = WEBHOOK_URL
    parsed = urlparse(webhook_url)
    if parsed.port is not None and parsed.port != listen_port:
        webhook_url = _with_port(webhook_url, listen_port)
        logger.warning("WEBHOOK_URL port adjusted to %s", listen_port)

    cert_file = None
    try:
        if WEBHOOK_CERT:
            cert_file = open(WEBHOOK_CERT, "rb")
        bot.remove_webhook()
        ok = bot.set_webhook(
            url=webhook_url,
            certificate=cert_file,
            drop_pending_updates=True,
            secret_token=WEBHOOK_SECRET or None,
        )
        if not ok:
            raise RuntimeError("Failed to set webhook")
    finally:
        if cert_file:
            cert_file.close()

    server = start_webhook_server(
        bot,
        WEBHOOK_LISTEN,
        listen_port,
        WEBHOOK_PATH,
        secret=WEBHOOK_SECRET or None,
        cert_path=WEBHOOK_CERT or None,
        key_path=WEBHOOK_KEY or None,
    )
    if not server:
        raise RuntimeError("Webhook server failed to start")
    server.serve_forever()


def register_common(bot: telebot.TeleBot) -> None:
    @bot.message_handler(commands=["start"])
    def start_handler(message: telebot.types.Message):
        common_handlers.sync_user(message.from_user)
        role = auth.get_role(message.from_user.id)
        if auth.is_admin(role):
            common_handlers.send_admin_menu(bot, message.chat.id)
            return
        if auth.is_jury(role):
            common_handlers.send_jury_menu(bot, message.chat.id)
            return
        text = "Доступ ограничен. Если вы жюри — введите команду /join"
        bot.send_message(message.chat.id, text)

    @bot.message_handler(commands=["join"])
    def join_handler(message: telebot.types.Message):
        common_handlers.sync_user(message.from_user)
        role = auth.get_role(message.from_user.id)
        if auth.is_jury(role):
            bot.send_message(message.chat.id, "Вы уже в роли жюри.")
            audit.log_action(
                bot,
                message.from_user.id,
                "join_failed",
                {"reason": "already_jury"},
            )
            return
        if auth.is_admin(role):
            bot.send_message(message.chat.id, "Вы уже админ. Код жюри неприменим.")
            audit.log_action(
                bot,
                message.from_user.id,
                "join_failed",
                {"reason": "already_admin"},
            )
            return
        common_handlers.set_session(message.from_user.id, "join_wait_code", {})
        bot.send_message(message.chat.id, "Введите код приглашения следующим сообщением.")
        audit.log_action(
            bot,
            message.from_user.id,
            "join_requested",
        )

    @bot.message_handler(content_types=["text"])
    def join_code_handler(message: telebot.types.Message):
        if message.text and message.text.startswith("/"):
            return telebot.ContinueHandling()
        sess = common_handlers.get_session(message.from_user.id)
        if not sess:
            return telebot.ContinueHandling()
        state, data = sess
        if state == "join_wait_code":
            common_handlers.sync_user(message.from_user)
            code = (message.text or "").strip().upper()
            if not code:
                bot.send_message(message.chat.id, "Введите код приглашения.")
                audit.log_action(
                    bot,
                    message.from_user.id,
                    "join_failed",
                    {"reason": "empty_code"},
                )
                return
            role = auth.get_role(message.from_user.id)
            if auth.is_jury(role):
                bot.send_message(message.chat.id, "Вы уже в роли жюри.")
                common_handlers.clear_session(message.from_user.id)
                audit.log_action(
                    bot,
                    message.from_user.id,
                    "join_failed",
                    {"reason": "already_jury"},
                )
                return
            if auth.is_admin(role):
                bot.send_message(message.chat.id, "Вы уже админ. Код жюри неприменим.")
                common_handlers.clear_session(message.from_user.id)
                audit.log_action(
                    bot,
                    message.from_user.id,
                    "join_failed",
                    {"reason": "already_admin"},
                )
                return
            ok = auth.join_with_code(
                message.from_user.id,
                message.from_user.username,
                f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip(),
                code,
            )
            if ok:
                common_handlers.clear_session(message.from_user.id)
                bot.send_message(message.chat.id, "Добро пожаловать, жюри!")
                common_handlers.send_jury_menu(bot, message.chat.id)
                audit.log_action(
                    bot,
                    message.from_user.id,
                    "join_success",
                    {"code": code},
                )
            else:
                bot.send_message(message.chat.id, "Код недействителен или отключен. Попробуйте ещё раз.")
                audit.log_action(
                    bot,
                    message.from_user.id,
                    "join_failed",
                    {"reason": "invalid_code", "code": code},
                )
            return

        return telebot.ContinueHandling()

    @bot.message_handler(commands=["link"])
    def link_handler(message: telebot.types.Message):
        common_handlers.sync_user(message.from_user)
        parts = (message.text or "").split()
        if len(parts) < 3:
            bot.send_message(message.chat.id, "Использование: /link login password")
            audit.log_action(
                bot,
                message.from_user.id,
                "link_failed",
                {"reason": "missing_credentials"},
            )
            return
        login = parts[1].strip()
        password = parts[2].strip()
        ok = auth.link_admin(
            message.from_user.id,
            message.from_user.username,
            f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip(),
            login,
            password,
        )
        if ok:
            bot.send_message(message.chat.id, "Админ-аккаунт привязан.")
            common_handlers.send_admin_menu(bot, message.chat.id)
            audit.log_action(
                bot,
                message.from_user.id,
                "link_success",
                {"login": login},
            )
        else:
            bot.send_message(message.chat.id, "Не удалось привязать аккаунт.")
            audit.log_action(
                bot,
                message.from_user.id,
                "link_failed",
                {"reason": "invalid_credentials", "login": login},
            )


if __name__ == "__main__":
    main()
