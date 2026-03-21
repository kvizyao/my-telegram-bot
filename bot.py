import os
import asyncio
import logging
from datetime import datetime, date
from calendar import monthcalendar
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

# Функция для определения четности недели
def get_week_parity() -> str:
    """
    Определяет четность текущей недели.
    За основу берется первая неделя сентября (или любая другая отправная точка)
    """
    today = date.today()
    # Берем начало учебного года (1 сентября)
    start_date = date(today.year, 3, 2)

    # Если сегодня до 1 сентября, берем прошлый год
    if today < start_date:
        start_date = date(today.year - 1, 3, 2)

    # Вычисляем разницу в днях
    delta = (today - start_date).days
    # Определяем номер недели от начала учебного года
    week_number = delta // 7

    # Четная или нечетная неделя
    return "even" if week_number % 2 == 0 else "odd"


# Структура расписания:
# SCHEDULE[четность_недели][день_недели] = список пар
# день_недели: 0=пн, 1=вт, 2=ср, 3=чт, 4=пт, 5=сб, 6=вс

SCHEDULE = {
    "odd": {  # Нечетная неделя
        0: [  # Понедельник
            {
                "time": "08:30-10:00",
                "subject": "АСБУ: Автоматизированные системы бухгалтерского учета (1С)",
                "teacher": "Исаева Ириада Евгеньевна",
                "room": "4-06А",
                "type": "лекция"
            },
            {
                "time": "10:10-11:40",
                "subject": "физра",
                "teacher": "",
                "room": "",
                "type": ""
            },
            {
                "time": "12:00-13:30",
                "subject": "ППОД: Прикладные пакеты обработки данных",
                "teacher": "Горшкова Ольга Петровна",
                "room": "2-02А",
                "type": "лабораторная"
            },
            {
                "time": "13:40-15:10",
                "subject": "ППОД: Прикладные пакеты обработки данных",
                "teacher": "Смирнова Елена Владимировна",
                "room": "4-22Г",
                "type": "лекция"
            }
        ],
        1: [  # Вторник
            {
                "time": "08:30-10:00",
                "subject": "ПОЭИС: Предметно-ориентированные экономические информационные системы (1С)",
                "teacher": "Трухляева Анна Александровна",
                "room": "2-02А",
                "type": "лабораторная"
            },
            {
                "time": "10:10-11:40",
                "subject": "ПСЭД: Проектирование систем электронного документооборота",
                "teacher": "Баубель Юлия Игоревна",
                "room": "2-02А",
                "type": "лабораторная"
            },
            {
                "time": "12:00-13:30",
                "subject": "ПСЭД: Проектирование систем электронного документооборота",
                "teacher": "Трухляева Анна Александровна",
                "room": "4-17В",
                "type": "лекция"
            }
        ],
        2: [  # Среда
            {
                "time": "12:00-13:30",
                "subject": "ВССТ: Вычислительные системы, сети, телекоммуникации",
                "teacher": "Горте Иван Александрович",
                "room": "2-02А",
                "type": "лабораторная"
            },
            {
                "time": "13:40-15:10",
                "subject": "ОУД: Организация и управление данными",
                "teacher": "Шипилева Алла Владимировна",
                "room": "4-22Г",
                "type": "лекция"
            },
            {
                "time": "15:20-16:50",
                "subject": "ОУД: Организация и управление данными",
                "teacher": "Шипилева Алла Владимировна",
                "room": "2-02А",
                "type": "практика"
            },
            {
                "time": "17:00-18:30",
                "subject": "ССУКПО: Стандартизация, сертификация и управление качеством программного обеспечения",
                "teacher": "Смирнова Елена Владимировна",
                "room": "2-03А",
                "type": "практика"
            }
        ],
        3: [  # Четверг
            {
                "time": "08:30-10:00",
                "subject": "ВССТ: Вычислительные системы, сети, телекоммуникации",
                "teacher": "Иванченко Геннадий Сергеевич",
                "room": "2-13В",
                "type": "лекция"
            },
            {
                "time": "10:10-11:40",
                "subject": "ПИС: Проектирование информационных систем",
                "teacher": "Лапина Марина Сергеевна",
                "room": "2-13В",
                "type": "лекция"
            },
            {
                "time": "12:00-13:30",
                "subject": "ПИС: Проектирование информационных систем",
                "teacher": "Калинина Вера Владимировна",
                "room": "2-02А",
                "type": "лабораторная"
            },
            {
                "time": "13:40-15:10",
                "subject": "АСБУ: Автоматизированные системы бухгалтерского учета (1С)",
                "teacher": "Баубель Юлия Игоревна",
                "room": "2-03А",
                "type": "лабораторная"
            }
        ],
        4: [],
        5: [],
        6: []  # Воскресенье - выходной
    },

    "even": {  # Четная неделя (отличается расписанием)
        0: [  # Понедельник
            {
                "time": "08:30-10:00",
                "subject": "ВССТ: Вычислительные системы, сети, телекоммуникации",
                "teacher": "Махортов Владимир Денисович",
                "room": "2-03А",
                "type": "лабораторная"
            },
            {
                "time": "10:10-11:40",
                "subject": "физра",
                "teacher": "",
                "room": "",
                "type": ""
            },
            {
                "time": "12:00-13:30",
                "subject": "ППОД: Прикладные пакеты обработки данных",
                "teacher": "Горшкова Ольга Петровна",
                "room": "2-02А",
                "type": "лабораторная"
            },
            {
                "time": "13:40-15:10",
                "subject": "ССУКПО: Стаднартизация, сертификация и управление качеством программного обеспечения",
                "teacher": "Шипилева Алла Владимировна",
                "room": "4-22Г",
                "type": "лекция"
            }
        ],
        1: [  # Вторник
            {
                "time": "08:30-10:00",
                "subject": "ПОЭИС: Предметно-ориентированные экономические информационные системы (1С)",
                "teacher": "Трухляева Анна Александровна",
                "room": "2-02А",
                "type": "лабораторная"
            },
            {
                "time": "10:10-11:40",
                "subject": "ПСЭД: Проектирование систем электронного документооборота",
                "teacher": "Баубель Юлия Игоревна",
                "room": "2-02А",
                "type": "лабораторная"
            },
            {
                "time": "12:00-13:30",
                "subject": "ПОЭИС: Предметно-ориентированные экономические информационные системы (1С)",
                "teacher": "Трухляева Анна Александровна",
                "room": "4-17В",
                "type": "лекция"
            }
        ],
        2: [  # Среда
            {
                "time": "15:20-16:50",
                "subject": "ОУД: Организация и управление данными",
                "teacher": "Шипилева Алла Владимировна",
                "room": "2-02А",
                "type": "практика"
            },
            {
                "time": "17:00-18:30",
                "subject": "ССУКПО: Стандартизация, сертификация и управление качеством программного обеспечения",
                "teacher": "Смирнова Елена Владимировна",
                "room": "2-03А",
                "type": "практика"
            }
        ],
        3: [  # Четверг
            {
                "time": "08:30-10:00",
                "subject": "ВССТ: Вычислительные системы, сети, телекоммуникации",
                "teacher": "Иванченко Геннадий Сергеевич",
                "room": "2-13В",
                "type": "лекция"
            },
            {
                "time": "10:10-11:40",
                "subject": "ПИС: Проектирование информационных систем",
                "teacher": "Лапина Марина Сергеевна",
                "room": "2-13В",
                "type": "лекция"
            },
            {
                "time": "12:00-13:30",
                "subject": "ПИС: Проектирование информационных систем",
                "teacher": "Калинина Вера Владимировна",
                "room": "2-02А",
                "type": "лабораторная"
            },
            {
                "time": "13:40-15:10",
                "subject": "АСБУ: Автоматизированные системы бухгалтерского учета (1С)",
                "teacher": "Баубель Юлия Игоревна",
                "room": "2-03А",
                "type": "лабораторная"
            }
        ],
        4: [],
        5: [],
        6: []
    }
}


