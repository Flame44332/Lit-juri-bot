from typing import Tuple

import db


class VotingError(Exception):
    pass


def get_active_class_id() -> str | None:
    value = db.get_setting("active_class_id")
    return value if value else None


def set_active_class_id(class_id: str | None) -> None:
    db.set_setting("active_class_id", class_id or "")


def open_class(class_id: str) -> None:
    active = get_active_class_id()
    if active and active != class_id:
        raise VotingError(f"Уже открыто голосование для {active}")
    db.set_class_state(class_id, is_open=1, is_finished=0)
    set_active_class_id(class_id)


def close_class(class_id: str) -> None:
    db.set_class_state(class_id, is_open=0, is_finished=1)
    active = get_active_class_id()
    if active == class_id:
        set_active_class_id(None)


def get_class_progress(class_id: str) -> Tuple[int, int]:
    jury_ids = db.list_jury_ids()
    total = len(jury_ids)
    if total == 0:
        return 0, 0
    criteria_count = db.count_criteria()
    if criteria_count == 0:
        return 0, total
    completed = 0
    for uid in jury_ids:
        cnt = db.count_votes_for_user_class(uid, class_id)
        if cnt >= criteria_count:
            completed += 1
    return completed, total


def is_class_complete(class_id: str) -> bool:
    completed, total = get_class_progress(class_id)
    return total > 0 and completed >= total


def all_classes_complete() -> bool:
    classes = db.list_classes_ordered()
    if not classes:
        return False
    for row in classes:
        if not is_class_complete(row["class_id"]):
            return False
    return True


def user_votes_for_class(telegram_id: int, class_id: str) -> dict[int, int]:
    return db.get_votes_for_user_class(telegram_id, class_id)


def set_vote(telegram_id: int, class_id: str, criterion_id: int, score: int) -> None:
    db.upsert_vote(telegram_id, class_id, criterion_id, score)
