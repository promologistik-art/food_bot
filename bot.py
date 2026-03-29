import logging
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import BOT_TOKEN, DEBUG
from food_search import FoodSearch
from db import UserDB

# Настройка логирования
logging.basicConfig(level=logging.INFO if not DEBUG else logging.DEBUG)

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
food_search = FoodSearch()
user_db = UserDB()

# Состояния FSM
class AddProductState(StatesGroup):
    waiting_for_quantity = State()

# Вспомогательные функции
def format_nutrients(product_data: dict, quantity: float = 1.0) -> str:
    """Форматирует информацию о КБЖУ"""
    protein = product_data["protein"] * quantity
    fat = product_data["fat"] * quantity
    carbs = product_data["carbohydrates"] * quantity
    calories = product_data["calories"] * quantity
    
    quantity_text = f" ×{quantity:.1f}" if quantity != 1 else ""
    
    return f"""
🥗 *{product_data['product_name']}*{quantity_text}

📊 *КБЖУ:*
• 🔥 Калории: {calories:.1f} ккал
• 🥩 Белки: {protein:.1f} г
• 🧈 Жиры: {fat:.1f} г
• 🍚 Углеводы: {carbs:.1f} г
"""

def format_daily_stats(stats: dict) -> str:
    """Форматирует дневную статистику"""
    return f"""
📈 *Статистика за сегодня:*

• 🔥 Калории: {stats['calories']:.0f} ккал
• 🥩 Белки: {stats['protein']:.1f} г
• 🧈 Жиры: {stats['fat']:.1f} г
• 🍚 Углеводы: {stats['carbs']:.1f} г
"""

# Команды
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Приветственное сообщение"""
    user_db.get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    welcome_text = """
🍽️ *Добро пожаловать в FoodTracker Bot!*

Я помогу вам отслеживать питание и считать КБЖУ.

*Как пользоваться:*
• Просто напишите название продукта, который съели
• Я найду его в базе и покажу КБЖУ
• Затем спрошу количество (граммы/штуки)
• Вся статистика сохраняется

*Примеры запросов:*
• `яблоко`
• `гречка отварная`
• `куриная грудка`