# --- Вспомогательные функции ---
def get_day_name(day_num: int) -> str:
    """Получить название дня по номеру"""
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    return days[day_num]


def format_lessons(lessons: list) -> str:
    """Форматирует список пар в красивую строку"""
    if not lessons:
        return "Выходной 🎉\n\nНет занятий"

    result = ""
    for i, lesson in enumerate(lessons, 1):
        result += f"📚 *{i}. {lesson['subject']}*\n"
        result += f"   🕐 {lesson['time']}\n"
        result += f"   👨‍🏫 {lesson['teacher']}\n"
        result += f"   🏛️ ауд. {lesson['room']}\n"
        result += f"   📖 {get_lesson_type_emoji(lesson['type'])} {lesson['type'].capitalize()}\n\n"
    return result


def get_lesson_type_emoji(lesson_type: str) -> str:
    """Возвращает эмодзи для типа занятия"""
    types = {
        "лекция": "📝",
        "практика": "💻",
        "лабораторная": "🔬"
    }
    return types.get(lesson_type, "📚")


def get_current_week_info() -> tuple:
    """Возвращает информацию о текущей неделе"""
    parity = get_week_parity()
    week_type = "нечетная" if parity == "odd" else "четная"
    week_emoji = "➗" if parity == "odd" else "✖️"
    return parity, week_type, week_emoji


