import os
from dotenv import load_dotenv

load_dotenv()

# База данных продуктов в корне проекта
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FOOD_DB_PATH = os.path.join(BASE_DIR, "data.json")  # теперь в корне

# Проверяем при старте
print(f"🔍 Путь к базе: {FOOD_DB_PATH}")
print(f"✅ Файл существует: {os.path.exists(FOOD_DB_PATH)}")

# Остальные настройки
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://routerai.ru/api/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek/deepseek-v3.2"
BOT_TOKEN = os.getenv("BOT_TOKEN")
USER_DB_PATH = os.path.join(BASE_DIR, "users.db")  # тоже в корне
MAX_CANDIDATES = 10
SEARCH_TEMPERATURE = 0.1
DEBUG = os.getenv("DEBUG", "False").lower() == "true"