# app/usage_stats.py
import os
import json
import asyncio
from datetime import datetime

# Абсолютный путь к файлу статистики
STATS_FILE = "/data/usage_stats.json"

async def log_usage(user):
    """
    Регистрирует факт взаимодействия пользователя с ботом.
    Обновляет (или создаёт) запись для данного пользователя, увеличивая счётчик взаимодействий за текущую дату.
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _update_stats, user)

def _update_stats(user):
    try:
        with open(STATS_FILE, "r") as f:
            data = json.load(f)
    except Exception:
        data = {}

    uid = str(user.id)
    today = datetime.now().strftime("%Y-%m-%d")
    if uid not in data:
        username = user.username if user.username else f"{user.first_name} {user.last_name}".strip()
        data[uid] = {"username": username, "interactions": {}}
    if today not in data[uid]["interactions"]:
        data[uid]["interactions"][today] = 0
    data[uid]["interactions"][today] += 1

    try:
        with open(STATS_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Ошибка при сохранении статистики: {e}")

def read_stats():
    """
    Синхронно считывает статистику использования из файла.
    """
    if not os.path.exists(STATS_FILE):
        return {}
    try:
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Ошибка при чтении статистики: {e}")
        return {}
