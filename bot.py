import logging
import asyncio
import re
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import BOT_TOKEN, DEBUG
from food_search import FoodSearch
from db import UserDB

logging.basicConfig(level=logging.INFO if not DEBUG else logging.DEBUG)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
food_search = FoodSearch()
user_db = UserDB()

def extract_weight_from_user_input(user_text: str, product_name: str) -> float:
    """Извлекает вес продукта из исходного сообщения пользователя"""
    patterns = [
        rf'{product_name}\s*(\d+(?:[.,]\d+)?)\s*г',
        rf'{product_name}\s*(\d+(?:[.,]\d+)?)\s*грамм',
        rf'(\d+(?:[.,]\d+)?)\s*г\s*{product_name}',
        rf'(\d+(?:[.,]\d+)?)\s*грамм\s*{product_name}',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, user_text, re.IGNORECASE)
        if match:
            return float(match.group(1).replace(',', '.'))
    
    # Если не нашли вес, возвращаем None
    return None

def calculate_product(product_name: str, weight_grams: float, food_db: dict) -> dict:
    """Рассчитывает КБЖУ для продукта по весу"""
    if product_name in food_db:
        data = food_db[product_name]
        multiplier = weight_grams / 100
        return {
            "found_name": product_name,
            "weight_grams": weight_grams,
            "calories": data["calories"] * multiplier,
            "protein": data["protein"] * multiplier,
            "fat": data["fat"] * multiplier,
            "carbs": data["carbohydrates"] * multiplier
        }
    return None

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
    
    await message.answer("""
FoodTracker Bot

Просто напишите, что съели.

Примеры:
яичница 4 яйца, кофе 2 ложки сахара
гречка 200г, куриная грудка 150
яблоко 2 шт

Команды:
/stats — статистика
/history — история
/clear — очистить
""")

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

@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    user_text = message.text.strip()
    
    await bot.send_chat_action(message.chat.id, "typing")
    
    result = await food_search.parse_and_calculate(user_text)
    
    if not result["success"]:
        await message.answer(result["data"]["response_text"])
        return
    
    data = result["data"]
    products_from_ai = data.get("products", [])
    
    if not products_from_ai:
        await message.answer("Не удалось распознать продукты.")
        return
    
    # ВАЖНО: пересчитываем продукты с правильным весом
    corrected_products = []
    
    for product in products_from_ai:
        product_name = product.get("found_name")
        if not product_name:
            continue
        
        # Пытаемся извлечь вес из исходного сообщения
        weight = extract_weight_from_user_input(user_text, product_name)
        
        if weight is None:
            # Если вес не найден, используем то, что вернул AI
            weight = product.get("weight_grams", 100)
            # Но проверяем, не 1 ли грамм (ошибка AI)
            if weight == 1:
                weight = 100  # ставим разумное значение по умолчанию
        
        # Пересчитываем КБЖУ
        corrected = calculate_product(product_name, weight, food_search.food_db)
        
        if corrected:
            corrected["quantity"] = product.get("quantity", 1)
            corrected["unit"] = product.get("unit", "г")
            corrected_products.append(corrected)
    
    if not corrected_products:
        await message.answer("Не удалось найти продукты в базе.")
        return
    
    # Сохраняем в базу
    user_db.add_meals_batch(user_id, corrected_products)
    
    # Получаем статистику
    stats = user_db.get_today_stats(user_id)
    
    # Формируем ответ
    response_lines = ["Добавлено:\n"]
    
    for p in corrected_products:
        unit = p.get("unit", "г")
        qty = p.get("quantity", 1)
        if unit == "г":
            response_lines.append(f"{p['found_name']} — {p['weight_grams']:.0f} {unit} — {p['calories']:.0f} ккал")
        else:
            response_lines.append(f"{p['found_name']} — {qty} {unit} — {p['calories']:.0f} ккал")
    
    response_lines.append("\n" + format_daily_stats(stats))
    
    await message.answer("\n".join(response_lines))

async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())