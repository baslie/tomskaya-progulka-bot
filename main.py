# main.py
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from app.bot import telegram_app
from app.handlers import setup_handlers
from app.config import WEBHOOK_URL

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Инициализация телеграм-бота, установка обработчиков и регистрация вебхука.
    await telegram_app.initialize()
    setup_handlers()
    await telegram_app.bot.set_webhook(WEBHOOK_URL)
    yield
    # Shutdown: Удаление вебхука и корректное завершение работы бота.
    await telegram_app.bot.delete_webhook()
    await telegram_app.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    from telegram import Update
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}

@app.get("/")
async def root():
    return {"message": "Приложение работает"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
