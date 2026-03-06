import csv
import io
import random
import string
from datetime import datetime


def now_local_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def generate_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


def generate_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


def format_status(is_open: int, is_finished: int) -> str:
    if is_open:
        return "ОТКРЫТО"
    if is_finished:
        return "ЗАВЕРШЕНО"
    return "ЗАКРЫТО"


def csv_bytes(headers: list[str], rows: list[list]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")
