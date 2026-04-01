import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("DEEPSEEK_API_KEY")
OPENAI_BASE_URL = "https://routerai.ru/api/v1"
OPENAI_MODEL = "deepseek/deepseek-v3.2"

BOT_TOKEN = os.getenv("BOT_TOKEN")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FOOD_DB_PATH = os.path.join(BASE_DIR, "data.json")
USER_DB_PATH = os.path.join(BASE_DIR, "users.db")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")  # Username админа без @
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # ID админа для уведомлений
TRIAL_DAYS = 5
SUBSCRIPTION_PRICE = 300
ADMIN_CONTACT = f"@{ADMIN_USERNAME}" if ADMIN_USERNAME else "@silverzen"

SEARCH_TEMPERATURE = 0.1
DEBUG = os.getenv("DEBUG", "False").lower() == "true"