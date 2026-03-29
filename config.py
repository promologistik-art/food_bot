import os
from dotenv import load_dotenv

load_dotenv()

# API для DeepSeek
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://routerai.ru/api/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek/deepseek-v3.2"

# Telegram Bot
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Пути к файлам
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FOOD_DB_PATH = os.getenv("FOOD_DB_PATH", os.path.join(BASE_DIR, "data", "food_database.json"))
USER_DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "data", "users.db"))

# Создаём папку data если её нет
os.makedirs(os.path.dirname(FOOD_DB_PATH), exist_ok=True)

# Настройки поиска
MAX_CANDIDATES = 10  # Максимум кандидатов для отправки в API
SEARCH_TEMPERATURE = 0.1  # Низкая температура для точного поиска

# Режим отладки
DEBUG = os.getenv("DEBUG", "False").lower() == "true"