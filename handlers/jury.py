import json
import logging

from telebot import types

import db
from keyboards import class_list_keyboard, jury_class_card_keyboard, jury_main_menu, jury_vote_menu_keyboard, score_keyboard
from services import auth, utils, voting, results, audit
from config import WEB_ENABLED, WEB_RESULTS_PATH
from handlers.common import sync_user

logger = logging.getLogger(__name__)


def _is_jury(user_id: int) -> bool:
    return auth.is_jury(auth.get_role(user_id))


def _edit_or_send(bot, call, text: str, kb=None) -> None:
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=kb)


def _class_card_text(cls, progress: tuple[int, int], criteria_count: int, votes_count: int) -> str:
    status = utils.format_status(cls["is_open"], cls["is_finished"])
    voted, total = progress
    song = cls["song_title"] or "—"
    total_criteria = max(int(criteria_count), 0)
    total_votes = min(max(int(votes_count), 0), total_criteria) if total_criteria else 0
    return (
        f"Класс {cls['class_id']}\n"
        f"Песня: {song}\n"
        f"№ в очереди: {cls['performance_order']}\n"
        f"Статус: {status}\n"
        f"Прогресс: {voted}/{total} жюри\n"
        f"Оценено: {total_votes}/{total_criteria}"
    )


def _my_votes_text(user_id: int) -> str:
    jury_id = auth.resolve_jury_id(user_id)
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT class_id, SUM(score) AS total, COUNT(1) AS cnt FROM votes WHERE telegram_id=? GROUP BY class_id",
            (jury_id,),
        ).fetchall()
    if not rows:
        return "У вас пока нет оценок."
    lines = ["Мои оценки:"]
    for r in rows:
        lines.append(f"{r['class_id']} — {r['total']} балл. ({r['cnt']} критериев)")
    return "\n".join(lines)


def _status_text() -> str:
    classes = db.list_classes_ordered()
    lines = ["Статус выступлений:"]
    for cls in classes:
        status = utils.format_status(cls["is_open"], cls["is_finished"])
        voted, total = voting.get_class_progress(cls["class_id"])
        lines.append(f"{cls['class_id']} — {status} — {voted}/{total}")
    return "\n".join(lines)


