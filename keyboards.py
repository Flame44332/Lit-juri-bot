from telebot import types

SHORT_CRITERIA_LABELS = {
    "Вокал: Живое исполнение (или записана своя фонограмма)": "Вокал: живое/своя фонограмма",
    "Вокал: Техника": "Вокал: техника",
    "Вокал: Артистизм": "Вокал: артистизм",
    "Видео-визитка: Наличие видео-визитки": "Видео: визитка есть",
    "Видео-визитка: Сюжет": "Видео: сюжет",
    "Видео-визитка: Качество": "Видео: качество",
    "Яркость: Сюжет (соответствует тематике)": "Яркость: сюжет (тема)",
    "Яркость: Танец": "Яркость: танец",
    "Яркость: Декорации и/или костюмы": "Яркость: декор/костюмы",
    "Яркость: Артистизм": "Яркость: артистизм",
    "Бонусный балл (по желанию)": "Бонус (по желанию)",
}


def _short_criterion_label(name: str) -> str:
    short = SHORT_CRITERIA_LABELS.get(name)
    if short:
        return short
    if len(name) <= 32:
        return name
    return name[:29].rstrip() + "..."


def admin_main_menu() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("Классы и песни", callback_data="adm:classes"),
        types.InlineKeyboardButton("Очередь выступлений", callback_data="adm:queue"),
        types.InlineKeyboardButton("Критерии", callback_data="adm:criteria"),
        types.InlineKeyboardButton("Пользователи", callback_data="adm:users"),
        types.InlineKeyboardButton("Управление голосованием", callback_data="adm:voting"),
        types.InlineKeyboardButton("Результаты", callback_data="adm:results"),
        types.InlineKeyboardButton("Настройки/Сервис", callback_data="adm:settings"),
    )
    return kb


def jury_main_menu() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("Голосовать", callback_data="jury:vote"),
        types.InlineKeyboardButton("Мои оценки", callback_data="jury:my"),
        types.InlineKeyboardButton("Промежуточные итоги", callback_data="jury:results"),
        types.InlineKeyboardButton("Статус выступлений", callback_data="jury:status"),
        types.InlineKeyboardButton("Помощь", callback_data="jury:help"),
    )
    return kb


def back_button(callback: str) -> types.InlineKeyboardButton:
    return types.InlineKeyboardButton("⬅️ Назад", callback_data=callback)


def parallel_keyboard(prefix: str, back: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("9 параллель", callback_data=f"{prefix}:par:9"),
        types.InlineKeyboardButton("10 параллель", callback_data=f"{prefix}:par:10"),
        types.InlineKeyboardButton("11 параллель", callback_data=f"{prefix}:par:11"),
    )
    kb.add(back_button(back))
    return kb


def class_list_keyboard(classes, prefix: str, back: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    for cls in classes:
        label = f"{cls['class_id']}"
        kb.add(types.InlineKeyboardButton(label, callback_data=f"{prefix}:class:{cls['class_id']}"))
    kb.add(back_button(back))
    return kb


def admin_class_card_keyboard(class_id: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✏️ Изменить песню", callback_data=f"adm:class:edit_song:{class_id}"),
        types.InlineKeyboardButton("🔢 Изменить номер", callback_data=f"adm:class:edit_order:{class_id}"),
    )
    kb.add(back_button("adm:classes"))
    return kb


def admin_queue_menu_keyboard() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔁 Поменять местами", callback_data="adm:queue:swap"),
        types.InlineKeyboardButton("🔢 Поставить номер", callback_data="adm:queue:set"),
    )
    kb.add(back_button("adm:menu"))
    return kb


def admin_criteria_menu_keyboard() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("➕ Добавить", callback_data="adm:criteria:add"),
        types.InlineKeyboardButton("✏️ Переименовать", callback_data="adm:criteria:rename"),
        types.InlineKeyboardButton("🗑️ Удалить", callback_data="adm:criteria:delete"),
    )
    kb.add(back_button("adm:menu"))
    return kb


def criteria_select_keyboard(criteria, action: str, back: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for c in criteria:
        kb.add(types.InlineKeyboardButton(c["name"], callback_data=f"adm:criteria:{action}:{c['id']}"))
    kb.add(back_button(back))
    return kb


def admin_users_menu_keyboard() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("Админы", callback_data="adm:users:admins"),
        types.InlineKeyboardButton("Жюри", callback_data="adm:users:jury"),
        types.InlineKeyboardButton("Коды приглашений", callback_data="adm:users:invites"),
        types.InlineKeyboardButton("Создать админ-аккаунт", callback_data="adm:users:create_admin"),
        types.InlineKeyboardButton("Создать жюри (код)", callback_data="adm:users:create_jury"),
    )
    kb.add(back_button("adm:menu"))
    return kb


