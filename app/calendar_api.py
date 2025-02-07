# calendar_api.py
from datetime import datetime, timezone, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from .config import SCOPES, SERVICE_ACCOUNT_FILE, CALENDAR_ID

# Инициализация учетных данных и клиента Google Calendar API.
try:
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build('calendar', 'v3', credentials=credentials)
except Exception as e:
    # Логирование ошибки и, при необходимости, уведомление разработчиков.
    print(f"Ошибка при инициализации Google Calendar API: {e}")
    raise

def get_upcoming_events():
    """
    Запрашивает ближайшие 30 мероприятий из календаря.
    Возвращает список событий или пустой список при ошибке.
    """
    try:
        now = datetime.now(timezone.utc).isoformat()
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=now,
            maxResults=30,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        return events_result.get('items', [])
    except Exception as e:
        print(f"Ошибка при получении мероприятий: {e}")
        return []

def add_event_to_calendar(event_body):
    """
    Добавляет событие в Google Calendar.
    При возникновении ошибки пробрасывает исключение.
    """
    try:
        return service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
    except Exception as e:
        print(f"Ошибка при добавлении мероприятия: {e}")
        raise
