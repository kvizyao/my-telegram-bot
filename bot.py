import os
import asyncio
import logging
import io
from datetime import datetime, date, timedelta
from PIL import Image, ImageDraw, ImageFont
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

# ==================== ФУНКЦИИ ДЛЯ ГЕНЕРАЦИИ ИЗОБРАЖЕНИЙ ====================

# Цветовая схема
COLORS = {
    "bg": (248, 250, 252),  # светло-серый фон
    "card_bg": (255, 255, 255),  # белый фон карточки
    "header": (79, 129, 189),  # синий для заголовков
    "accent": (100, 150, 200),  # акцентный цвет
    "text": (30, 41, 59),  # тёмно-серый текст
    "text_light": (100, 116, 139),  # светлый текст
    "border": (226, 232, 240),  # цвет границы
    "time": (59, 130, 246),  # синий для времени
    "teacher": (139, 92, 246),  # фиолетовый для преподавателя
    "room": (236, 72, 153),  # розовый для аудитории
}

# Типы занятий с цветами
LESSON_TYPES = {
    "лекция": {"emoji": "📚", "color": (59, 130, 246)},
    "практика": {"emoji": "💻", "color": (16, 185, 129)},
    "лабораторная": {"emoji": "🔬", "color": (245, 158, 11)},
    "": {"emoji": "📖", "color": (100, 116, 139)}
}


def get_font(size, bold=False):
    """Пытается загрузить шрифт, если нет — использует дефолтный"""
    font_paths = [
        # Windows
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        # macOS
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
    ]

    for path in font_paths:
        try:
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
        except:
            continue

    # Если шрифтов нет — используем дефолтный
    return ImageFont.load_default()