def admin_invites_keyboard(invites) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("Создать многоразовый", callback_data="adm:invites:create:multi"),
        types.InlineKeyboardButton("Создать одноразовый", callback_data="adm:invites:create:single"),
    )
    for inv in invites:
        status = "✅" if inv["is_active"] == 1 else "🚫"
        kb.add(
            types.InlineKeyboardButton(
                f"{status} {inv['code']}", callback_data=f"adm:invites:toggle:{inv['code']}"
            )
        )
    kb.add(back_button("adm:users"))
    return kb


def admin_voting_menu_keyboard() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("Открыть голосование", callback_data="adm:voting:open"),
        types.InlineKeyboardButton("Закрыть голосование", callback_data="adm:voting:close"),
        types.InlineKeyboardButton("Следующий по очереди", callback_data="adm:voting:next"),
        types.InlineKeyboardButton("Напомнить жюри", callback_data="adm:voting:remind"),
        types.InlineKeyboardButton("Статус", callback_data="adm:voting:status"),
    )
    kb.add(back_button("adm:menu"))
    return kb


def confirm_keyboard(confirm_cb: str, back_cb: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Подтвердить", callback_data=confirm_cb),
        types.InlineKeyboardButton("⬅️ Отмена", callback_data=back_cb),
    )
    return kb


def admin_results_menu_keyboard() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("Промежуточные результаты", callback_data="adm:results:partial"),
        types.InlineKeyboardButton("Финальные результаты", callback_data="adm:results:final"),
    )
    kb.add(back_button("adm:menu"))
    return kb


def admin_settings_menu_keyboard() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("Экспорт CSV", callback_data="adm:settings:export"),
        types.InlineKeyboardButton("Сбросить голоса", callback_data="adm:settings:reset"),
        types.InlineKeyboardButton("Логи действий", callback_data="adm:settings:logs"),
    )
    kb.add(back_button("adm:menu"))
    return kb


def jury_class_card_keyboard(criteria, class_id: str, votes: dict[int, int], is_open: bool) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    if is_open:
        for c in criteria:
            score = votes.get(int(c["id"]))
            min_score = c["min_score"] if "min_score" in c.keys() and c["min_score"] is not None else 1
            max_score = c["max_score"] if "max_score" in c.keys() and c["max_score"] is not None else 10
            name = _short_criterion_label(c["name"])
            score_text = score if score is not None else "—"
            label = f"{score_text} | {name} ({min_score}-{max_score})"
            kb.add(types.InlineKeyboardButton(label, callback_data=f"jury:criterion:{class_id}:{c['id']}"))
    kb.add(back_button("jury:vote"))
    return kb


def score_keyboard(class_id: str, criterion_id: int, min_score: int, max_score: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=5)
    start = int(min_score)
    end = int(max_score)
    if end < start:
        start, end = end, start
    buttons = [
        types.InlineKeyboardButton(str(i), callback_data=f"jury:score:{class_id}:{criterion_id}:{i}")
        for i in range(start, end + 1)
    ]
    kb.add(*buttons)
    kb.add(back_button(f"jury:class:{class_id}"))
    return kb


def jury_vote_menu_keyboard() -> types.InlineKeyboardMarkup:
    return parallel_keyboard("jury", "jury:menu")


def jury_open_vote_keyboard(class_id: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("Голосовать", callback_data=f"jury:class:{class_id}"))
    return kb


def admin_open_menu_keyboard() -> types.InlineKeyboardMarkup:
    return parallel_keyboard("adm:voting:open", "adm:voting")


def admin_close_menu_keyboard(classes) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    for cls in classes:
        kb.add(
            types.InlineKeyboardButton(
                f"{cls['class_id']}", callback_data=f"adm:voting:close:class:{cls['class_id']}"
            )
        )
    kb.add(back_button("adm:voting"))
    return kb


def admin_class_list_for_set_order(classes, action: str, back: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    for cls in classes:
        kb.add(types.InlineKeyboardButton(cls["class_id"], callback_data=f"{action}:{cls['class_id']}"))
    kb.add(back_button(back))
    return kb


def order_select_keyboard(action_prefix: str, class_id: str, back: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=6)
    buttons = [
        types.InlineKeyboardButton(str(i), callback_data=f"{action_prefix}:{class_id}:{i}")
        for i in range(1, 19)
    ]
    kb.add(*buttons)
    kb.add(back_button(back))
    return kb
