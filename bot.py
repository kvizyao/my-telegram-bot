import os
import asyncio
import logging
from datetime import datetime, date, timedelta
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO)

# --- Переменные окружения ---
BOT_TOKEN = os.environ["BOT_TOKEN"]
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")
PORT = int(os.getenv("PORT", 8000))


# ==================== ДАННЫЕ РАСПИСАНИЯ ====================

def get_week_parity_for_date(target_date: date = None) -> str:
    """
    Определяет четность недели для указанной даты.
    Возвращает: "numerator" (числитель/чётная) или "denominator" (знаменатель/нечётная)
    """
    if target_date is None:
        target_date = date.today()

    start_date = date(target_date.year, 3, 2)

    if target_date < start_date:
        start_date = date(target_date.year - 1, 3, 2)

    delta = (target_date - start_date).days
    week_number = delta // 7

    # Чётная = числитель, нечётная = знаменатель
    return "numerator" if week_number % 2 == 0 else "denominator"


def get_week_parity() -> str:
    """Определяет четность текущей недели"""
    return get_week_parity_for_date(date.today())


# Структура расписания
SCHEDULE = {
    "numerator": {  # Чётная неделя = Числитель
        0: [  # Понедельник
            {"time": "08:30-10:00", "subject": "АСБУ: Автоматизированные системы бухгалтерского учета (1С)",
             "teacher": "Исаева Ириада Евгеньевна", "room": "4-06А", "type": "лекция"},
            {"time": "10:10-11:40", "subject": "физра", "teacher": "", "room": "", "type": ""},
            {"time": "12:00-13:30", "subject": "ППОД: Прикладные пакеты обработки данных",
             "teacher": "Горшкова Ольга Петровна", "room": "2-02А", "type": "лабораторная"},
            {"time": "13:40-15:10", "subject": "ППОД: Прикладные пакеты обработки данных",
             "teacher": "Смирнова Елена Владимировна", "room": "4-22Г", "type": "лекция"}
        ],
        1: [  # Вторник
            {"time": "08:30-10:00",
             "subject": "ПОЭИС: Предметно-ориентированные экономические информационные системы (1С)",
             "teacher": "Трухляева Анна Александровна", "room": "2-02А", "type": "лабораторная"},
            {"time": "10:10-11:40", "subject": "ПСЭД: Проектирование систем электронного документооборота",
             "teacher": "Баубель Юлия Игоревна", "room": "2-02А", "type": "лабораторная"},
            {"time": "12:00-13:30", "subject": "ПСЭД: Проектирование систем электронного документооборота",
             "teacher": "Трухляева Анна Александровна", "room": "4-17В", "type": "лекция"}
        ],
        2: [  # Среда
            {"time": "12:00-13:30", "subject": "ВССТ: Вычислительные системы, сети, телекоммуникации",
             "teacher": "Горте Иван Александрович", "room": "2-02А", "type": "лабораторная"},
            {"time": "13:40-15:10", "subject": "ОУД: Организация и управление данными",
             "teacher": "Шипилева Алла Владимировна", "room": "4-22Г", "type": "лекция"},
            {"time": "15:20-16:50", "subject": "ОУД: Организация и управление данными",
             "teacher": "Шипилева Алла Владимировна", "room": "2-02А", "type": "практика"},
            {"time": "17:00-18:30",
             "subject": "ССУКПО: Стандартизация, сертификация и управление качеством программного обеспечения",
             "teacher": "Смирнова Елена Владимировна", "room": "2-03А", "type": "практика"}
        ],
        3: [  # Четверг
            {"time": "08:30-10:00", "subject": "ВССТ: Вычислительные системы, сети, телекоммуникации",
             "teacher": "Иванченко Геннадий Сергеевич", "room": "2-13В", "type": "лекция"},
            {"time": "10:10-11:40", "subject": "ПИС: Проектирование информационных систем",
             "teacher": "Лапина Марина Сергеевна", "room": "2-13В", "type": "лекция"},
            {"time": "12:00-13:30", "subject": "ПИС: Проектирование информационных систем",
             "teacher": "Калинина Вера Владимировна", "room": "2-02А", "type": "лабораторная"},
            {"time": "13:40-15:10", "subject": "АСБУ: Автоматизированные системы бухгалтерского учета (1С)",
             "teacher": "Баубель Юлия Игоревна", "room": "2-03А", "type": "лабораторная"}
        ],
        4: [],  # Пятница
        5: [],  # Суббота
        6: []  # Воскресенье
    },
    "denominator": {  # Нечётная неделя = Знаменатель
        0: [  # Понедельник
            {"time": "08:30-10:00", "subject": "ВССТ: Вычислительные системы, сети, телекоммуникации",
             "teacher": "Махортов Владимир Денисович", "room": "2-03А", "type": "лабораторная"},
            {"time": "10:10-11:40", "subject": "физра", "teacher": "", "room": "", "type": ""},
            {"time": "12:00-13:30", "subject": "ППОД: Прикладные пакеты обработки данных",
             "teacher": "Горшкова Ольга Петровна", "room": "2-02А", "type": "лабораторная"},
            {"time": "13:40-15:10",
             "subject": "ССУКПО: Стандартизация, сертификация и управление качеством программного обеспечения",
             "teacher": "Шипилева Алла Владимировна", "room": "4-22Г", "type": "лекция"}
        ],
        1: [  # Вторник
            {"time": "08:30-10:00",
             "subject": "ПОЭИС: Предметно-ориентированные экономические информационные системы (1С)",
             "teacher": "Трухляева Анна Александровна", "room": "2-02А", "type": "лабораторная"},
            {"time": "10:10-11:40", "subject": "ПСЭД: Проектирование систем электронного документооборота",
             "teacher": "Баубель Юлия Игоревна", "room": "2-02А", "type": "лабораторная"},
            {"time": "12:00-13:30",
             "subject": "ПОЭИС: Предметно-ориентированные экономические информационные системы (1С)",
             "teacher": "Трухляева Анна Александровна", "room": "4-17В", "type": "лекция"}
        ],
        2: [  # Среда
            {"time": "15:20-16:50", "subject": "ОУД: Организация и управление данными",
             "teacher": "Шипилева Алла Владимировна", "room": "2-02А", "type": "практика"},
            {"time": "17:00-18:30",
             "subject": "ССУКПО: Стандартизация, сертификация и управление качеством программного обеспечения",
             "teacher": "Смирнова Елена Владимировна", "room": "2-03А", "type": "практика"}
        ],
        3: [  # Четверг
            {"time": "08:30-10:00", "subject": "ВССТ: Вычислительные системы, сети, телекоммуникации",
             "teacher": "Иванченко Геннадий Сергеевич", "room": "2-13В", "type": "лекция"},
            {"time": "10:10-11:40", "subject": "ПИС: Проектирование информационных систем",
             "teacher": "Лапина Марина Сергеевна", "room": "2-13В", "type": "лекция"},
            {"time": "12:00-13:30", "subject": "ПИС: Проектирование информационных систем",
             "teacher": "Калинина Вера Владимировна", "room": "2-02А", "type": "лабораторная"},
            {"time": "13:40-15:10", "subject": "АСБУ: Автоматизированные системы бухгалтерского учета (1С)",
             "teacher": "Баубель Юлия Игоревна", "room": "2-03А", "type": "лабораторная"}
        ],
        4: [],  # Пятница
        5: [],  # Суббота
        6: []  # Воскресенье
    }
}


