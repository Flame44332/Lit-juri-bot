import os
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv(path: str) -> None:
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"").strip("'")
            os.environ.setdefault(key, value)


_load_dotenv(os.path.join(BASE_DIR, ".env"))


def _get_env(name: str, required: bool = True, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if required and (value is None or value == ""):
        raise RuntimeError(f"ENV {name} is required")
    return value


def _parse_parallel_range(raw: str) -> tuple[int, int]:
    value = (raw or "").strip()
    parts = value.split("-", 1)
    if len(parts) != 2:
        raise RuntimeError("CLASS_PARALLELS must be in format '<start>-<end>', for example '9-11' or '5-8'")
    try:
        start = int(parts[0].strip())
        end = int(parts[1].strip())
    except ValueError as exc:
        raise RuntimeError("CLASS_PARALLELS must contain integers, for example '9-11'") from exc
    if start > end:
        raise RuntimeError("CLASS_PARALLELS start must be <= end")
    if start < 1 or end > 11:
        raise RuntimeError("CLASS_PARALLELS must be within school range 1-11")
    return start, end


BOT_DISABLED = os.getenv("BOT_DISABLED", "0").lower() in ("1", "true", "yes")
BOT_TOKEN = _get_env("BOT_TOKEN", required=not BOT_DISABLED)
SUPERADMIN_TELEGRAM_ID = int(_get_env("SUPERADMIN_TELEGRAM_ID", required=not BOT_DISABLED, default="0") or 0)

DB_PATH = os.getenv("DB_PATH", "juri_bot.sqlite3")
CLASS_PARALLELS = os.getenv("CLASS_PARALLELS", "9-11").strip()
CLASS_PARALLEL_START, CLASS_PARALLEL_END = _parse_parallel_range(CLASS_PARALLELS)

SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "1800"))

WEB_ENABLED = os.getenv("WEB_ENABLED", "0").lower() not in ("0", "false", "no")
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "8080"))
WEB_DIR = os.getenv("WEB_DIR", os.path.join(BASE_DIR, "web"))
WEB_RESULTS_PATH = os.getenv("WEB_RESULTS_PATH", os.path.join(WEB_DIR, "results.json"))
WEB_JURY_CODES = [c.strip().upper() for c in os.getenv("WEB_JURY_CODES", "").split(",") if c.strip()]

LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID", "").strip() or None

BOT_MODE = os.getenv("BOT_MODE", "polling").strip().lower()
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "").strip()
WEBHOOK_LISTEN = os.getenv("WEBHOOK_LISTEN", "0.0.0.0").strip()
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8443"))
WEBHOOK_CERT = os.getenv("WEBHOOK_CERT", "").strip()
WEBHOOK_KEY = os.getenv("WEBHOOK_KEY", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

if not BOT_DISABLED:
    if BOT_MODE not in ("polling", "webhook"):
        raise RuntimeError("BOT_MODE must be 'polling' or 'webhook'")
    if WEBHOOK_KEY and not WEBHOOK_CERT:
        raise RuntimeError("WEBHOOK_KEY requires WEBHOOK_CERT")
    if WEBHOOK_URL:
        parsed_url = urlparse(WEBHOOK_URL)
        if parsed_url.scheme != "https":
            raise RuntimeError("WEBHOOK_URL must start with https://")
        url_path = parsed_url.path or "/"
        if not WEBHOOK_PATH:
            WEBHOOK_PATH = url_path
        elif not WEBHOOK_PATH.startswith("/"):
            WEBHOOK_PATH = f"/{WEBHOOK_PATH}"
        if WEBHOOK_PATH != url_path:
            raise RuntimeError("WEBHOOK_PATH must match WEBHOOK_URL path")
    elif BOT_MODE == "webhook":
        raise RuntimeError("WEBHOOK_URL is required in webhook mode")
    if not WEBHOOK_PATH:
        WEBHOOK_PATH = "/webhook"
