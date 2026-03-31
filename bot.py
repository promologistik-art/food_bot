import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import BOT_TOKEN
from food_search import FoodSearch
from db import UserDB

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
food_search = FoodSearch()
user_db = UserDB()

def format_daily_stats(stats: dict) -> str:
    return f"""
Статистика за сегодня:
Калории: {stats['calories']:.0f} ккал
Белки: {stats['protein']:.1f} г
Жиры: {stats['fat']:.1f} г
Углеводы: {stats['carbs']:.1f} г
"""

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_db.get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    await message.answer("FoodTracker Bot\n\nПросто напишите, что съели — я всё посчитаю!\n\nПримеры:\nяичница 4 яйца, кофе 2 ложки сахара\nгречка 200г, куриная грудка 150\nборщ 400г\n\nКоманды:\n/stats — статистика\n/history — история\n/clear — очистить")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    stats = user_db.get_today_stats(message.from_user.id)
    await message.answer(format_daily_stats(stats))

@dp.message(Command("history"))
async def cmd_history(message: types.Message):
    meals = user_db.get_recent_meals(message.from_user.id, 10)
    if not meals:
        await message.answer("История пуста.")
        return
    text = "Последние записи:\n\n"
    for meal in meals:
        qty = f" x{meal['quantity']:.1f}" if meal['quantity'] != 1 else ""
        text += f"{meal['product_name']}{qty} — {meal['calories'] * meal['quantity']:.0f} ккал\n"
    await message.answer(text)

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data="clear_confirm"),
         InlineKeyboardButton(text="Нет", callback_data="clear_cancel")]
    ])
    await message.answer("Очистить статистику за сегодня?", reply_markup=markup)

@dp.callback_query(lambda c: c.data.startswith("clear_"))
async def handle_clear_callback(callback: types.CallbackQuery):
    if callback.data == "clear_confirm":
        user_db.clear_today(callback.from_user.id)
        await callback.message.edit_text("Статистика очищена!")
    else:
        await callback.message.edit_text("Отменено.")
    await callback.answer()

def extract_product_data(product: dict) -> dict:
    return {
        "name": product.get("name", "Неизвестный продукт"),
        "weight_grams": product.get("weight_grams", 100),
        "calories": product.get("calories", 0),
        "protein": product.get("protein", 0),
        "fat": product.get("fat", 0),
        "carbs": product.get("carbs", 0)
    }

@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    
    waiting_msg = await message.answer("Считаю...")
    await bot.send_chat_action(message.chat.id, "typing")
    
    result = await food_search.parse_and_calculate(message.text)
    
    await waiting_msg.delete()
    
    if not result["success"]:
        error_text = result.get('error', '')
        await message.answer(f"Не удалось обработать.\n\n{error_text}\n\nПопробуйте написать по-другому, например:\nборщ 400г\nяичница 4 яйца\nстакан кефира")
        return
    
    data = result["data"]
    products = data.get("products", [])
    user_text = result.get("user_text", "")
    
    if not products:
        await message.answer("Не удалось распознать продукты.\n\nПопробуйте написать по-другому, например:\nборщ 400г\nяичница 4 яйца\nстакан кефира")
        return
    
    for p in products:
        product_data = extract_product_data(p)
        user_db.add_meal(user_id, product_data)
    
    stats = user_db.get_today_stats(user_id)
    
    if user_text:
        await message.answer(user_text + "\n\n" + format_daily_stats(stats))

async def main():
    print("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())