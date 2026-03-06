import json
import logging
from io import BytesIO

from telebot import types

import db
from keyboards import (
    admin_class_card_keyboard,
    admin_close_menu_keyboard,
    admin_class_list_for_set_order,
    admin_criteria_menu_keyboard,
    admin_invites_keyboard,
    admin_main_menu,
    admin_open_menu_keyboard,
    admin_queue_menu_keyboard,
    admin_results_menu_keyboard,
    admin_settings_menu_keyboard,
    admin_users_menu_keyboard,
    admin_voting_menu_keyboard,
    class_list_keyboard,
    confirm_keyboard,
    criteria_select_keyboard,
    jury_open_vote_keyboard,
    order_select_keyboard,
    parallel_keyboard,
)
from services import auth, results, utils, voting, audit
from config import WEB_ENABLED, WEB_RESULTS_PATH
from handlers.common import clear_session, get_session, set_session, send_admin_menu, sync_user

logger = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    return auth.is_admin(auth.get_role(user_id))


def _edit_or_send(bot, call, text: str, kb=None) -> None:
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb)
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=kb)


def _actor_meta(user: types.User) -> dict:
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return {
        "telegram_id": user.id,
        "name": name or None,
        "username": user.username,
        "role": auth.get_role(user.id),
    }


def _class_card_text(cls, progress: tuple[int, int]) -> str:
    status = utils.format_status(cls["is_open"], cls["is_finished"])
    voted, total = progress
    song = cls["song_title"] or "—"
    return (
        f"Класс {cls['class_id']}\n"
        f"Песня: {song}\n"
        f"№ в очереди: {cls['performance_order']}\n"
        f"Статус: {status}\n"
        f"Прогресс: {voted}/{total} жюри"
    )


def _list_classes_text(classes) -> str:
    lines = ["Очередь выступлений:"]
    for cls in classes:
        song = cls["song_title"] or "—"
        lines.append(f"{cls['performance_order']}. {cls['class_id']} — {song}")
    return "\n".join(lines)


def _list_criteria_text(criteria) -> str:
    lines = ["Критерии:"]
    for c in criteria:
        min_score = c["min_score"] if "min_score" in c.keys() and c["min_score"] is not None else 1
        max_score = c["max_score"] if "max_score" in c.keys() and c["max_score"] is not None else 10
        lines.append(f"{c['id']}. {c['name']} ({min_score}-{max_score})")
    return "\n".join(lines)


def _list_admin_accounts_text(accounts) -> str:
    lines = ["Админ-аккаунты:"]
    for a in accounts:
        linked = "✅" if a["telegram_id"] else "—"
        lines.append(f"{a['username']} / {a['password']} — привязан: {linked}")
    lines.append("\nПривязка: /link login password")
    return "\n".join(lines)


def _list_jury_text(jury) -> str:
    lines = ["Жюри:"]
    for j in jury:
        name = j["tg_name"] or "—"
        username = f"@{j['tg_username']}" if j["tg_username"] else "—"
        code = j["jury_code"] if "jury_code" in j.keys() and j["jury_code"] else "—"
        lines.append(f"{j['telegram_id']} — {code} — {name} — {username}")
    return "\n".join(lines)


def _status_list_text() -> str:
    classes = db.list_classes_ordered()
    lines = ["Статус по классам:"]
    for cls in classes:
        status = utils.format_status(cls["is_open"], cls["is_finished"])
        voted, total = voting.get_class_progress(cls["class_id"])
        lines.append(f"{cls['class_id']} — {status} — {voted}/{total}")
    return "\n".join(lines)


def _send_results(bot, chat_id: int, title: str) -> None:
    res = results.get_results()
    jury_total = db.count_jury()
    jury_voted = results.count_jury_voted()
    text = results.format_results(title, res, jury_voted, jury_total)
    bot.send_message(chat_id, text)
    _export_web_results()


