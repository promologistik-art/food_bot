import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

from config import BOT_TOKEN
from food_search import FoodSearch
from db import UserDB

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
food_search = FoodSearch()
user_db = UserDB()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_db.get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    await message.answer("🍽 Привет! Просто напиши, что съел, и я посчитаю КБЖУ.\n\nПримеры:\nяичница 4 яйца, кофе с сахаром\ngречка 200г, куриная грудка 150\nяблоко 2 шт")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    stats = user_db.get_today_stats(message.from_user.id)
    await message.answer(f"📊 Статистика за сегодня:\nКалории: {stats['calories']:.0f} ккал\nБелки: {stats['protein']:.1f}г\nЖиры: {stats['fat']:.1f}г\nУглеводы: {stats['carbs']:.1f}г")

@dp.message()
async def handle_message(message: types.Message):
    await bot.send_chat_action(message.chat.id, "typing")
    
    result = await food_search.parse_and_calculate(message.text)
    
    if result["success"]:
        await message.answer(result["answer"])
    else:
        await message.answer("😕 Не удалось обработать. Попробуй написать проще, например: гречка 200г, курица 150")

async def main():
    print("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())