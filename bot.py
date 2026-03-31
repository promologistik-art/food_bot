import logging
import asyncio
import re
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import BOT_TOKEN
from food_search import FoodSearch
from db import UserDB

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
food_search = FoodSearch()
user_db = UserDB()

class WaitingState(StatesGroup):
    waiting_for_correction = State()

def format_daily_stats(stats: dict) -> str:
    return f"""
Статистика за сегодня:
Калории: {stats['calories']:.0f} ккал
Белки: {stats['protein']:.1f} г
Жиры: {stats['fat']:.1f} г
Углеводы: {stats['carbs']:.1f} г
"""

async def set_bot_commands():
    commands = [
        BotCommand(command="start", description="Начать работу"),
        BotCommand(command="stats", description="Статистика за сегодня"),
        BotCommand(command="history", description="История записей"),
        BotCommand(command="clear", description="Очистить статистику"),
        BotCommand(command="help", description="Помощь"),
    ]
    await bot.set_my_commands(commands)

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_db.get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    await message.answer("FoodTracker Bot\n\nПросто напишите, что съели — я всё посчитаю!\n\nПримеры:\nяичница 4 яйца, кофе 2 ложки сахара\nгречка 200г, куриная грудка 150\nборщ 400г\n\nКоманды:\n/stats — статистика\n/history — история\n/clear — очистить")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer("Помощь:\n\n/stats — статистика за сегодня\n/history — история записей\n/clear — очистить статистику\n\nПросто напишите, что съели, например:\nборщ 400г\nяичница 4 яйца\nгречка 200г, курица 150")

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

def is_affirmative(text: str) -> bool:
    text = text.lower().strip()
    affirmative = ["да", "yes", "+", "ок", "окей", "хорошо", "верно", "ага", "дада"]
    return any(word in text for word in affirmative)

def is_negative(text: str) -> bool:
    text = text.lower().strip()
    negative = ["нет", "no", "-", "не", "неверно", "не правильно", "не так"]
    return any(word in text for word in negative)

def is_correction(text: str) -> bool:
    has_numbers = bool(re.search(r'\d+', text))
    has_units = bool(re.search(r'г|гр|грамм|шт|штук|ложк|стакан|чашка', text.lower()))
    return has_numbers or has_units

def is_delete_command(text: str) -> bool:
    text = text.lower().strip()
    delete_words = ["удали", "убрать", "удалить", "убри", "убери", "delete", "remove"]
    return any(word in text for word in delete_words)

