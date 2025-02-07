# app/config.py
import os

# Если переменная AMVERA не установлена (то есть, приложение работает локально),
# загружаем переменные из файла .env.
if not os.environ.get("AMVERA"):
    from dotenv import load_dotenv
    load_dotenv()

# Далее – считывание переменных окружения.
try:
    TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
except KeyError:
    raise ValueError("Не найден токен Telegram Bot в переменных окружения")

SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'calendar-of-tomsk-progulka-b7cd9e8caac0.json'
CALENDAR_ID = 'u972jon1v46k3qed2anvj5mv14@group.calendar.google.com'
WEBHOOK_URL = 'https://kalendar--progulki-baslie.amvera.io/webhook'

ALLOWED_EDITORS = {
    903107929: "Алёна Федотова",
    799057247: "Анастасия Рекичинская",
    992334236: "Евгений Рогозин",
    822357130: "Евгения Колодяжная",
    1375676945: "Елена Маслова",
    1115434638: "Зоя Буркина",
    123064888: "Михаил Виноградов",
    193574626: "Роман Пуртов",
    1151753795: "Роман Стебунов"
}

BUTTONS = {
    "UPCOMING": "🗓️ Ближайшие мероприятия",
    "ADD_EVENT": "➕ Добавить мероприятие",
    "STATISTICS": "📊 Статистика",
    "MENU": "Меню",
    "BACK": "Назад",
    "CANCEL": "Отмена",
    "HELP": "Помощь",
    "SKIP": "Пропустить"
}

MESSAGES = {
    "WELCOME": "<b>Добро пожаловать в календарь мероприятий «Томской Прогулки»!</b>",
    "NO_EVENTS": "Ближайших мероприятий не найдено.",
    "NOT_AUTHORIZED": "У вас нет прав для добавления мероприятий.",
    "ENTER_TITLE": "Введите название мероприятия:",
    "ENTER_START": ("Введите дату и время начала мероприятия.\n"
                    "Можно ввести только дату (например, {example_date}) для события на весь день, "
                    "либо дату и время (например, {example_datetime}) для точного времени:"),
    "ENTER_END": "Введите дату и время окончания мероприятия (формат: ДД.MM.ГГГГ ЧЧ:ММ):",
    "ENTER_DESCRIPTION": "Введите описание мероприятия или нажмите «{skip}»:",
    "ENTER_LOCATION": "Введите локацию мероприятия или нажмите «{skip}»:",
    "CHOOSE_ORGANIZERS": "Выберите организатора(-ов) мероприятия:",
    "ANNOUNCE_QUERY": "Это событие нужно анонсировать в «Прогулке»?",
    "CONFIRMATION_QUERY": "Проверьте введённые данные:\n{summary}\n\nПодтверждаете создание мероприятия?",
    "EVENT_CREATED": "✅ Мероприятие создано успешно. Ссылка: {link}",
    "EVENT_CANCELLED": "Создание мероприятия отменено.",
    "PROCESSING": "Подождите, идёт обработка запроса…",
    "INPUT_ERROR": ("Неверный формат. Пожалуйста, введите данные в формате ДД.MM.ГГГГ [ЧЧ:ММ]. "
                    "Пример: 25.12.2025 15:00")
}
