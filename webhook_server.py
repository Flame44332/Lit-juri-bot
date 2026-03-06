import json
import logging
import secrets
import ssl
import threading
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from telebot import types


logger = logging.getLogger(__name__)


class TelegramWebhookHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, bot=None, path: str = "/webhook", secret: str | None = None, **kwargs):
        self._bot = bot
        self._path = path
        self._secret = secret or ""
        super().__init__(*args, **kwargs)

    def _send_status(self, status: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != self._path:
            self._send_status(404)
            return
        if self._secret:
            token = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if not secrets.compare_digest(token, self._secret):
                self._send_status(403)
                return
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            self._send_status(400)
            return
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_status(400)
            return
        update = types.Update.de_json(payload)
        threading.Thread(
            target=self._bot.process_new_updates,
            args=([update],),
            daemon=True,
        ).start()
        self._send_status(200)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path != self._path:
            self._send_status(404)
            return
        self._send_status(200)

    def log_message(self, fmt: str, *args) -> None:
        logger.debug("Webhook: " + fmt, *args)


def start_webhook_server(
    bot,
    host: str,
    port: int,
    path: str,
    secret: str | None = None,
    cert_path: str | None = None,
    key_path: str | None = None,
) -> ThreadingHTTPServer | None:
    handler = partial(TelegramWebhookHandler, bot=bot, path=path, secret=secret)
    try:
        httpd = ThreadingHTTPServer((host, port), handler)
    except OSError as exc:
        logger.error("Failed to start webhook server: %s", exc)
        return None
    if cert_path:
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=cert_path, keyfile=key_path or None)
            httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
        except Exception as exc:
            logger.error("Failed to configure TLS for webhook: %s", exc)
            return None
    scheme = "https" if cert_path else "http"
    logger.info("Webhook server running on %s://%s:%s%s", scheme, host, port, path)
    return httpd