def create_schedule_image(day_name: str, week_info: str, lessons: list, width: int = 800) -> bytes:
    """
    Создаёт изображение с расписанием на день
    Возвращает bytes для отправки в Telegram
    """
    # Вычисляем высоту в зависимости от количества пар
    card_height = 130  # высота одной карточки
    header_height = 120
    footer_height = 40
    total_height = header_height + len(lessons) * card_height + footer_height

    # Если нет занятий — компактное изображение
    if not lessons:
        total_height = 200

    # Создаём изображение
    img = Image.new('RGB', (width, total_height), color=COLORS["bg"])
    draw = ImageDraw.Draw(img)

    # Загружаем шрифты
    font_title = get_font(28, bold=True)
    font_subtitle = get_font(18)
    font_lesson_title = get_font(20, bold=True)
    font_normal = get_font(16)
    font_small = get_font(14)

    y_offset = 20

    # --- Шапка ---
    # Рисуем декоративную полоску
    draw.rectangle([0, 0, width, 8], fill=COLORS["header"])

    # День недели
    draw.text((30, y_offset), day_name, fill=COLORS["text"], font=font_title)
    y_offset += 45

    # Информация о неделе
    draw.text((30, y_offset), week_info, fill=COLORS["accent"], font=font_subtitle)
    y_offset += 35

    # Разделитель
    draw.line([(20, y_offset), (width - 20, y_offset)], fill=COLORS["border"], width=2)
    y_offset += 25

    # --- Карточки пар ---
    if not lessons:
        # Если выходной
        draw.text((width // 2 - 100, y_offset + 40), "🎉 ВЫХОДНОЙ! 🎉",
                  fill=COLORS["header"], font=get_font(24, bold=True))
        draw.text((width // 2 - 80, y_offset + 90), "Нет занятий. Отдыхайте! 🌟",
                  fill=COLORS["text_light"], font=font_normal)
    else:
        for i, lesson in enumerate(lessons):
            # Фон карточки
            card_x = 20
            card_y = y_offset
            card_w = width - 40
            card_h = card_height - 10

            # Рисуем белую карточку с тенью (простая имитация)
            draw.rectangle([card_x, card_y, card_x + card_w, card_y + card_h],
                           fill=COLORS["card_bg"], outline=COLORS["border"], width=1)

            # Левая цветная полоска (тип занятия)
            lesson_type = lesson.get('type', '')
            type_color = LESSON_TYPES.get(lesson_type, LESSON_TYPES[""])["color"]
            draw.rectangle([card_x, card_y, card_x + 8, card_y + card_h], fill=type_color)

            # Номер пары
            draw.text((card_x + 20, card_y + 12), f"{i + 1}",
                      fill=COLORS["header"], font=font_lesson_title)

            # Время
            time_text = f"🕐 {lesson['time']}"
            draw.text((card_x + 60, card_y + 12), time_text,
                      fill=COLORS["time"], font=font_normal)

            # Название предмета
            subject = lesson['subject']
            if len(subject) > 45:
                subject = subject[:42] + "..."
            draw.text((card_x + 20, card_y + 42), subject,
                      fill=COLORS["text"], font=font_lesson_title)

            # Преподаватель
            teacher = lesson.get('teacher', '')
            if teacher and teacher != "":
                teacher_text = f"👨‍🏫 {teacher}"
                if len(teacher_text) > 55:
                    teacher_text = teacher_text[:52] + "..."
                draw.text((card_x + 20, card_y + 72), teacher_text,
                          fill=COLORS["teacher"], font=font_normal)

            # Аудитория
            room = lesson.get('room', '')
            if room and room != "":
                room_text = f"🏛️ ауд. {room}"
                draw.text((card_x + 20, card_y + 97), room_text,
                          fill=COLORS["room"], font=font_normal)

            # Тип занятия
            type_emoji = LESSON_TYPES.get(lesson_type, LESSON_TYPES[""])["emoji"]
            type_text = f"{type_emoji} {lesson_type.capitalize()}" if lesson_type else "📖 Занятие"
            draw.text((card_x + card_w - 100, card_y + 12), type_text,
                      fill=type_color, font=font_small)

            y_offset += card_h - 5

    # --- Подвал ---
    y_offset += 10
    draw.line([(20, y_offset), (width - 20, y_offset)], fill=COLORS["border"], width=1)
    y_offset += 15
    draw.text((30, y_offset), "📅 Бот-расписание | Актуально на текущую неделю",
              fill=COLORS["text_light"], font=get_font(12))

    # Сохраняем в bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)

    return img_bytes.getvalue()


def create_week_image(parity: str, week_name: str, week_emoji: str, width: int = 800) -> bytes:
    """
    Создаёт изображение с расписанием на всю неделю
    """
    from SCHEDULE import SCHEDULE  # нужно импортировать

    # Вычисляем высоту
    rows = 0
    for day_num in range(7):
        lessons = SCHEDULE[parity].get(day_num, [])
        rows += max(1, len(lessons))

    row_height = 45
    header_height = 120
    footer_height = 40
    total_height = header_height + rows * row_height + footer_height

    img = Image.new('RGB', (width, total_height), color=COLORS["bg"])
    draw = ImageDraw.Draw(img)

    font_title = get_font(28, bold=True)
    font_subtitle = get_font(18)
    font_day = get_font(18, bold=True)
    font_normal = get_font(14)

    y_offset = 20

    # Шапка
    draw.rectangle([0, 0, width, 8], fill=COLORS["header"])
    draw.text((30, y_offset), f"📅 Расписание на неделю", fill=COLORS["text"], font=font_title)
    y_offset += 45
    draw.text((30, y_offset), f"{week_name} {week_emoji} неделя", fill=COLORS["accent"], font=font_subtitle)
    y_offset += 40
    draw.line([(20, y_offset), (width - 20, y_offset)], fill=COLORS["border"], width=2)
    y_offset += 15

    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    day_emojis = ["🌙", "🔥", "⚡", "💪", "🎯", "🎉", "😴"]

    for day_num in range(7):
        lessons = SCHEDULE[parity].get(day_num, [])
        day_name = f"{day_emojis[day_num]} {days[day_num]}"

        draw.text((20, y_offset), day_name, fill=COLORS["header"], font=font_day)
        y_offset += 28

        if lessons:
            for lesson in lessons:
                lesson_text = f"  • {lesson['time']} — {lesson['subject']}"
                draw.text((30, y_offset), lesson_text, fill=COLORS["text"], font=font_normal)
                y_offset += 25
        else:
            draw.text((30, y_offset), "  • Выходной 🎉", fill=COLORS["text_light"], font=font_normal)
            y_offset += 25

        y_offset += 5

    # Подвал
    draw.line([(20, y_offset), (width - 20, y_offset)], fill=COLORS["border"], width=1)
    y_offset += 15
    draw.text((30, y_offset), "📅 Бот-расписание | Актуально на текущую неделю",
              fill=COLORS["text_light"], font=get_font(12))

    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)

    return img_bytes.getvalue()


# ==================== ДАННЫЕ РАСПИСАНИЯ ====================

def get_week_parity_for_date(target_date: date = None) -> str:
    """Определяет четность недели"""
    if target_date is None:
        target_date = date.today()

    start_date = date(target_date.year, 3, 2)
    if target_date < start_date:
        start_date = date(target_date.year - 1, 3, 2)

    delta = (target_date - start_date).days
    week_number = delta // 7

    return "numerator" if week_number % 2 == 0 else "denominator"


def get_week_parity() -> str:
    return get_week_parity_for_date(date.today())


# Ваше расписание (SCHEDULE) остаётся без изменений
SCHEDULE = {
    "numerator": {
        0: [
            {"time": "08:30-10:00", "subject": "АСБУ: Автоматизированные системы бухгалтерского учета (1С)",
             "teacher": "Исаева Ириада Евгеньевна", "room": "4-06А", "type": "лекция"},
            {"time": "10:10-11:40", "subject": "физра", "teacher": "", "room": "", "type": ""},
            {"time": "12:00-13:30", "subject": "ППОД: Прикладные пакеты обработки данных",
             "teacher": "Горшкова Ольга Петровна", "room": "2-02А", "type": "лабораторная"},
            {"time": "13:40-15:10", "subject": "ППОД: Прикладные пакеты обработки данных",
             "teacher": "Смирнова Елена Владимировна", "room": "4-22Г", "type": "лекция"}
        ],
        1: [
            {"time": "08:30-10:00",
             "subject": "ПОЭИС: Предметно-ориентированные экономические информационные системы (1С)",
             "teacher": "Трухляева Анна Александровна", "room": "2-02А", "type": "лабораторная"},
            {"time": "10:10-11:40", "subject": "ПСЭД: Проектирование систем электронного документооборота",
             "teacher": "Баубель Юлия Игоревна", "room": "2-02А", "type": "лабораторная"},
            {"time": "12:00-13:30", "subject": "ПСЭД: Проектирование систем электронного документооборота",
             "teacher": "Трухляева Анна Александровна", "room": "4-17В", "type": "лекция"}
        ],
        2: [
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
        3: [
            {"time": "08:30-10:00", "subject": "ВССТ: Вычислительные системы, сети, телекоммуникации",
             "teacher": "Иванченко Геннадий Сергеевич", "room": "2-13В", "type": "лекция"},
            {"time": "10:10-11:40", "subject": "ПИС: Проектирование информационных систем",
             "teacher": "Лапина Марина Сергеевна", "room": "2-13В", "type": "лекция"},
            {"time": "12:00-13:30", "subject": "ПИС: Проектирование информационных систем",
             "teacher": "Калинина Вера Владимировна", "room": "2-02А", "type": "лабораторная"},
            {"time": "13:40-15:10", "subject": "АСБУ: Автоматизированные системы бухгалтерского учета (1С)",
             "teacher": "Баубель Юлия Игоревна", "room": "2-03А", "type": "лабораторная"}
        ],
        4: [],
        5: [],
        6: []
    },
    "denominator": {
        0: [
            {"time": "08:30-10:00", "subject": "ВССТ: Вычислительные системы, сети, телекоммуникации",
             "teacher": "Махортов Владимир Денисович", "room": "2-03А", "type": "лабораторная"},
            {"time": "10:10-11:40", "subject": "физра", "teacher": "", "room": "", "type": ""},
            {"time": "12:00-13:30", "subject": "ППОД: Прикладные пакеты обработки данных",
             "teacher": "Горшкова Ольга Петровна", "room": "2-02А", "type": "лабораторная"},
            {"time": "13:40-15:10",
             "subject": "ССУКПО: Стандартизация, сертификация и управление качеством программного обеспечения",
             "teacher": "Шипилева Алла Владимировна", "room": "4-22Г", "type": "лекция"}
        ],
        1: [
            {"time": "08:30-10:00",
             "subject": "ПОЭИС: Предметно-ориентированные экономические информационные системы (1С)",
             "teacher": "Трухляева Анна Александровна", "room": "2-02А", "type": "лабораторная"},
            {"time": "10:10-11:40", "subject": "ПСЭД: Проектирование систем электронного документооборота",
             "teacher": "Баубель Юлия Игоревна", "room": "2-02А", "type": "лабораторная"},
            {"time": "12:00-13:30",
             "subject": "ПОЭИС: Предметно-ориентированные экономические информационные системы (1С)",
             "teacher": "Трухляева Анна Александровна", "room": "4-17В", "type": "лекция"}
        ],
        2: [
            {"time": "15:20-16:50", "subject": "ОУД: Организация и управление данными",
             "teacher": "Шипилева Алла Владимировна", "room": "2-02А", "type": "практика"},
            {"time": "17:00-18:30",
             "subject": "ССУКПО: Стандартизация, сертификация и управление качеством программного обеспечения",
             "teacher": "Смирнова Елена Владимировна", "room": "2-03А", "type": "практика"}
        ],
        3: [
            {"time": "08:30-10:00", "subject": "ВССТ: Вычислительные системы, сети, телекоммуникации",
             "teacher": "Иванченко Геннадий Сергеевич", "room": "2-13В", "type": "лекция"},
            {"time": "10:10-11:40", "subject": "ПИС: Проектирование информационных систем",
             "teacher": "Лапина Марина Сергеевна", "room": "2-13В", "type": "лекция"},
            {"time": "12:00-13:30", "subject": "ПИС: Проектирование информационных систем",
             "teacher": "Калинина Вера Владимировна", "room": "2-02А", "type": "лабораторная"},
            {"time": "13:40-15:10", "subject": "АСБУ: Автоматизированные системы бухгалтерского учета (1С)",
             "teacher": "Баубель Юлия Игоревна", "room": "2-03А", "type": "лабораторная"}
        ],
        4: [],
        5: [],
        6: []
    }
}


# --- Вспомогательные функции ---
def get_day_name(day_num: int) -> str:
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    return days[day_num]


def get_current_week_info() -> tuple:
    parity = get_week_parity()
    if parity == "numerator":
        week_name = "Числитель"
        week_emoji = "🧮"
    else:
        week_name = "Знаменатель"
        week_emoji = "📊"
    return parity, week_name, week_emoji


# --- Обработчики команд (отправляют изображения) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _, week_name, week_emoji = get_current_week_info()

    await update.message.reply_text(
        f"🎓 *Привет! Я бот-расписание* 🎓\n\n"
        f"📅 *Текущая неделя:* {week_name} {week_emoji}\n\n"
        f"👇 *Нажми на кнопку ниже, чтобы узнать расписание:*",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )


async def show_today_callback(query):
    """Отправить изображение с расписанием на сегодня"""
    today = datetime.now().weekday()
    parity, week_name, week_emoji = get_current_week_info()
    day_name = get_day_name(today)
    lessons = SCHEDULE[parity].get(today, [])

    week_info = f"{week_name} {week_emoji} неделя"
    image_bytes = create_schedule_image(day_name, week_info, lessons)

    await query.message.reply_photo(
        photo=image_bytes,
        caption=f"📅 {day_name} | {week_info}",
        reply_markup=get_days_keyboard(0)
    )
    await query.delete_message()  # Удаляем сообщение с кнопкой, чтобы не дублировалось


# Остальные обработчики аналогично переписываются на отправку изображений...

# --- Клавиатуры (остаются без изменений) ---
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("📅 Сегодня", callback_data="today")],
        [InlineKeyboardButton("📆 Завтра", callback_data="tomorrow")],
        [InlineKeyboardButton("📊 Текущая неделя", callback_data="week_current")],
        [InlineKeyboardButton("⏩ Следующая неделя", callback_data="week_next")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_days_keyboard(weeks_offset: int = 0):
    keyboard = [
        [InlineKeyboardButton("🌙 ПН", callback_data=f"day_0_offset_{weeks_offset}"),
         InlineKeyboardButton("🔥 ВТ", callback_data=f"day_1_offset_{weeks_offset}"),
         InlineKeyboardButton("⚡ СР", callback_data=f"day_2_offset_{weeks_offset}")],
        [InlineKeyboardButton("💪 ЧТ", callback_data=f"day_3_offset_{weeks_offset}"),
         InlineKeyboardButton("🎯 ПТ", callback_data=f"day_4_offset_{weeks_offset}"),
         InlineKeyboardButton("🎉 СБ", callback_data=f"day_5_offset_{weeks_offset}")],
        [InlineKeyboardButton("😴 ВС", callback_data=f"day_6_offset_{weeks_offset}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


# --- Обработчики ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "today":
        await show_today_callback(query)
    elif data == "back_to_main":
        await query.edit_message_text(
            "📌 *Главное меню*\n\nВыберите нужную опцию:",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )


# ... остальные обработчики аналогично

# --- Главная функция ---
async def main():
    app = Application.builder().token(BOT_TOKEN).updater(None).build()

    app.add_handler(CommandHandler("start", start))
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