import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import BOT_TOKEN, DEBUG
from food_search import FoodSearch
from db import UserDB

logging.basicConfig(level=logging.INFO if not DEBUG else logging.DEBUG)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
food_search = FoodSearch()
user_db = UserDB()

class AddProductState(StatesGroup):
    waiting_for_quantity = State()


def format_daily_stats(stats: dict) -> str:
    return f"""
📈 *Статистика за сегодня:*
🔥 {stats['calories']:.0f} ккал | 🥩 {stats['protein']:.1f}г | 🧈 {stats['fat']:.1f}г | 🍚 {stats['carbs']:.1f}г
"""


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_db.get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    await message.answer("""
🍽️ *FoodTracker Bot*

Просто напишите, что съели — я всё посчитаю!

*Примеры:*
• `яичница 4 яйца, кофе 2 ложки сахара, бутерброд с авокадо`
• `гречка 200г, куриная грудка 150`
• `яблоко 2 шт`

*Команды:*
/stats — статистика
/history — история
/clear — очистить
""", parse_mode="Markdown")


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    stats = user_db.get_today_stats(message.from_user.id)
    await message.answer(format_daily_stats(stats), parse_mode="Markdown")


@dp.message(Command("history"))
async def cmd_history(message: types.Message):
    meals = user_db.get_recent_meals(message.from_user.id, 10)
    
    if not meals:
        await message.answer("📭 История пуста.")
        return
    
    text = "📋 *Последние записи:*\n\n"
    for meal in meals:
        qty = f" ×{meal['quantity']:.1f}" if meal['quantity'] != 1 else ""
        text += f"• {meal['product_name']}{qty} — {meal['calories'] * meal['quantity']:.0f} ккал\n"
    
    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data="clear_confirm"),
         InlineKeyboardButton(text="❌ Нет", callback_data="clear_cancel")]
    ])
    await message.answer("⚠️ Очистить статистику за сегодня?", reply_markup=markup)


@dp.callback_query(lambda c: c.data.startswith("clear_"))
async def handle_clear_callback(callback: types.CallbackQuery):
    if callback.data == "clear_confirm":
        user_db.clear_today(callback.from_user.id)
        await callback.message.edit_text("✅ Статистика очищена!")
    else:
        await callback.message.edit_text("❌ Отменено.")
    await callback.answer()


@dp.message(Command("test"))
async def cmd_test(message: types.Message):
    """Тест API"""
    await message.answer("🔍 Тестирую API...")
    
    result = await food_search.parse_and_calculate("яблоко 150г")
    
    if result["success"]:
        data = result["data"]
        products = data.get("products", [])
        total = data.get("total", {})
        
        await message.answer(
            f"✅ *API работает!*\n\n"
            f"Найдено: {len(products)} продуктов\n"
            f"Калорий: {total.get('calories', 0):.0f} ккал\n\n"
            f"```json\n{str(data)[:400]}```",
            parse_mode="Markdown"
        )
    else:
        await message.answer(f"❌ Ошибка API", parse_mode="Markdown")


@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    user_text = message.text.strip()
    
    await bot.send_chat_action(message.chat.id, "typing")
    
    result = await food_search.parse_and_calculate(user_text)
    
    if not result["success"]:
        await message.answer(result["data"]["response_text"], parse_mode="Markdown")
        return
    
    data = result["data"]
    products = data.get("products", [])
    
    if not products:
        await message.answer("😕 Не удалось распознать продукты.", parse_mode="Markdown")
        return
    
    # Сохраняем продукты
    products_to_save = []
    not_found = []
    
    for product in products:
        if product.get("found_name"):
            products_to_save.append(product)
        else:
            not_found.append(product)
    
    if products_to_save:
        user_db.add_meals_batch(user_id, products_to_save)
    
    stats = user_db.get_today_stats(user_id)
    
    # Формируем ответ
    response_lines = ["📋 *Добавлено:*\n"]
    
    for p in products_to_save:
        qty = f"{p['quantity']:.1f} {p.get('unit', 'г')}"
        warn = " ⚠️" if p.get("confidence") == "low" else ""
        response_lines.append(f"• {p['found_name']}{warn} — {qty} — {p['calories'] * p['quantity']:.0f} ккал")
    
    if not_found:
        response_lines.append("\n❓ *Не найдено:*")
        for p in not_found:
            response_lines.append(f"• {p.get('user_input', '?')} — {p.get('quantity', 1)} {p.get('unit', 'порция')}")
    
    response_lines.append("\n━━━━━━━━━━━━━━━━━━━━━")
    response_lines.append(format_daily_stats(stats))
    response_lines.append("\n/stats — статистика | /history — история")
    
    await message.answer("\n".join(response_lines), parse_mode="Markdown")


async def main():
    logger.info("🤖 Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())