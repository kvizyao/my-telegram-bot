import os
import asyncio
import logging
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- Настройка логирования, чтобы видеть, что происходит ---
logging.basicConfig(level=logging.INFO)

# --- Переменные окружения (их мы зададим на сайте Render) ---
# Токен вашего бота от @BotFather
BOT_TOKEN = os.environ["BOT_TOKEN"]
# URL, который выдаст Render (например, https://mybot.onrender.com)
# Render создает эту переменную автоматически!
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")
# Порт, который Render выделит для нашего сервера
PORT = int(os.getenv("PORT", 8000))

# --- Обработчик команды /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Бот отвечает на команду /start
    await update.message.reply_text("Привет! Я работаю 24/7 на Render.com! 🚀")

# --- Главная функция, которая запускает бота и веб-сервер ---
async def main():
    # 1. Создаем приложение бота (Application)
    app = Application.builder().token(BOT_TOKEN).updater(None).build()
    # 2. Добавляем в него наш обработчик команды
    app.add_handler(CommandHandler("start", start))

    # 3. Устанавливаем Webhook. Это говорит Telegram: "Присылай сообщения по этому адресу"
    webhook_url = f"{RENDER_EXTERNAL_URL}/telegram"
    await app.bot.set_webhook(url=webhook_url, allowed_updates=Update.ALL_TYPES)
    logging.info(f"Webhook установлен на: {webhook_url}")

    # 4. Создаем небольшой веб-сервер на Starlette для приема сообщений от Telegram
    #    и для проверки здоровья (healthcheck), которую требует Render.
    async def telegram_webhook(request: Request) -> Response:
        # Получаем JSON от Telegram и кладем его в очередь обновлений бота
        await app.update_queue.put(Update.de_json(await request.json(), app.bot))
        return Response()

    async def healthcheck(request: Request) -> PlainTextResponse:
        # Этот эндпоинт Render пингует, чтобы убедиться, что наш сервис жив.
        return PlainTextResponse("OK")

    starlette_app = Starlette(routes=[
        Route("/telegram", telegram_webhook, methods=["POST"]),
        Route("/healthcheck", healthcheck, methods=["GET"]),
    ])

    # 5. Запускаем веб-сервер параллельно с ботом
    import uvicorn
    server = uvicorn.Server(uvicorn.Config(starlette_app, host="0.0.0.0", port=PORT, log_level="info"))

    # Запускаем оба приложения (бот и веб-сервер) в асинхронном режиме
    async with app:
        await app.start()
        await server.serve()
        await app.stop()

# --- Точка входа. Запускаем нашу асинхронную main-функцию ---
if __name__ == "__main__":
    asyncio.run(main())