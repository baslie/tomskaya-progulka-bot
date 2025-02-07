# app/cache.py
import os
import json
import asyncio
from datetime import datetime, timedelta

# Используем aiofiles для асинхронного доступа к файлам
import aiofiles

from .calendar_api import get_upcoming_events

# Абсолютный путь к файлу кэша и время жизни кэша (3 минуты)
CACHE_FILE = "/data/events_cache.json"
CACHE_TTL = timedelta(minutes=3)

async def get_cached_events():
    """
    Возвращает список ближайших мероприятий с использованием файлового кэша.
    Если файл кэша существует и его возраст меньше CACHE_TTL, данные считываются из него.
    Иначе выполняется новый запрос к Google Calendar и кэш обновляется.
    """
    print("Запуск функции get_cached_events")  # Лог запуска функции

    try:
        # Проверяем время модификации файла
        stat_result = await asyncio.get_running_loop().run_in_executor(None, os.stat, CACHE_FILE)
        file_mod_time = datetime.fromtimestamp(stat_result.st_mtime)
        age = datetime.now() - file_mod_time
        print(f"Файл кэша найден. Возраст файла: {age}. TTL: {CACHE_TTL}.")
        if age < CACHE_TTL:
            # Файл кэша свежий – читаем данные из него
            async with aiofiles.open(CACHE_FILE, "r") as f:
                data = await f.read()
                try:
                    events = json.loads(data)
                    print("Данные успешно прочитаны из кэша:", events)
                    return events
                except json.JSONDecodeError as json_err:
                    print(f"Ошибка декодирования JSON из кэша: {json_err}")
    except FileNotFoundError:
        print("Файл кэша не найден.")
    except Exception as e:
        print(f"Ошибка при проверке кэша: {e}")

    # Если кэш отсутствует или устарел – выполняем запрос к Google Calendar
    print("Выполнение запроса к Google Calendar...")
    events = await asyncio.to_thread(get_upcoming_events)
    print("Полученные события:", events)
    
    # Обновляем файл кэша
    try:
        async with aiofiles.open(CACHE_FILE, "w") as f:
            await f.write(json.dumps(events))
        print("Кэш успешно обновлён.")
    except Exception as e:
        print(f"Ошибка при обновлении кэша: {e}")
    return events