# --- Вспомогательные функции для форматирования ---
def get_day_name(day_num: int) -> str:
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    return days[day_num]


def get_day_emoji(day_num: int) -> str:
    """Возвращает эмодзи для дня недели"""
    emojis = ["🔥", "🔥", "🔥", "🔥", "😴", "😴", "😴"]
    return emojis[day_num]


def format_lessons_simple(lessons: list) -> str:
    """Форматирует список пар в простой текст без рамок"""
    if not lessons:
        return "🎉 Выходной! Нет занятий. Отдыхайте! 🌟"

    result = ""
    for i, lesson in enumerate(lessons, 1):
        # Определяем эмодзи для типа занятия
        type_emoji = "📚" if lesson.get('type') == "лекция" else "💻" if lesson.get('type') == "практика" else "🔬"

        # Название предмета с номером
        result += f"\n*{i}. {lesson['subject']}*\n"

        # Время
        result += f"🕐 {lesson['time']}\n"

        # Преподаватель
        if lesson.get('teacher') and lesson['teacher'] != "":
            result += f"👨‍🏫 {lesson['teacher']}\n"

        # Аудитория
        if lesson.get('room') and lesson['room'] != "":
            result += f"🏛️ ауд. {lesson['room']}\n"

        # Тип занятия
        if lesson.get('type') and lesson['type'] != "":
            result += f"{type_emoji} {lesson['type'].capitalize()}\n"

        result += "─" * 30 + "\n"

    return result


