# app/handlers.py
import asyncio
from datetime import datetime, timezone, timedelta
import json
import os

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from .config import ALLOWED_EDITORS, BUTTONS, MESSAGES
from .calendar_api import get_upcoming_events, add_event_to_calendar
from .bot import telegram_app
from .cache import get_cached_events  # используем кэш для мероприятий
from .usage_stats import log_usage, read_stats

# Состояния диалога создания мероприятия.
TITLE, START_TIME, END_TIME, DESCRIPTION, LOCATION, ORGANIZERS, ANNOUNCE, CONFIRMATION = range(8)

PREVIOUS_STATE = {
    START_TIME: TITLE,
    END_TIME: START_TIME,
    DESCRIPTION: END_TIME,
    LOCATION: DESCRIPTION,
    ORGANIZERS: LOCATION,
    ANNOUNCE: ORGANIZERS,
    CONFIRMATION: ANNOUNCE
}

def get_main_menu_keyboard(user_id: int = None) -> ReplyKeyboardMarkup:
    """
    Генерирует главное меню.
    Для редакторов добавляется дополнительная кнопка «Статистика».
    """
    if user_id is not None and user_id in ALLOWED_EDITORS:
        buttons = [
            [BUTTONS["UPCOMING"], BUTTONS["ADD_EVENT"]],
            [BUTTONS["STATISTICS"]]
        ]
    else:
        buttons = [[BUTTONS["UPCOMING"]]]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=False)

def get_navigation_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[BUTTONS["BACK"], BUTTONS["CANCEL"]]], resize_keyboard=True, one_time_keyboard=True)

def number_to_emoji(n: int) -> str:
    if n == 10:
        return "🔟"
    mapping = {
        "0": "0️⃣",
        "1": "1️⃣",
        "2": "2️⃣",
        "3": "3️⃣",
        "4": "4️⃣",
        "5": "5️⃣",
        "6": "6️⃣",
        "7": "7️⃣",
        "8": "8️⃣",
        "9": "9️⃣"
    }
    return "".join(mapping[d] for d in str(n))

MONTH_NAMES = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}
WEEKDAY_NAMES = {
    0: "пн", 1: "вт", 2: "ср", 3: "чт", 4: "пт", 5: "сб", 6: "вс"
}

async def check_navigation_commands(update: Update, context: ContextTypes.DEFAULT_TYPE, current_state: int):
    text = update.message.text.strip()
    if text == BUTTONS["CANCEL"]:
        await update.message.reply_text(MESSAGES["EVENT_CANCELLED"], reply_markup=get_main_menu_keyboard(update.message.from_user.id))
        return ConversationHandler.END
    if text == BUTTONS["BACK"]:
        prev_state = PREVIOUS_STATE.get(current_state)
        if prev_state is not None:
            await update.message.reply_text("Возврат на предыдущий шаг.", reply_markup=get_navigation_keyboard())
            return prev_state
        else:
            await update.message.reply_text("Невозможно вернуться назад.", reply_markup=get_navigation_keyboard())
            return current_state
    return None

# Глобальный обработчик для записи статистики
async def log_usage_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user:
        await log_usage(user)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id if update.message else None
        reply_markup = get_main_menu_keyboard(user_id)
        await update.message.reply_text(MESSAGES["WELCOME"], reply_markup=reply_markup, parse_mode="HTML")
    except Exception as e:
        print(f"Error in start handler: {e}")

async def events_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Используем кэш для получения мероприятий
    events = await get_cached_events()
    user_id = update.message.from_user.id if update.message else None
    reply_markup = get_main_menu_keyboard(user_id)
    if not events:
        await update.message.reply_text(MESSAGES["NO_EVENTS"], reply_markup=reply_markup)
        return

    is_editor = user_id in ALLOWED_EDITORS if user_id is not None else False

    filtered_events = []
    for event in events:
        summary = event.get("summary", "")
        if not is_editor and "*" in summary:
            continue
        filtered_events.append(event)

    if not filtered_events:
        await update.message.reply_text(MESSAGES["NO_EVENTS"], reply_markup=reply_markup)
        return

    message = ""
    for idx, event in enumerate(filtered_events, start=1):
        emoji_number = number_to_emoji(idx)
        if "dateTime" in event["start"]:
            dt = datetime.fromisoformat(event["start"]["dateTime"])
        else:
            dt = datetime.strptime(event["start"].get("date"), "%Y-%m-%d")
        day = dt.day
        month = MONTH_NAMES.get(dt.month, "")
        weekday = WEEKDAY_NAMES.get(dt.weekday(), "")
        date_str = f"<b>{day} {month} ({weekday})</b>"
        summary = event.get("summary", "Без названия")
        message += f"{emoji_number} {date_str}: {summary}\n"
    
    await update.message.reply_text(message, reply_markup=reply_markup, parse_mode="HTML")

