import logging
import time

import db
from config import WEB_DIR, WEB_ENABLED, WEB_HOST, WEB_PORT, WEB_RESULTS_PATH
from services import results
from webserver import start_web_server


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("web-only")


def main() -> None:
    db.init_db()
    if not WEB_ENABLED:
        logger.error("WEB_ENABLED=0, web server is disabled")
        return
    results.export_results_json(WEB_RESULTS_PATH)
    server = start_web_server(WEB_HOST, WEB_PORT, WEB_DIR, enable_api=True)
    if not server:
        logger.error("Web server failed to start")
        return
    logger.info("Web-only mode started")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Web-only mode stopped")


if __name__ == "__main__":
    main()