def format_week_simple(parity: str) -> str:
    """Форматирует всю неделю в простой текст"""
    result = ""

    for day_num in range(7):
        day_name = get_day_name(day_num)
        day_emoji = get_day_emoji(day_num)
        lessons = SCHEDULE[parity].get(day_num, [])

        result += f"\n{day_emoji} *{day_name}*\n"

        if lessons:
            for lesson in lessons:
                result += f"   🕐 {lesson['time']} — {lesson['subject']}\n"
                if lesson.get('room') and lesson['room'] != "":
                    result += f"      🏛️ ауд. {lesson['room']}\n"
        else:
            result += "   🎉 Выходной\n"

        result += "\n"

    return result


def get_week_type_info(parity: str) -> tuple:
    """Возвращает информацию о типе недели"""
    if parity == "numerator":
        return "Числитель", "🧮", "чётная"
    else:
        return "Знаменатель", "📊", "нечётная"


def get_current_week_info() -> tuple:
    parity = get_week_parity()
    week_name, week_emoji, parity_ru = get_week_type_info(parity)
    return parity, week_name, week_emoji, parity_ru


def get_week_info_for_offset(weeks_offset: int) -> tuple:
    """Получить информацию о неделе со смещением"""
    target_date = date.today() + timedelta(weeks=weeks_offset)
    parity = get_week_parity_for_date(target_date)
    week_name, week_emoji, parity_ru = get_week_type_info(parity)

    if weeks_offset == 0:
        week_label = "Текущая"
    elif weeks_offset == 1:
        week_label = "Следующая"
    elif weeks_offset == -1:
        week_label = "Предыдущая"
    else:
        week_label = f"{weeks_offset:+d} неделя"

    return parity, week_name, week_emoji, parity_ru, week_label