async def statistics_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик кнопки «Статистика» (доступен только редакторам).
    Считывает статистику использования за текущий день и отправляет краткий отчёт.
    """
    user = update.effective_user
    if user is None or user.id not in ALLOWED_EDITORS:
        await update.message.reply_text("У вас нет доступа к статистике.", reply_markup=get_main_menu_keyboard(user.id if user else None))
        return

    try:
        stats = await asyncio.to_thread(read_stats)
        today = datetime.now().strftime("%Y-%m-%d")
        message = "<b>Статистика за сегодня:</b>\n"
        total_interactions = 0
        unique_users = 0
        for uid, info in stats.items():
            interactions = info.get("interactions", {}).get(today, 0)
            if interactions:
                username = info.get("username", uid)
                # Если у имени нет символа '@', добавляем его.
                if not username.startswith("@"):
                    username = "@" + username
                message += f"{username}: {interactions} взаимодействий\n"
                total_interactions += interactions
                unique_users += 1
        message += f"\nВсего взаимодействий: {total_interactions}\nУникальных пользователей: {unique_users}"
        await update.message.reply_text(message, parse_mode="HTML", reply_markup=get_main_menu_keyboard(user.id))
    except Exception as e:
        await update.message.reply_text(f"Ошибка при получении статистики: {e}", reply_markup=get_main_menu_keyboard(user.id))

# Обработчики диалога создания мероприятия (без существенных изменений)

async def add_event_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    if user_id not in ALLOWED_EDITORS:
        await update.message.reply_text(MESSAGES["NOT_AUTHORIZED"], reply_markup=get_main_menu_keyboard(user_id))
        return ConversationHandler.END
    await update.message.reply_text(MESSAGES["ENTER_TITLE"], reply_markup=ReplyKeyboardRemove())
    return TITLE

async def add_event_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nav = await check_navigation_commands(update, context, TITLE)
    if nav is not None:
        return nav

    context.user_data["title"] = update.message.text.strip()
    tomorrow = (datetime.now(timezone(timedelta(hours=7))) + timedelta(days=1)).strftime("%d.%m.%Y")
    example_datetime = f"{tomorrow} 15:00"
    start_message = MESSAGES["ENTER_START"].format(example_date=tomorrow, example_datetime=example_datetime)
    await update.message.reply_text(start_message, reply_markup=get_navigation_keyboard())
    return START_TIME

async def add_event_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nav = await check_navigation_commands(update, context, START_TIME)
    if nav is not None:
        return nav

    text = update.message.text.strip()
    if " " in text:
        try:
            dt = datetime.strptime(text, "%d.%m.%Y %H:%M")
            dt = dt.replace(tzinfo=timezone(timedelta(hours=7)))
            context.user_data["start_time"] = dt
            context.user_data["all_day"] = False
            await update.message.reply_text(MESSAGES["ENTER_END"], reply_markup=get_navigation_keyboard())
            return END_TIME
        except Exception:
            await update.message.reply_text(MESSAGES["INPUT_ERROR"], reply_markup=get_navigation_keyboard())
            return START_TIME
    else:
        try:
            dt = datetime.strptime(text, "%d.%m.%Y")
            dt = dt.replace(tzinfo=timezone(timedelta(hours=7)))
            context.user_data["start_time"] = dt
            context.user_data["all_day"] = True
            context.user_data["end_time"] = dt + timedelta(days=1)
            skip_keyboard = ReplyKeyboardMarkup([[BUTTONS["SKIP"]]], one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text(MESSAGES["ENTER_DESCRIPTION"].format(skip=BUTTONS["SKIP"]), reply_markup=skip_keyboard)
            return DESCRIPTION
        except Exception:
            await update.message.reply_text(MESSAGES["INPUT_ERROR"], reply_markup=get_navigation_keyboard())
            return START_TIME

async def add_event_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nav = await check_navigation_commands(update, context, END_TIME)
    if nav is not None:
        return nav

    text = update.message.text.strip()
    try:
        dt = datetime.strptime(text, "%d.%m.%Y %H:%M")
        dt = dt.replace(tzinfo=timezone(timedelta(hours=7)))
        context.user_data["end_time"] = dt
        skip_keyboard = ReplyKeyboardMarkup([[BUTTONS["SKIP"]]], one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(MESSAGES["ENTER_DESCRIPTION"].format(skip=BUTTONS["SKIP"]), reply_markup=skip_keyboard)
        return DESCRIPTION
    except Exception:
        await update.message.reply_text(MESSAGES["INPUT_ERROR"], reply_markup=get_navigation_keyboard())
        return END_TIME

async def add_event_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nav = await check_navigation_commands(update, context, DESCRIPTION)
    if nav is not None:
        return nav

    text = update.message.text.strip()
    context.user_data["description"] = "" if text.lower() in {"", "-", "0", "пропустить"} else text
    skip_keyboard = ReplyKeyboardMarkup([[BUTTONS["SKIP"]]], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(MESSAGES["ENTER_LOCATION"].format(skip=BUTTONS["SKIP"]), reply_markup=skip_keyboard)
    return LOCATION

async def add_event_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nav = await check_navigation_commands(update, context, LOCATION)
    if nav is not None:
        return nav

    text = update.message.text.strip()
    context.user_data["location"] = "" if text.lower() in {"", "-", "0", "пропустить"} else text
    context.user_data["organizers"] = set()
    keyboard = build_organizers_keyboard(context.user_data["organizers"])
    await update.message.reply_text(MESSAGES["CHOOSE_ORGANIZERS"], reply_markup=keyboard)
    return ORGANIZERS

def build_organizers_keyboard(selected_set: set) -> InlineKeyboardMarkup:
    buttons = []
    for editor_id, editor_name in ALLOWED_EDITORS.items():
        btn_text = f"✅ {editor_name}" if str(editor_id) in selected_set else editor_name
        buttons.append([InlineKeyboardButton(btn_text, callback_data=str(editor_id))])
    buttons.append([InlineKeyboardButton("Готово", callback_data="done")])
    return InlineKeyboardMarkup(buttons)

async def organizers_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "done":
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        announce_keyboard = ReplyKeyboardMarkup([["Да", "Нет"]], one_time_keyboard=True, resize_keyboard=True)
        await query.message.reply_text(MESSAGES["ANNOUNCE_QUERY"], reply_markup=announce_keyboard)
        return ANNOUNCE
    else:
        selected = context.user_data.get("organizers", set())
        if data in selected:
            selected.remove(data)
        else:
            selected.add(data)
        context.user_data["organizers"] = selected
        keyboard = build_organizers_keyboard(selected)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return ORGANIZERS

async def add_event_announce(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nav = await check_navigation_commands(update, context, ANNOUNCE)
    if nav is not None:
        return nav

    text = update.message.text.strip().lower()
    if text == "да":
        context.user_data["announce"] = True
    else:
        context.user_data["announce"] = False

    title = context.user_data.get("title")
    title_display = title if context.user_data.get("announce") else f"{title} *"
    start_time = context.user_data.get("start_time")
    end_time = context.user_data.get("end_time")
    if context.user_data.get("all_day"):
        start_str = start_time.strftime("%d.%m.%Y")
        end_str = (end_time - timedelta(days=1)).strftime("%d.%m.%Y")
    else:
        start_str = start_time.strftime("%d.%m.%Y %H:%M")
        end_str = end_time.strftime("%d.%m.%Y %H:%M")
    description = context.user_data.get("description")
    location = context.user_data.get("location")
    organizers_selected = context.user_data.get("organizers", set())
    organizers_list = [ALLOWED_EDITORS.get(int(editor_id)) for editor_id in organizers_selected]
    organizers_str = ", ".join(organizers_list) if organizers_list else "-"
    summary = (
        f"Название: {title_display}\n"
        f"Начало: {start_str}\n"
        f"Конец: {end_str}\n"
        f"Описание: {description if description else '-'}\n"
        f"Локация: {location if location else '-'}\n"
        f"Организатор(ы): {organizers_str}"
    )
    confirm_keyboard = ReplyKeyboardMarkup([["Да", "Нет"]], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(MESSAGES["CONFIRMATION_QUERY"].format(summary=summary), reply_markup=confirm_keyboard)
    return CONFIRMATION

async def add_event_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nav = await check_navigation_commands(update, context, CONFIRMATION)
    if nav is not None:
        return nav

    text = update.message.text.strip().lower()
    user_id = update.message.from_user.id
    reply_markup = get_main_menu_keyboard(user_id)
    if text == "да":
        title = context.user_data.get("title")
        title = title if context.user_data.get("announce") else f"{title} *"
        start_time = context.user_data.get("start_time")
        end_time = context.user_data.get("end_time")
        description = context.user_data.get("description")
        location = context.user_data.get("location")
        organizers_selected = context.user_data.get("organizers", set())
        organizers_list = [ALLOWED_EDITORS.get(int(editor_id)) for editor_id in organizers_selected]
        organizers_str = ", ".join(organizers_list) if organizers_list else "-"
        event_summary = f"{title} | {organizers_str}"
        added_by = ALLOWED_EDITORS.get(user_id, "Неизвестно")
        event_description = (
            f"Описание: {description if description else '-'}\n"
            f"Локация: {location if location else '-'}\n"
            f"Событие добавил: {added_by}"
        )
        if context.user_data.get("all_day"):
            event_body = {
                "summary": event_summary,
                "start": {"date": start_time.strftime("%Y-%m-%d")},
                "end": {"date": end_time.strftime("%Y-%m-%d")},
                "description": event_description
            }
        else:
            event_body = {
                "summary": event_summary,
                "start": {"dateTime": start_time.isoformat(), "timeZone": "Asia/Tomsk"},
                "end": {"dateTime": end_time.isoformat(), "timeZone": "Asia/Tomsk"},
                "description": event_description
            }
        try:
            await update.message.reply_text(MESSAGES["PROCESSING"], reply_markup=reply_markup)
            created_event = await asyncio.to_thread(add_event_to_calendar, event_body)
            event_link = created_event.get("htmlLink", "нет ссылки")
            await update.message.reply_text(MESSAGES["EVENT_CREATED"].format(link=event_link), reply_markup=reply_markup)
        except Exception as e:
            await update.message.reply_text(f"Ошибка при создании мероприятия: {e}", reply_markup=reply_markup)
    else:
        await update.message.reply_text(MESSAGES["EVENT_CANCELLED"], reply_markup=reply_markup)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    reply_markup = get_main_menu_keyboard(user_id)
    await update.message.reply_text(MESSAGES["EVENT_CANCELLED"], reply_markup=reply_markup)
    return ConversationHandler.END

def setup_handlers():
    # Глобальный обработчик для логирования статистики (с group=0 – срабатывает на все обновления)
    telegram_app.add_handler(MessageHandler(filters.ALL, log_usage_handler), group=1)
    
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("events", events_command))
    telegram_app.add_handler(MessageHandler(filters.Regex(f"^{BUTTONS['UPCOMING']}$"), events_command))
    telegram_app.add_handler(MessageHandler(filters.Regex(f"^{BUTTONS['STATISTICS']}$"), statistics_handler))
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("add_event", add_event_start),
            MessageHandler(filters.Regex(f"^{BUTTONS['ADD_EVENT']}$"), add_event_start)
        ],
        states={
            TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_event_title)
            ],
            START_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_event_start_time)
            ],
            END_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_event_end_time)
            ],
            DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_event_description)
            ],
            LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_event_location)
            ],
            ORGANIZERS: [
                CallbackQueryHandler(organizers_callback, pattern=r"^(done|\d+)$")
            ],
            ANNOUNCE: [
                MessageHandler(filters.Regex("^(Да|Нет|да|нет)$"), add_event_announce)
            ],
            CONFIRMATION: [
                MessageHandler(filters.Regex("^(Да|Нет|да|нет)$"), add_event_confirmation)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    telegram_app.add_handler(conv_handler)
    telegram_app.add_error_handler(lambda update, context: None)

setup_handlers()