# --- Обработчики команд ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение"""
    _, week_type, week_emoji = get_current_week_info()

    await update.message.reply_text(
        f"🎓 *Привет! Я бот-расписание* 🎓\n\n"
        f"📅 *Текущая неделя:* {week_type} {week_emoji}\n\n"
        f"*Доступные команды:*\n"
        f"/today - расписание на сегодня\n"
        f"/tomorrow - расписание на завтра\n"
        f"/week - расписание на всю неделю\n"
        f"/day [день] - расписание на конкретный день\n"
        f"/current_week - показать текущую неделю\n"
        f"/help - помощь\n\n"
        f"*Примеры:*\n"
        f"/day понедельник\n"
        f"/day пн\n"
        f"/day 1",
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь"""
    await update.message.reply_text(
        "📖 *Помощь по командам*\n\n"
        "/today - расписание на сегодня\n"
        "/tomorrow - расписание на завтра\n"
        "/week - полное расписание на неделю\n"
        "/day [день] - расписание на указанный день\n"
        "/current_week - какая сейчас неделя (четная/нечетная)\n"
        "/help - это сообщение\n\n"
        "*Дни недели:*\n"
        "пн, понедельник, 1\n"
        "вт, вторник, 2\n"
        "ср, среда, 3\n"
        "чт, четверг, 4\n"
        "пт, пятница, 5\n"
        "сб, суббота, 6\n"
        "вс, воскресенье, 7",
        parse_mode="Markdown"
    )


async def schedule_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Расписание на сегодня"""
    today = datetime.now().weekday()
    parity, week_type, _ = get_current_week_info()
    day_name = get_day_name(today)
    lessons = SCHEDULE[parity].get(today, [])

    response = f"📅 *{day_name}* ({week_type} неделя)\n\n"
    response += format_lessons(lessons)

    await update.message.reply_text(response, parse_mode="Markdown")


async def schedule_tomorrow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Расписание на завтра"""
    tomorrow = (datetime.now().weekday() + 1) % 7
    parity, week_type, _ = get_current_week_info()
    day_name = get_day_name(tomorrow)
    lessons = SCHEDULE[parity].get(tomorrow, [])

    response = f"📅 *{day_name}* ({week_type} неделя)\n\n"
    response += format_lessons(lessons)

    await update.message.reply_text(response, parse_mode="Markdown")


async def schedule_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Расписание на всю неделю"""
    parity, week_type, week_emoji = get_current_week_info()
    response = f"📅 *Расписание на неделю* ({week_type} {week_emoji})\n\n"

    for day_num in range(7):
        day_name = get_day_name(day_num)
        lessons = SCHEDULE[parity].get(day_num, [])

        response += f"*{day_name}*\n"
        if lessons:
            for lesson in lessons:
                response += f"  • {lesson['time']} - {lesson['subject']} ({lesson['room']})\n"
            response += "\n"
        else:
            response += "  • Выходной\n\n"

    await update.message.reply_text(response, parse_mode="Markdown")


async def schedule_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Расписание на конкретный день"""
    if not context.args:
        await update.message.reply_text(
            "Укажите день недели.\n"
            "Примеры:\n/day понедельник\n/day пн\n/day 1"
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
            "Не понял день. Используйте:\n"
            "пн, вт, ср, чт, пт, сб, вс"
        )
        return

    day_num = day_map[day_input]
    parity, week_type, _ = get_current_week_info()
    day_name = get_day_name(day_num)
    lessons = SCHEDULE[parity].get(day_num, [])

    response = f"📅 *{day_name}* ({week_type} неделя)\n\n"
    response += format_lessons(lessons)

    await update.message.reply_text(response, parse_mode="Markdown")


async def current_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать текущую неделю"""
    _, week_type, week_emoji = get_current_week_info()
    await update.message.reply_text(
        f"📅 *Текущая неделя:* {week_type} {week_emoji}\n\n"
        f"Расписание автоматически меняется каждую неделю.",
        parse_mode="Markdown"
    )


# --- Главная функция ---
async def main():
    app = Application.builder().token(BOT_TOKEN).updater(None).build()

    # Регистрируем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("today", schedule_today))
    app.add_handler(CommandHandler("tomorrow", schedule_tomorrow))
    app.add_handler(CommandHandler("week", schedule_week))
    app.add_handler(CommandHandler("day", schedule_day))
    app.add_handler(CommandHandler("current_week", current_week))

    # Webhook настройки
    webhook_url = f"{RENDER_EXTERNAL_URL}/telegram"
    await app.bot.set_webhook(url=webhook_url, allowed_updates=Update.ALL_TYPES)
    logging.info(f"Webhook установлен на: {webhook_url}")

    # Веб-сервер
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