# --- Клавиатуры ---
def get_main_keyboard():
    """Главная клавиатура с кнопками"""
    keyboard = [
        [
            InlineKeyboardButton("📅 Сегодня", callback_data="today"),
            InlineKeyboardButton("📆 Завтра", callback_data="tomorrow")
        ],
        [
            InlineKeyboardButton("📊 Текущая неделя", callback_data="week_current"),
            InlineKeyboardButton("⏩ Следующая неделя", callback_data="week_next")
        ],
        [
            InlineKeyboardButton("ℹ️ Инфо о неделе", callback_data="current_week"),
            InlineKeyboardButton("📖 Помощь", callback_data="help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_days_keyboard(weeks_offset: int = 0):
    """Клавиатура с днями недели для выбора"""
    keyboard = [
        [
            InlineKeyboardButton("🔥 ПН", callback_data=f"day_0_offset_{weeks_offset}"),
            InlineKeyboardButton("🔥 ВТ", callback_data=f"day_1_offset_{weeks_offset}"),
            InlineKeyboardButton("🔥 СР", callback_data=f"day_2_offset_{weeks_offset}")
        ],
        [
            InlineKeyboardButton("🔥 ЧТ", callback_data=f"day_3_offset_{weeks_offset}"),
            InlineKeyboardButton("😴 ПТ", callback_data=f"day_4_offset_{weeks_offset}"),
            InlineKeyboardButton("😴 СБ", callback_data=f"day_5_offset_{weeks_offset}")
        ],
        [
            InlineKeyboardButton("😴 ВС", callback_data=f"day_6_offset_{weeks_offset}")
        ],
        [
            InlineKeyboardButton("📊 Показать всю неделю", callback_data=f"week_offset_{weeks_offset}")
        ],
        [
            InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# --- Обработчики ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение с кнопками"""
    _, week_name, week_emoji, parity_ru = get_current_week_info()

    welcome_text = (
        f" *Бот-расписание* 🎓\n\n"
        f"📅 *Текущая неделя:* {week_name} {week_emoji} ({parity_ru})\n\n"
        f"👇 *Чтобы узнать расписание:*"
    )

    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "today":
        await show_today(query)
    elif data == "tomorrow":
        await show_tomorrow(query)
    elif data == "week_current":
        await show_week(query, weeks_offset=0)
    elif data == "week_next":
        await show_week(query, weeks_offset=1)
    elif data == "current_week":
        await show_current_week(query)
    elif data == "help":
        await show_help(query)
    elif data.startswith("day_"):
        parts = data.split("_")
        day_num = int(parts[1])
        offset = int(parts[3]) if len(parts) > 3 else 0
        await show_day(query, day_num, offset)
    elif data.startswith("week_offset_"):
        offset = int(data.split("_")[2])
        await show_week(query, offset)
    elif data == "back_to_main":
        await query.edit_message_text(
            "📌 *Главное меню*\n\nВыберите нужную опцию:",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )


async def show_today(query):
    """Показать расписание на сегодня"""
    today = datetime.now().weekday()
    parity, week_name, week_emoji, _ = get_current_week_info()
    day_name = get_day_name(today)
    day_emoji = get_day_emoji(today)
    lessons = SCHEDULE[parity].get(today, [])

    header = f"{day_emoji} *{day_name}* ({week_name} {week_emoji} неделя)\n"
    response = header + format_lessons_simple(lessons)

    await query.edit_message_text(
        response,
        parse_mode="Markdown",
        reply_markup=get_days_keyboard(weeks_offset=0)
    )


async def show_tomorrow(query):
    """Показать расписание на завтра"""
    tomorrow = (datetime.now().weekday() + 1) % 7
    parity, week_name, week_emoji, _ = get_current_week_info()
    day_name = get_day_name(tomorrow)
    day_emoji = get_day_emoji(tomorrow)
    lessons = SCHEDULE[parity].get(tomorrow, [])

    header = f"{day_emoji} *{day_name}* ({week_name} {week_emoji} неделя)\n"
    response = header + format_lessons_simple(lessons)

    await query.edit_message_text(
        response,
        parse_mode="Markdown",
        reply_markup=get_days_keyboard(weeks_offset=0)
    )


async def show_week(query, weeks_offset: int = 0):
    """Показать расписание на неделю"""
    parity, week_name, week_emoji, _, week_label = get_week_info_for_offset(weeks_offset)

    if weeks_offset == 0:
        title = f"📅 *Расписание* ({week_name} {week_emoji} неделя)"
    elif weeks_offset == 1:
        title = f"⏩ *Расписание на следующую неделю* ({week_name} {week_emoji})"
    else:
        title = f"📅 *Расписание* ({week_label}, {week_name} {week_emoji})"

    response = title + format_week_simple(parity)

    await query.edit_message_text(
        response,
        parse_mode="Markdown",
        reply_markup=get_days_keyboard(weeks_offset=weeks_offset)
    )


async def show_current_week(query):
    """Показать информацию о текущей неделе"""
    _, week_name, week_emoji, parity_ru = get_current_week_info()

    # Получаем информацию о следующей неделе
    _, next_week_name, next_week_emoji, next_parity_ru, _ = get_week_info_for_offset(1)

    await query.edit_message_text(
        f"📅 *Информация о неделях*\n\n"
        f"📌 *Текущая неделя:* {week_name} {week_emoji} ({parity_ru})\n"
        f"⏩ *Следующая неделя:* {next_week_name} {next_week_emoji} ({next_parity_ru})\n\n"
        f"📖 *Пояснение:*\n"
        f"• *Числитель* 🧮 — чётная неделя\n"
        f"• *Знаменатель* 📊 — нечётная неделя\n\n"
        f"🔄 Расписание автоматически меняется каждую неделю (отсчёт от 2 марта)",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )


async def show_help(query):
    """Показать помощь"""
    await query.edit_message_text(
        "📖 *Помощь по боту*\n\n"
        "*Доступные функции:*\n"
        "📅 *Сегодня* — расписание на текущий день\n"
        "📆 *Завтра* — расписание на следующий день\n"
        "📊 *Текущая неделя* — полное расписание на неделю\n"
        "⏩ *Следующая неделя* — расписание на следующую неделю\n"
        "ℹ️ *Инфо о неделе* — информация о четности недели\n\n"
        "*Советы:*\n"
        "• Нажимай на дни (ПН, ВТ...), чтобы посмотреть расписание на конкретный день\n"
        "• Можно смотреть расписание на следующую неделю заранее!\n\n"
        "*Система недель:*\n"
        "• Чётная неделя = *Числитель* 🧮\n"
        "• Нечётная неделя = *Знаменатель* 📊",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )


async def show_day(query, day_num: int, weeks_offset: int = 0):
    """Показать расписание на выбранный день"""
    parity, week_name, week_emoji, _, week_label = get_week_info_for_offset(weeks_offset)
    day_name = get_day_name(day_num)
    day_emoji = get_day_emoji(day_num)
    lessons = SCHEDULE[parity].get(day_num, [])

    if weeks_offset == 0:
        header = f"{day_emoji} *{day_name}* ({week_name} {week_emoji} неделя)\n"
    elif weeks_offset == 1:
        header = f"⏩ {day_emoji} *{day_name}* (следующая неделя, {week_name} {week_emoji})\n"
    else:
        header = f"{day_emoji} *{day_name}* ({week_label}, {week_name} {week_emoji})\n"

    response = header + format_lessons_simple(lessons)

    await query.edit_message_text(
        response,
        parse_mode="Markdown",
        reply_markup=get_days_keyboard(weeks_offset=weeks_offset)
    )


# --- Обработчики текстовых команд (для обратной совместимости) ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Помощь*\n\nНажмите /start чтобы открыть меню с кнопками",
        parse_mode="Markdown"
    )


async def schedule_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now().weekday()
    parity, week_name, week_emoji, _ = get_current_week_info()
    day_name = get_day_name(today)
    day_emoji = get_day_emoji(today)
    lessons = SCHEDULE[parity].get(today, [])

    header = f"{day_emoji} *{day_name}* ({week_name} {week_emoji} неделя)\n"
    response = header + format_lessons_simple(lessons)

    await update.message.reply_text(response, parse_mode="Markdown", reply_markup=get_days_keyboard(0))


async def schedule_tomorrow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tomorrow = (datetime.now().weekday() + 1) % 7
    parity, week_name, week_emoji, _ = get_current_week_info()
    day_name = get_day_name(tomorrow)
    day_emoji = get_day_emoji(tomorrow)
    lessons = SCHEDULE[parity].get(tomorrow, [])

    header = f"{day_emoji} *{day_name}* ({week_name} {week_emoji} неделя)\n"
    response = header + format_lessons_simple(lessons)

    await update.message.reply_text(response, parse_mode="Markdown", reply_markup=get_days_keyboard(0))


async def schedule_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parity, week_name, week_emoji, _ = get_current_week_info()
    title = f"📅 *Расписание* ({week_name} {week_emoji} неделя)\n"
    response = title + format_week_simple(parity)

    await update.message.reply_text(response, parse_mode="Markdown", reply_markup=get_days_keyboard(0))


async def schedule_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Укажите день недели.\nПримеры:\n/day понедельник\n/day пн\n/day 1",
            reply_markup=get_days_keyboard(0)
        )
        return

    day_input = context.args[0].lower()
    day_map = {
        "пн": 0, "понедельник": 0, "1": 0,
        "вт": 1, "вторник": 1, "2": 1,
        "ср": 2, "среда": 2, "3": 2,
        "чт": 3, "четверг": 3, "4": 3,
        "пт": 4, "пятница": 4, "5": 4,
        "сб": 5, "суббота": 5, "6": 5,
        "вс": 6, "воскресенье": 6, "7": 6
    }

    if day_input not in day_map:
        await update.message.reply_text(
            "Не понял день. Используйте: пн, вт, ср, чт, пт, сб, вс",
            reply_markup=get_days_keyboard(0)
        )
        return

    day_num = day_map[day_input]
    parity, week_name, week_emoji, _ = get_current_week_info()
    day_name = get_day_name(day_num)
    day_emoji = get_day_emoji(day_num)
    lessons = SCHEDULE[parity].get(day_num, [])

    header = f"{day_emoji} *{day_name}* ({week_name} {week_emoji} неделя)\n"
    response = header + format_lessons_simple(lessons)

    await update.message.reply_text(response, parse_mode="Markdown", reply_markup=get_days_keyboard(0))


async def current_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _, week_name, week_emoji, parity_ru = get_current_week_info()
    await update.message.reply_text(
        f"📅 *Текущая неделя:* {week_name} {week_emoji} ({parity_ru})\n\n"
        f"🔄 Расписание автоматически меняется каждую неделю.",
        parse_mode="Markdown",
        reply_markup=get_days_keyboard(0)
    )


# --- Главная функция ---
async def main():
    app = Application.builder().token(BOT_TOKEN).updater(None).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("today", schedule_today))
    app.add_handler(CommandHandler("tomorrow", schedule_tomorrow))
    app.add_handler(CommandHandler("week", schedule_week))
    app.add_handler(CommandHandler("day", schedule_day))
    app.add_handler(CommandHandler("current_week", current_week))
    app.add_handler(CallbackQueryHandler(handle_callback))

    webhook_url = f"{RENDER_EXTERNAL_URL}/telegram"
    await app.bot.set_webhook(url=webhook_url, allowed_updates=Update.ALL_TYPES)
    logging.info(f"Webhook установлен на: {webhook_url}")

    async def telegram_webhook(request: Request) -> Response:
        await app.update_queue.put(Update.de_json(await request.json(), app.bot))
        return Response()

    async def healthcheck(request: Request) -> PlainTextResponse:
        return PlainTextResponse("OK")

    starlette_app = Starlette(routes=[
        Route("/telegram", telegram_webhook, methods=["POST"]),
        Route("/healthcheck", healthcheck, methods=["GET"]),
    ])

    import uvicorn
    server = uvicorn.Server(uvicorn.Config(starlette_app, host="0.0.0.0", port=PORT, log_level="info"))

    async with app:
        await app.start()
        await server.serve()
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())