def register(bot):
    @bot.callback_query_handler(func=lambda call: call.data.startswith("jury:"))
    def jury_callbacks(call: types.CallbackQuery):
        if not _is_jury(call.from_user.id):
            bot.answer_callback_query(call.id, "Доступ только для жюри")
            return
        sync_user(call.from_user)
        data = call.data.split(":")

        if call.data == "jury:menu":
            _edit_or_send(bot, call, "Меню жюри:", jury_main_menu())
            return

        if call.data == "jury:vote":
            _edit_or_send(bot, call, "Выберите параллель:", jury_vote_menu_keyboard())
            return

        if len(data) >= 3 and data[0] == "jury" and data[1] == "par":
            parallel = int(data[2])
            classes = db.list_classes_by_parallel(parallel)
            _edit_or_send(bot, call, "Выберите класс:", class_list_keyboard(classes, "jury", "jury:vote"))
            return

        if len(data) >= 3 and data[0] == "jury" and data[1] == "class":
            class_id = data[2]
            cls = db.get_class(class_id)
            if not cls:
                bot.answer_callback_query(call.id, "Класс не найден")
                return
            criteria = db.list_criteria()
            jury_id = auth.resolve_jury_id(call.from_user.id)
            votes = voting.user_votes_for_class(jury_id, class_id)
            progress = voting.get_class_progress(class_id)
            text = _class_card_text(cls, progress, len(criteria), len(votes))
            _edit_or_send(bot, call, text, jury_class_card_keyboard(criteria, class_id, votes, cls["is_open"] == 1))
            return

        if len(data) >= 4 and data[0] == "jury" and data[1] == "criterion":
            class_id = data[2]
            criterion_id = int(data[3])
            cls = db.get_class(class_id)
            if not cls or cls["is_open"] != 1:
                bot.answer_callback_query(call.id, "Голосование закрыто")
                return
            criterion = db.get_criterion(criterion_id)
            if not criterion:
                bot.answer_callback_query(call.id, "Критерий не найден")
                return
            min_score = criterion["min_score"] if criterion["min_score"] is not None else 1
            max_score = criterion["max_score"] if criterion["max_score"] is not None else 10
            kb = score_keyboard(class_id, criterion_id, min_score, max_score)
            _edit_or_send(
                bot,
                call,
                f"Поставьте оценку ({min_score}-{max_score}) для {class_id}:",
                kb,
            )
            return

        if len(data) >= 5 and data[0] == "jury" and data[1] == "score":
            class_id = data[2]
            criterion_id = int(data[3])
            score = int(data[4])
            cls = db.get_class(class_id)
            if not cls or cls["is_open"] != 1:
                bot.answer_callback_query(call.id, "Голосование закрыто")
                return
            criterion = db.get_criterion(criterion_id)
            if not criterion:
                bot.answer_callback_query(call.id, "Критерий не найден")
                return
            min_score = criterion["min_score"] if criterion["min_score"] is not None else 1
            max_score = criterion["max_score"] if criterion["max_score"] is not None else 10
            if score < min_score or score > max_score:
                bot.answer_callback_query(call.id, "Недопустимая оценка")
                return
            jury_id = auth.resolve_jury_id(call.from_user.id)
            voting.set_vote(jury_id, class_id, criterion_id, score)
            user_name = f"{call.from_user.first_name or ''} {call.from_user.last_name or ''}".strip()
            meta = {
                "actor": {
                    "telegram_id": call.from_user.id,
                    "name": user_name or None,
                    "username": call.from_user.username,
                    "role": auth.get_role(call.from_user.id),
                },
                "class": {
                    "class_id": class_id,
                    "song_title": cls["song_title"] or "—",
                },
                "criterion": {
                    "id": criterion_id,
                    "name": criterion["name"],
                    "min_score": min_score,
                    "max_score": max_score,
                },
                "score": score,
                "source": "bot",
            }
            audit.log_action(bot, call.from_user.id, "vote", meta)
            criteria = db.list_criteria()
            votes = voting.user_votes_for_class(jury_id, class_id)
            progress = voting.get_class_progress(class_id)
            text = _class_card_text(cls, progress, len(criteria), len(votes))
            _edit_or_send(bot, call, text, jury_class_card_keyboard(criteria, class_id, votes, True))
            _export_web_results()
            _check_auto_finalize(bot)
            return

        if call.data == "jury:my":
            _edit_or_send(bot, call, _my_votes_text(call.from_user.id), jury_main_menu())
            return

        if call.data == "jury:results":
            res = results.get_results()
            jury_total = db.count_jury()
            jury_voted = results.count_jury_voted()
            text = results.format_results("Промежуточные итоги", res, jury_voted, jury_total)
            _edit_or_send(bot, call, text, jury_main_menu())
            return

        if call.data == "jury:status":
            _edit_or_send(bot, call, _status_text(), jury_main_menu())
            return

        if call.data == "jury:help":
            text = "Если у вас есть код приглашения, используйте /join и отправьте код следующим сообщением. Голосование доступно только при открытии класса."
            _edit_or_send(bot, call, text, jury_main_menu())
            return

        bot.answer_callback_query(call.id, "Команда не распознана")

    def _check_auto_finalize(bot):
        if db.get_setting("final_sent") == "1":
            return
        if not voting.all_classes_complete():
            return
        res = results.get_results()
        jury_total = db.count_jury()
        jury_voted = results.count_jury_voted()
        text = results.format_results("Финальные итоги", res, jury_voted, jury_total)
        db.set_setting("final_sent", "1")
        for admin in db.list_admin_users():
            try:
                bot.send_message(admin["telegram_id"], text)
            except Exception:
                continue

    def _export_web_results() -> None:
        if not WEB_ENABLED:
            return
        results.export_results_json(WEB_RESULTS_PATH)