def _send_csv(bot, chat_id: int, filename: str, headers: list[str], rows: list[list]) -> None:
    data = utils.csv_bytes(headers, rows)
    bio = BytesIO(data)
    bio.name = filename
    bot.send_document(chat_id, bio)


def _export_web_results() -> None:
    if not WEB_ENABLED:
        return
    results.export_results_json(WEB_RESULTS_PATH)


def register(bot):
    @bot.callback_query_handler(func=lambda call: call.data.startswith("adm:"))
    def admin_callbacks(call: types.CallbackQuery):
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "Доступ только для админов")
            return
        sync_user(call.from_user)

        data = call.data.split(":")

        if call.data == "adm:menu":
            _edit_or_send(bot, call, "Админ-панель. Выберите раздел:", admin_main_menu())
            return

        if call.data == "adm:classes":
            _edit_or_send(bot, call, "Выберите параллель:", parallel_keyboard("adm:classes", "adm:menu"))
            return

        if len(data) >= 3 and data[0] == "adm" and data[1] == "classes" and data[2] == "par":
            parallel = int(data[3])
            classes = db.list_classes_by_parallel(parallel)
            _edit_or_send(bot, call, f"Параллель {parallel}. Выберите класс:", class_list_keyboard(classes, "adm:classes", "adm:classes"))
            return

        if len(data) >= 4 and data[0] == "adm" and data[1] == "classes" and data[2] == "class":
            class_id = data[3]
            cls = db.get_class(class_id)
            if not cls:
                bot.answer_callback_query(call.id, "Класс не найден")
                return
            progress = voting.get_class_progress(class_id)
            text = _class_card_text(cls, progress)
            _edit_or_send(bot, call, text, admin_class_card_keyboard(class_id))
            return

        if len(data) >= 4 and data[0] == "adm" and data[1] == "class" and data[2] == "edit_song":
            class_id = data[3]
            set_session(call.from_user.id, "edit_song", {"class_id": class_id})
            bot.send_message(call.message.chat.id, f"Введите название песни для {class_id}:")
            return

        if len(data) >= 4 and data[0] == "adm" and data[1] == "class" and data[2] == "edit_order":
            class_id = data[3]
            kb = order_select_keyboard("adm:class:order", class_id, f"adm:classes:class:{class_id}")
            _edit_or_send(bot, call, f"Выберите номер выступления для {class_id}:", kb)
            return

        if len(data) >= 5 and data[0] == "adm" and data[1] == "class" and data[2] == "order":
            class_id = data[3]
            order = int(data[4])
            db.update_class_order(class_id, order)
            cls = db.get_class(class_id)
            progress = voting.get_class_progress(class_id)
            _edit_or_send(bot, call, _class_card_text(cls, progress), admin_class_card_keyboard(class_id))
            _export_web_results()
            return

        if call.data == "adm:queue":
            classes = db.list_classes_ordered()
            _edit_or_send(bot, call, _list_classes_text(classes), admin_queue_menu_keyboard())
            return

        if call.data == "adm:queue:swap":
            classes = db.list_classes_ordered()
            kb = admin_class_list_for_set_order(classes, "adm:queue:swap:first", "adm:queue")
            _edit_or_send(bot, call, "Выберите первый класс для обмена:", kb)
            return

        if len(data) >= 5 and data[0] == "adm" and data[1] == "queue" and data[2] == "swap" and data[3] == "first":
            class_id = data[4]
            set_session(call.from_user.id, "swap_first", {"class_id": class_id})
            classes = db.list_classes_ordered()
            kb = admin_class_list_for_set_order(classes, "adm:queue:swap:second", "adm:queue")
            _edit_or_send(bot, call, "Выберите второй класс для обмена:", kb)
            return

        if len(data) >= 5 and data[0] == "adm" and data[1] == "queue" and data[2] == "swap" and data[3] == "second":
            sess = get_session(call.from_user.id)
            if not sess or sess[0] != "swap_first":
                bot.answer_callback_query(call.id, "Сессия не найдена")
                return
            first = sess[1].get("class_id")
            second = data[4]
            if first == second:
                bot.answer_callback_query(call.id, "Выберите другой класс")
                return
            db.swap_class_order(first, second)
            clear_session(call.from_user.id)
            classes = db.list_classes_ordered()
            _edit_or_send(bot, call, _list_classes_text(classes), admin_queue_menu_keyboard())
            _export_web_results()
            return

        if call.data == "adm:queue:set":
            classes = db.list_classes_ordered()
            kb = admin_class_list_for_set_order(classes, "adm:queue:set:class", "adm:queue")
            _edit_or_send(bot, call, "Выберите класс:", kb)
            return

        if len(data) >= 5 and data[0] == "adm" and data[1] == "queue" and data[2] == "set" and data[3] == "class":
            class_id = data[4]
            kb = order_select_keyboard("adm:queue:set:order", class_id, "adm:queue")
            _edit_or_send(bot, call, f"Выберите номер для {class_id}:", kb)
            return

        if len(data) >= 6 and data[0] == "adm" and data[1] == "queue" and data[2] == "set" and data[3] == "order":
            class_id = data[4]
            order = int(data[5])
            db.update_class_order(class_id, order)
            classes = db.list_classes_ordered()
            _edit_or_send(bot, call, _list_classes_text(classes), admin_queue_menu_keyboard())
            _export_web_results()
            return

        if call.data == "adm:criteria":
            criteria = db.list_criteria()
            _edit_or_send(bot, call, _list_criteria_text(criteria), admin_criteria_menu_keyboard())
            return

        if call.data == "adm:criteria:add":
            set_session(call.from_user.id, "criteria_add", {})
            bot.send_message(call.message.chat.id, "Введите название критерия:")
            return

        if call.data == "adm:criteria:rename":
            criteria = db.list_criteria()
            kb = criteria_select_keyboard(criteria, "rename", "adm:criteria")
            _edit_or_send(bot, call, "Выберите критерий:", kb)
            return

        if len(data) >= 4 and data[0] == "adm" and data[1] == "criteria" and data[2] == "rename":
            criterion_id = int(data[3])
            set_session(call.from_user.id, "criteria_rename", {"id": criterion_id})
            bot.send_message(call.message.chat.id, "Введите новое название:")
            return

        if call.data == "adm:criteria:delete":
            criteria = db.list_criteria()
            kb = criteria_select_keyboard(criteria, "delete", "adm:criteria")
            _edit_or_send(bot, call, "Выберите критерий для удаления:", kb)
            return

        if len(data) >= 4 and data[0] == "adm" and data[1] == "criteria" and data[2] == "delete":
            criterion_id = int(data[3])
            if db.count_votes_for_criterion(criterion_id) > 0:
                bot.answer_callback_query(call.id, "Нельзя удалить: есть голоса")
                return
            kb = confirm_keyboard(f"adm:criteria:delete:confirm:{criterion_id}", "adm:criteria")
            _edit_or_send(bot, call, "Подтвердите удаление критерия:", kb)
            return

        if len(data) >= 5 and data[0] == "adm" and data[1] == "criteria" and data[2] == "delete" and data[3] == "confirm":
            criterion_id = int(data[4])
            db.delete_criterion(criterion_id)
            criteria = db.list_criteria()
            _edit_or_send(bot, call, _list_criteria_text(criteria), admin_criteria_menu_keyboard())
            return

        if call.data == "adm:users":
            _edit_or_send(bot, call, "Управление пользователями:", admin_users_menu_keyboard())
            return

        if call.data == "adm:users:admins":
            accounts = db.list_admin_accounts()
            _edit_or_send(bot, call, _list_admin_accounts_text(accounts), admin_users_menu_keyboard())
            return

        if call.data == "adm:users:jury":
            jury = db.list_jury()
            _edit_or_send(bot, call, _list_jury_text(jury), admin_users_menu_keyboard())
            return

        if call.data == "adm:users:invites":
            invites = db.list_invites()
            _edit_or_send(bot, call, "Коды приглашений:", admin_invites_keyboard(invites))
            return

        if call.data == "adm:users:create_admin":
            set_session(call.from_user.id, "admin_create", {})
            bot.send_message(call.message.chat.id, "Введите username для админ-аккаунта:")
            return

        if call.data == "adm:users:create_jury":
            set_session(call.from_user.id, "jury_create", {})
            bot.send_message(call.message.chat.id, "Введите имя жюри (для логов):")
            return

        if len(data) >= 4 and data[0] == "adm" and data[1] == "invites" and data[2] == "create":
            code = utils.generate_code(6)
            if data[3] == "single":
                db.create_invite(code, max_uses=1)
                bot.send_message(call.message.chat.id, f"Одноразовый код: {code}")
            else:
                db.create_invite(code, max_uses=None)
                bot.send_message(call.message.chat.id, f"Многоразовый код: {code}")
            invites = db.list_invites()
            bot.send_message(call.message.chat.id, "Коды приглашений:", reply_markup=admin_invites_keyboard(invites))
            return

        if len(data) >= 4 and data[0] == "adm" and data[1] == "invites" and data[2] == "toggle":
            code = data[3]
            invites = db.list_invites()
            current = next((i for i in invites if i["code"] == code), None)
            if current:
                new_state = 0 if current["is_active"] == 1 else 1
                db.set_invite_active(code, new_state)
            invites = db.list_invites()
            _edit_or_send(bot, call, "Коды приглашений:", admin_invites_keyboard(invites))
            return

        if call.data == "adm:voting":
            _edit_or_send(bot, call, "Управление голосованием:", admin_voting_menu_keyboard())
            return

        if call.data == "adm:voting:open":
            _edit_or_send(bot, call, "Выберите параллель:", admin_open_menu_keyboard())
            return

        if len(data) >= 5 and data[0] == "adm" and data[1] == "voting" and data[2] == "open" and data[3] == "par":
            parallel = int(data[4])
            classes = db.list_classes_by_parallel(parallel)
            _edit_or_send(bot, call, "Выберите класс:", class_list_keyboard(classes, "adm:voting:open", "adm:voting:open"))
            return

        if len(data) >= 5 and data[0] == "adm" and data[1] == "voting" and data[2] == "open" and data[3] == "class":
            class_id = data[4]
            kb = confirm_keyboard(f"adm:voting:open:confirm:{class_id}", "adm:voting")
            _edit_or_send(bot, call, f"Открыть голосование для {class_id}?", kb)
            return

        if len(data) >= 5 and data[0] == "adm" and data[1] == "voting" and data[2] == "open" and data[3] == "confirm":
            class_id = data[4]
            try:
                voting.open_class(class_id)
            except voting.VotingError as exc:
                bot.answer_callback_query(call.id, str(exc))
                return
            cls = db.get_class(class_id)
            meta = {
                "actor": _actor_meta(call.from_user),
                "class": {
                    "class_id": class_id,
                    "song_title": cls["song_title"] if cls else None,
                },
            }
            audit.log_action(bot, call.from_user.id, "open_class", meta)
            _edit_or_send(bot, call, f"Голосование открыто для {class_id}", admin_voting_menu_keyboard())
            _notify_jury(bot, class_id)
            return

        if call.data == "adm:voting:close":
            open_classes = [c for c in db.list_classes_ordered() if c["is_open"] == 1]
            if not open_classes:
                bot.answer_callback_query(call.id, "Нет открытых классов")
                return
            _edit_or_send(bot, call, "Выберите класс для закрытия:", admin_close_menu_keyboard(open_classes))
            return

        if len(data) >= 5 and data[0] == "adm" and data[1] == "voting" and data[2] == "close" and data[3] == "class":
            class_id = data[4]
            kb = confirm_keyboard(f"adm:voting:close:confirm:{class_id}", "adm:voting")
            _edit_or_send(bot, call, f"Закрыть голосование для {class_id}?", kb)
            return

        if len(data) >= 5 and data[0] == "adm" and data[1] == "voting" and data[2] == "close" and data[3] == "confirm":
            class_id = data[4]
            voting.close_class(class_id)
            cls = db.get_class(class_id)
            meta = {
                "actor": _actor_meta(call.from_user),
                "class": {
                    "class_id": class_id,
                    "song_title": cls["song_title"] if cls else None,
                },
            }
            audit.log_action(bot, call.from_user.id, "close_class", meta)
            _edit_or_send(bot, call, f"Голосование закрыто для {class_id}", admin_voting_menu_keyboard())
            return

        if call.data == "adm:voting:next":
            active = voting.get_active_class_id()
            if active:
                bot.answer_callback_query(call.id, f"Сначала закройте {active}")
                return
            classes = [c for c in db.list_classes_ordered() if c["is_finished"] == 0]
            if not classes:
                bot.answer_callback_query(call.id, "Все классы завершены")
                return
            next_class = classes[0]["class_id"]
            kb = confirm_keyboard(f"adm:voting:next:confirm:{next_class}", "adm:voting")
            _edit_or_send(bot, call, f"Открыть следующий по очереди: {next_class}?", kb)
            return

        if len(data) >= 5 and data[0] == "adm" and data[1] == "voting" and data[2] == "next" and data[3] == "confirm":
            class_id = data[4]
            try:
                voting.open_class(class_id)
            except voting.VotingError as exc:
                bot.answer_callback_query(call.id, str(exc))
                return
            cls = db.get_class(class_id)
            meta = {
                "actor": _actor_meta(call.from_user),
                "class": {
                    "class_id": class_id,
                    "song_title": cls["song_title"] if cls else None,
                },
            }
            audit.log_action(bot, call.from_user.id, "open_class", meta)
            _edit_or_send(bot, call, f"Голосование открыто для {class_id}", admin_voting_menu_keyboard())
            _notify_jury(bot, class_id)
            return

        if call.data == "adm:voting:status":
            _edit_or_send(bot, call, _status_list_text(), admin_voting_menu_keyboard())
            return

        if call.data == "adm:voting:remind":
            active = voting.get_active_class_id()
            if not active:
                bot.answer_callback_query(call.id, "Нет открытого класса")
                return
            cls = db.get_class(active)
            criteria = db.list_criteria()
            if not criteria:
                bot.answer_callback_query(call.id, "Нет критериев для голосования")
                return
            total = len(criteria)
            sent = 0
            pending = 0
            failed = 0
            for uid in db.list_jury_telegram_ids():
                jury_id = auth.resolve_jury_id(uid)
                votes = db.get_votes_for_user_class(jury_id, active)
                missing = [c for c in criteria if int(c["id"]) not in votes]
                if not missing:
                    continue
                pending += 1
                lines = [
                    "Напоминание о голосовании",
                    f"Класс {active} — {cls['song_title'] or '—'}",
                    f"Оценено критериев: {total - len(missing)}/{total}",
                    "Не оценены:",
                ]
                for c in missing:
                    min_score = c["min_score"] if c["min_score"] is not None else 1
                    max_score = c["max_score"] if c["max_score"] is not None else 10
                    lines.append(f"- {c['name']} ({min_score}-{max_score})")
                text = "\n".join(lines)
                try:
                    bot.send_message(uid, text, reply_markup=jury_open_vote_keyboard(active))
                    sent += 1
                except Exception:
                    failed += 1
                    continue
            meta = {
                "actor": _actor_meta(call.from_user),
                "class": {"class_id": active, "song_title": cls["song_title"] if cls else None},
                "pending": pending,
                "sent": sent,
                "failed": failed,
            }
            audit.log_action(bot, call.from_user.id, "remind_jury", meta)
            bot.answer_callback_query(call.id, f"Отправлено: {sent}, нужно: {pending}")
            return

        if call.data == "adm:results":
            _edit_or_send(bot, call, "Результаты:", admin_results_menu_keyboard())
            return

        if call.data == "adm:results:partial":
            _send_results(bot, call.message.chat.id, "Промежуточные итоги")
            return

        if call.data == "adm:results:final":
            if voting.all_classes_complete() or db.get_setting("final_forced") == "1":
                db.set_setting("final_sent", "1")
                _send_results(bot, call.message.chat.id, "Финальные итоги")
                return
            kb = confirm_keyboard("adm:results:final:confirm", "adm:results")
            _edit_or_send(bot, call, "Не все классы завершены. Посчитать финал принудительно?", kb)
            return

        if call.data == "adm:results:final:confirm":
            db.set_setting("final_forced", "1")
            db.set_setting("final_sent", "1")
            _send_results(bot, call.message.chat.id, "Финальные итоги")
            return

        if call.data == "adm:settings":
            _edit_or_send(bot, call, "Настройки/Сервис:", admin_settings_menu_keyboard())
            return

        if call.data == "adm:settings:export":
            _export_all(bot, call.message.chat.id)
            return

        if call.data == "adm:settings:reset":
            kb = confirm_keyboard("adm:settings:reset:confirm1", "adm:settings")
            _edit_or_send(bot, call, "Сбросить все голоса?", kb)
            return

        if call.data == "adm:settings:reset:confirm1":
            set_session(call.from_user.id, "reset_confirmed", {})
            kb = confirm_keyboard("adm:settings:reset:confirm2", "adm:settings")
            _edit_or_send(bot, call, "Подтверждение 2/2. Сбросить?", kb)
            return

        if call.data == "adm:settings:reset:confirm2":
            sess = get_session(call.from_user.id)
            if not sess or sess[0] != "reset_confirmed":
                bot.answer_callback_query(call.id, "Нет подтверждения")
                return
            db.delete_votes()
            db.reset_classes_state()
            db.set_setting("active_class_id", "")
            db.set_setting("final_forced", "0")
            db.set_setting("final_sent", "0")
            clear_session(call.from_user.id)
            audit.log_action(bot, call.from_user.id, "reset_votes")
            _edit_or_send(bot, call, "Голоса сброшены", admin_settings_menu_keyboard())
            _export_web_results()
            return

        if call.data == "adm:settings:logs":
            logs = db.list_audit(20)
            lines = ["Последние действия:"]
            for item in logs:
                lines.append(f"{item['at']} — {item['actor_telegram_id']} — {item['action']} — {item['meta'] or ''}")
            _edit_or_send(bot, call, "\n".join(lines), admin_settings_menu_keyboard())
            return

        bot.answer_callback_query(call.id, "Команда не распознана")

    @bot.message_handler(content_types=["text"])
    def admin_text_handler(message: types.Message):
        if message.text and message.text.startswith("/"):
            return
        if not _is_admin(message.from_user.id):
            return
        sync_user(message.from_user)
        sess = get_session(message.from_user.id)
        if not sess:
            return
        state, data = sess

        if state == "edit_song":
            class_id = data.get("class_id")
            db.update_class_song(class_id, message.text.strip())
            clear_session(message.from_user.id)
            cls = db.get_class(class_id)
            progress = voting.get_class_progress(class_id)
            bot.send_message(message.chat.id, _class_card_text(cls, progress), reply_markup=admin_class_card_keyboard(class_id))
            _export_web_results()
            return

        if state == "criteria_add":
            name = message.text.strip()
            try:
                db.add_criterion(name)
                audit.log_action(bot, message.from_user.id, "add_criterion", {"name": name})
                bot.send_message(message.chat.id, "Критерий добавлен", reply_markup=admin_criteria_menu_keyboard())
            except Exception:
                bot.send_message(message.chat.id, "Не удалось добавить критерий. Возможно, он уже существует.")
            clear_session(message.from_user.id)
            return

        if state == "criteria_rename":
            criterion_id = int(data.get("id"))
            name = message.text.strip()
            db.rename_criterion(criterion_id, name)
            audit.log_action(
                bot,
                message.from_user.id,
                "rename_criterion",
                {"id": criterion_id, "name": name},
            )
            clear_session(message.from_user.id)
            bot.send_message(message.chat.id, "Критерий переименован", reply_markup=admin_criteria_menu_keyboard())
            return

        if state == "admin_create":
            username = message.text.strip()
            password = utils.generate_password(10)
            try:
                db.create_admin_account(username, password)
                audit.log_action(bot, message.from_user.id, "create_admin", {"username": username})
                bot.send_message(message.chat.id, f"Создан аккаунт: {username} / {password}")
            except Exception:
                bot.send_message(message.chat.id, "Не удалось создать аккаунт (возможно, уже существует).")
            clear_session(message.from_user.id)
            return

        if state == "jury_create":
            name = message.text.strip()
            if not name:
                bot.send_message(message.chat.id, "Введите имя жюри.")
                return
            code = None
            for _ in range(10):
                candidate = utils.generate_code(6)
                if db.get_invite(candidate):
                    continue
                code = candidate
                break
            if not code:
                bot.send_message(message.chat.id, "Не удалось создать код. Попробуйте ещё раз.")
                clear_session(message.from_user.id)
                return
            try:
                db.create_invite(code, max_uses=1)
                jury_id = db.jury_id_from_code(code)
                db.upsert_user(jury_id, "jury", None, name)
                db.set_user_jury_code(jury_id, code)
                audit.log_action(
                    bot,
                    message.from_user.id,
                    "create_jury_account",
                    {"name": name, "code": code},
                )
                bot.send_message(message.chat.id, f"Жюри создано: {name}\nКод: {code}")
            except Exception:
                bot.send_message(message.chat.id, "Не удалось создать жюри.")
            clear_session(message.from_user.id)
            return

    def _notify_jury(bot, class_id: str) -> None:
        cls = db.get_class(class_id)
        if not cls:
            return
        text = f"Открыто голосование: {class_id} — {cls['song_title'] or '—'}"
        kb = jury_open_vote_keyboard(class_id)
        for uid in db.list_jury_telegram_ids():
            try:
                bot.send_message(uid, text, reply_markup=kb)
            except Exception:
                continue

    def _export_all(bot, chat_id: int) -> None:
        classes = db.list_classes_ordered()
        _send_csv(
            bot,
            chat_id,
            "classes.csv",
            ["class_id", "parallel", "number", "song_title", "performance_order", "is_open", "is_finished"],
            [[c["class_id"], c["parallel"], c["number"], c["song_title"], c["performance_order"], c["is_open"], c["is_finished"]] for c in classes],
        )
        criteria = db.list_criteria()
        _send_csv(
            bot,
            chat_id,
            "criteria.csv",
            ["id", "name", "min_score", "max_score", "group_key"],
            [[c["id"], c["name"], c["min_score"], c["max_score"], c["group_key"]] for c in criteria],
        )
        votes = db.list_votes()
        _send_csv(
            bot,
            chat_id,
            "votes.csv",
            ["telegram_id", "class_id", "criterion_id", "score", "updated_at"],
            [[v["telegram_id"], v["class_id"], v["criterion_id"], v["score"], v["updated_at"]] for v in votes],
        )
        criteria_totals = db.total_scores_by_class_and_criterion()
        _send_csv(
            bot,
            chat_id,
            "criteria_totals.csv",
            ["class_id", "criterion_id", "criterion_name", "group_key", "total"],
            [
                [r["class_id"], r["criterion_id"], r["criterion_name"], r["group_key"], r["total"]]
                for r in criteria_totals
            ],
        )
        res = results.get_results()
        _send_csv(
            bot,
            chat_id,
            "results.csv",
            ["class_id", "song_title", "total", "vocal_total", "video_total", "vocal_video_total", "performance_total"],
            [
                [
                    r.class_id,
                    r.song_title,
                    r.total,
                    r.vocal_total,
                    r.video_total,
                    r.vocal_video_total,
                    r.performance_total,
                ]
                for r in res
            ],
        )
