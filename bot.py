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
    await message.answer("FoodTracker Bot\n\nПросто напишите, что съели — я всё посчитаю!\n\nПримеры:\nяичница 4 яйца, кофе 2 ложки сахара\ngречка 200г, куриная грудка 150\nборщ 400г\n\nКоманды:\n/stats — статистика\n/history — история\n/clear — очистить")

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
    """Извлекает данные продукта из разных форматов ответа DeepSeek"""
    return {
        "name": product.get("found_name") or product.get("name") or product.get("product_name") or "Неизвестный продукт",
        "weight_grams": product.get("weight_grams") or product.get("weight") or product.get("quantity", 100),
        "calories": product.get("calories", 0),
        "protein": product.get("protein", 0),
        "fat": product.get("fat", 0),
        "carbs": product.get("carbs") or product.get("carbohydrates", 0)
    }

@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    await bot.send_chat_action(message.chat.id, "typing")
    
    result = await food_search.parse_and_calculate(message.text)
    
    if not result["success"]:
        await message.answer(f"Не удалось обработать. {result.get('error', '')}")
        return
    
    data = result["data"]
    products = data.get("products", [])
    user_text = data.get("user_text", "")
    
    if not products:
        await message.answer("Не удалось распознать продукты.")
        return
    
    # Сохраняем в базу
    for p in products:
        product_data = extract_product_data(p)
        user_db.add_meal(user_id, product_data)
    
    stats = user_db.get_today_stats(user_id)
    
    # Отправляем ответ
    if user_text:
        await message.answer(user_text + "\n\n" + format_daily_stats(stats))
    else:
        response = "Добавлено:\n\n"
        for p in products:
            pd = extract_product_data(p)
            response += f"{pd['name']} — {pd['weight_grams']:.0f}г — Калории: {pd['calories']:.0f}, Белки: {pd['protein']:.1f}, Жиры: {pd['fat']:.1f}, Углеводы: {pd['carbs']:.1f}\n"
        response += "\n" + format_daily_stats(stats)
        await message.answer(response)

async def main():
    print("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())