*Команды:*
/start - Показать это сообщение
/stats - Показать статистику за сегодня
/history - Показать последние записи
/help - Помощь
/clear - Очистить статистику за сегодня
"""
    await message.answer(welcome_text, parse_mode="Markdown")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Помощь"""
    help_text = """
📖 *Помощь по командам:*

/start - Начать работу
/stats - Статистика за сегодня
/history - Последние 10 записей
/clear - Очистить статистику за сегодня

*Как добавлять продукты:*
1. Напишите название продукта
2. Я найду его в базе
3. Введите количество (в граммах или штуках)

*Пример:*
Вы: яблоко
Бот: найдено яблоко, 52 ккал/100г
Вы: 150 (грамм)
Бот: добавлено 78 ккал
"""
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Показывает статистику за сегодня"""
    stats = user_db.get_today_stats(message.from_user.id)
    await message.answer(format_daily_stats(stats), parse_mode="Markdown")

@dp.message(Command("history"))
async def cmd_history(message: types.Message):
    """Показывает историю записей"""
    meals = user_db.get_recent_meals(message.from_user.id, 10)
    
    if not meals:
        await message.answer("📭 История пуста. Добавьте первый продукт!")
        return
    
    history_text = "📋 *Последние записи:*\n\n"
    for meal in meals:
        quantity_str = f" ×{meal['quantity']:.1f}" if meal['quantity'] != 1 else ""
        history_text += f"• {meal['product_name']}{quantity_str} — {meal['calories'] * meal['quantity']:.0f} ккал\n"
    
    await message.answer(history_text, parse_mode="Markdown")

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    """Очищает статистику за сегодня с подтверждением"""
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data="clear_confirm"),
            InlineKeyboardButton(text="❌ Нет", callback_data="clear_cancel")
        ]
    ])
    await message.answer("⚠️ Вы уверены, что хотите очистить статистику за сегодня?", reply_markup=markup)

@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    """Отменяет текущий ввод"""
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer("❌ Ввод отменён.")
    else:
        await message.answer("Нет активных операций для отмены.")

# Обработчики callback
@dp.callback_query(lambda c: c.data.startswith("clear_"))
async def handle_clear_callback(callback: types.CallbackQuery):
    if callback.data == "clear_confirm":
        user_db.clear_today(callback.from_user.id)
        await callback.message.edit_text("✅ Статистика за сегодня очищена!")
    else:
        await callback.message.edit_text("❌ Очистка отменена.")
    await callback.answer()

# Поиск продукта
@dp.message(AddProductState.waiting_for_quantity)
async def handle_quantity_input(message: types.Message, state: FSMContext):
    """Обрабатывает ввод количества продукта"""
    quantity_text = message.text.strip()
    
    # Парсим количество
    try:
        quantity_text = quantity_text.replace('г', '').replace('гр', '').replace('шт', '').strip()
        quantity = float(quantity_text.replace(',', '.'))
        
        if quantity <= 0:
            raise ValueError("Количество должно быть больше 0")
        
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите корректное количество (например: 150, 2.5, 3 шт)",
            parse_mode="Markdown"
        )
        return
    
    # Получаем сохранённый продукт
    data = await state.get_data()
    product = data.get("last_product")
    
    if not product:
        await state.clear()
        await message.answer("❌ Произошла ошибка. Попробуйте ввести продукт заново.")
        return
    
    # Добавляем в базу
    user_db.add_meal(message.from_user.id, product, quantity)
    
    # Получаем обновлённую статистику
    stats = user_db.get_today_stats(message.from_user.id)
    
    # Формируем ответ
    response = format_nutrients(product, quantity)
    response += "\n✅ *Добавлено в дневник!*\n"
    response += format_daily_stats(stats)
    response += "\n\n📝 *Что дальше?*\n"
    response += "• Введите ещё один продукт\n"
    response += "• /stats - посмотреть статистику\n"
    response += "• /history - история записей"
    
    await message.answer(response, parse_mode="Markdown")
    await state.clear()

@dp.message()
async def handle_product_search(message: types.Message, state: FSMContext):
    """Обрабатывает поиск продукта"""
    query = message.text.strip()
    
    # Отправляем уведомление о наборе
    await bot.send_chat_action(message.chat.id, "typing")
    
    try:
        product = await food_search.search_product(query)
        
        if not product or not product.get("product_name"):
            await message.answer(
                f"😕 Не удалось найти продукт: *{query}*\n\n"
                "Попробуйте перефразировать запрос или ввести название точнее.",
                parse_mode="Markdown"
            )
            return
        
        # Сохраняем продукт в состояние
        await state.set_state(AddProductState.waiting_for_quantity)
        await state.update_data(last_product=product)
        
        # Отправляем информацию о продукте
        product_info = format_nutrients(product, 100)
        confidence_note = ""
        
        if product.get("match_confidence") == "medium":
            confidence_note = "\n\n⚠️ *Внимание:* Это наиболее подходящий вариант. Проверьте, тот ли продукт вы имели в виду?"
        elif product.get("match_confidence") == "low":
            confidence_note = "\n\n⚠️ *Внимание:* Точное совпадение не найдено. Проверьте, правильный ли продукт выбран."
        
        if product.get("note"):
            confidence_note += f"\n\n📝 *Примечание:* {product['note']}"
        
        await message.answer(
            f"{product_info}{confidence_note}\n\n"
            "✍️ *Сколько вы съели?*\n"
            "Напишите количество в граммах (например: 150) или штуках (например: 2)",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logging.error(f"Error in product search: {e}")
        await message.answer(
            "😕 Произошла ошибка при поиске продукта. Попробуйте позже.",
            parse_mode="Markdown"
        )

# Запуск
async def main():
    """Запуск бота"""
    print("🤖 Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())