@dp.message(WaitingState.waiting_for_correction)
async def handle_correction(message: types.Message, state: FSMContext):
    user_text = message.text.strip().lower()
    data = await state.get_data()
    original_products = data.get("original_products", [])
    
    if is_affirmative(user_text):
        for p in original_products:
            product_data = extract_product_data(p)
            user_db.add_meal(message.from_user.id, product_data)
        stats = user_db.get_today_stats(message.from_user.id)
        await message.answer(f"Сохранено!\n\n{format_daily_stats(stats)}")
        await state.clear()
        return
    
    if is_negative(user_text) and not is_correction(user_text):
        await message.answer("Напишите правильные данные, например:\nборщ 300г\nкефир 200г\nили\nудали яйца")
        return
    
    if is_delete_command(user_text):
        words_to_delete = re.findall(r'[\w]+', user_text.replace("удали", "").replace("убрать", "").replace("удалить", ""))
        if words_to_delete:
            to_delete = words_to_delete[0]
            new_products = []
            for p in original_products:
                if to_delete not in p.get("name", "").lower():
                    new_products.append(p)
            
            if len(new_products) == len(original_products):
                await message.answer(f"Не найден продукт '{to_delete}' для удаления.")
                return
            
            total = {"calories": 0, "protein": 0, "fat": 0, "carbs": 0}
            for p in new_products:
                total["calories"] += p.get("calories", 0)
                total["protein"] += p.get("protein", 0)
                total["fat"] += p.get("fat", 0)
                total["carbs"] += p.get("carbs", 0)
            
            lines = []
            for p in new_products:
                name = p.get("name", "")
                weight = p.get("weight_grams", 0)
                cal = p.get("calories", 0)
                prot = p.get("protein", 0)
                fat = p.get("fat", 0)
                carbs = p.get("carbs", 0)
                lines.append(f"{name} - {weight}г, К {cal:.0f}, Б {prot:.1f}, Ж {fat:.1f}, У {carbs:.1f}")
            
            result_text = "Обновлено:\n\n" + "\n".join(lines)
            result_text += f"\n\nИТОГО: {total['calories']:.0f} ккал | Б: {total['protein']:.1f}г | Ж: {total['fat']:.1f}г | У: {total['carbs']:.1f}г"
            result_text += "\n\nВерно?"
            
            await state.update_data(original_products=new_products)
            await message.answer(result_text)
        return
    
    if is_correction(user_text):
        waiting_msg = await message.answer("Пересчитываю...")
        result = await food_search.parse_and_calculate(user_text)
        await waiting_msg.delete()
        
        if not result["success"] or not result["data"].get("products"):
            await message.answer("Не удалось распознать корректировку. Напишите, например:\nборщ 300г\nкефир 200г")
            return
        
        new_products = result["data"].get("products", [])
        total = result["data"].get("total", {})
        
        lines = []
        for p in new_products:
            name = p.get("name", "")
            weight = p.get("weight_grams", 0)
            cal = p.get("calories", 0)
            prot = p.get("protein", 0)
            fat = p.get("fat", 0)
            carbs = p.get("carbs", 0)
            lines.append(f"{name} - {weight}г, К {cal:.0f}, Б {prot:.1f}, Ж {fat:.1f}, У {carbs:.1f}")
        
        result_text = "Обновлено:\n\n" + "\n".join(lines)
        result_text += f"\n\nИТОГО: {total['calories']:.0f} ккал | Б: {total['protein']:.1f}г | Ж: {total['fat']:.1f}г | У: {total['carbs']:.1f}г"
        result_text += "\n\nВерно?"
        
        await state.update_data(original_products=new_products)
        await message.answer(result_text)
        return
    
    await message.answer("Не понял. Напишите 'да' для сохранения, 'нет' для исправления, или просто правильные данные.")

@dp.message()
async def handle_message(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    current_state = await state.get_state()
    if current_state == WaitingState.waiting_for_correction.state:
        await handle_correction(message, state)
        return
    
    waiting_msg = await message.answer("Считаю...")
    await bot.send_chat_action(message.chat.id, "typing")
    
    result = await food_search.parse_and_calculate(message.text)
    
    await waiting_msg.delete()
    
    if not result["success"] or not result["data"].get("products"):
        await message.answer("Не удалось обработать. Попробуйте написать по-другому, например:\nборщ 400г\nяичница 4 яйца\nстакан кефира")
        return
    
    data = result["data"]
    products = data.get("products", [])
    user_text = result.get("user_text", "")
    
    if not products:
        await message.answer("Не удалось распознать продукты.")
        return
    
    await state.set_state(WaitingState.waiting_for_correction)
    await state.update_data(original_products=products, original_message=message.text)
    
    if user_text:
        await message.answer(user_text + "\n\nВерно?")
    else:
        lines = []
        for p in products:
            name = p.get("name", "")
            weight = p.get("weight_grams", 0)
            cal = p.get("calories", 0)
            prot = p.get("protein", 0)
            fat = p.get("fat", 0)
            carbs = p.get("carbs", 0)
            lines.append(f"{name} - {weight}г, К {cal:.0f}, Б {prot:.1f}, Ж {fat:.1f}, У {carbs:.1f}")
        
        total = data.get("total", {})
        result_text = "\n".join(lines)
        result_text += f"\n\nИТОГО: {total.get('calories', 0):.0f} ккал | Б: {total.get('protein', 0):.1f}г | Ж: {total.get('fat', 0):.1f}г | У: {total.get('carbs', 0):.1f}г"
        result_text += "\n\nВерно?"
        
        await message.answer(result_text)

async def main():
    await set_bot_commands()
    print("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())