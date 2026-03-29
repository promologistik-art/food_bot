import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# Определяем корневую директорию проекта
BASE_DIR = Path(__file__).parent.absolute()

# Путь к файлу базы продуктов (ищем в нескольких местах)
def get_food_db_path():
    """Ищет файл базы в разных местах"""
    possible_paths = [
        BASE_DIR / "data" / "food_database.json",
        BASE_DIR / "food_database.json",
        Path("/app/data/food_database.json"),  # для Docker/хостинга
        Path("/home/bitrix/www/data/food_database.json"),  # для Bitrix/хостинга
    ]
    
    for path in possible_paths:
        if path.exists():
            print(f"✅ Найден файл базы: {path}")
            return str(path)
    
    # Если файл не найден, создаём тестовую базу
    print("⚠️ Файл базы не найден, создаю тестовую...")
    return str(BASE_DIR / "data" / "food_database.json")

FOOD_DB_PATH = get_food_db_path()

# Создаём папку data если её нет
os.makedirs(os.path.dirname(FOOD_DB_PATH), exist_ok=True)

# Остальные настройки
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://routerai.ru/api/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek/deepseek-v3.2"
BOT_TOKEN = os.getenv("BOT_TOKEN")
USER_DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "data" / "users.db"))
MAX_CANDIDATES = 10
SEARCH_TEMPERATURE = 0.1
DEBUG = os.getenv("DEBUG", "False").lower() == "true"