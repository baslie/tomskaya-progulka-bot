# bot.py
from telegram.ext import Application, Defaults
from telegram.constants import ParseMode
from .config import TELEGRAM_TOKEN

# Инициализация приложения Telegram Bot с заданными параметрами по умолчанию.
telegram_app = (
    Application.builder()
    .token(TELEGRAM_TOKEN)
    .defaults(Defaults(parse_mode=ParseMode.HTML))  # Использование HTML-разметки по умолчанию
    .build()
)
