import logging
import asyncio
from typing import Dict, List, Any
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import BOT_TOKEN, DEBUG
from food_search import FoodSearch
from db import UserDB

# Настройка логирования
logging.basicConfig(
    level=logging.INFO if not DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
food_search = FoodSearch()
user_db = UserDB()

# Состояния FSM
class AddProductState(StatesGroup):
    waiting_for_quantity = State()


def format_nutrients(product_data: dict, quantity: float = 1.0) -> str:
    """Форматирует информацию о КБЖУ"""
    protein = product_data.get("protein", 0) * quantity
    fat = product_data.get("fat", 0) * quantity
    carbs = product_data.get("carbohydrates", product_data.get("carbs", 0)) * quantity
    calories = product_data.get("calories", 0) * quantity
    
    quantity_text = f" ×{quantity:.1f}" if quantity != 1 else ""
    unit = product_data.get("unit", "г")
    
    return f"""
🥗 *{product_data.get('name', product_data.get('product_name', 'Продукт'))}*{quantity_text}
🔥 {calories:.0f} ккал | 🥩 {protein:.1f}г | 🧈 {fat:.1f}г | 🍚 {carbs:.1f}г
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


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Приветственное сообщение"""
    user_db.get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    welcome_text = """
🍽️ *FoodTracker Bot*

Я помогу вам отслеживать питание и считать КБЖУ!

*Как пользоваться:*
Просто напишите, что съели — я всё посчитаю!

*Примеры:*
• `яичница 4 яйца, кофе 2 ложки сахара, бутерброд с авокадо`
• `гречка 200г, куриная грудка 150`
• `яблоко 2 шт`
• `борщ 300 мл`

*Команды:*
/stats — статистика за сегодня
/history — последние записи
/clear — очистить статистику
/help — помощь
"""
    await message.answer(welcome_text, parse_mode="Markdown")


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Помощь"""
    help_text = """
📖 *Помощь по командам:*

/start — начать работу
/stats — статистика за сегодня
/history — последние 10 записей
/clear — очистить статистику за сегодня
/help — показать это сообщение

*Как добавлять продукты:*
1. Просто напишите, что съели
2. Бот сам разберёт сообщение и найдёт продукты
3. Все данные сохранятся в дневник

*Примеры правильных запросов:*
• `яблоко 150г`
• `гречка 200, курица 150`
• `яичница 4 яйца, кофе с молоком`
• `борщ 300мл, хлеб 1 кусок`

*Поддерживаемые единицы измерения:*
г, гр, грамм, кг, мл, шт, штук, порция, ложка, чашка
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


@dp.callback_query(lambda c: c.data.startswith("clear_"))
async def handle_clear_callback(callback: types.CallbackQuery):
    """Обработка подтверждения очистки"""
    if callback.data == "clear_confirm":
        user_db.clear_today(callback.from_user.id)
        await callback.message.edit_text("✅ Статистика за сегодня очищена!")
    else:
        await callback.message.edit_text("❌ Очистка отменена.")
    await callback.answer()


@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    """Отменяет текущий ввод"""
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer("❌ Ввод отменён.")
    else:
        await message.answer("Нет активных операций для отмены.")


@dp.message()
async def handle_message(message: types.Message, state: FSMContext):
    """
    Главный обработчик сообщений.
    Отправляет текст пользователя в DeepSeek для парсинга и расчёта КБЖУ.
    """
    user_id = message.from_user.id
    user_text = message.text.strip()
    
    # Проверяем, не ждём ли мы количество (для обратной совместимости)
    current_state = await state.get_state()
    if current_state == AddProductState.waiting_for_quantity.state:
        await handle_quantity_input(message, state)
        return
    
    # Отправляем уведомление о наборе
    await bot.send_chat_action(message.chat.id, "typing")
    
    try:
        # Отправляем запрос в DeepSeek
        logger.info(f"Processing message from user {user_id}: {user_text[:100]}...")
        result = await food_search.parse_and_calculate(user_text)
        
        if not result["success"]:
            await message.answer(result["data"]["response_text"], parse_mode="Markdown")
            return
        
        data = result["data"]
        products = data.get("products", [])
        
        if not products:
            await message.answer(
                "😕 Не удалось распознать продукты в вашем сообщении.\n\n"
                "Попробуйте написать проще, например:\n"
                "• `яблоко 150г`\n"
                "• `гречка 200, курица 150`",
                parse_mode="Markdown"
            )
            return
        
        # Подготавливаем продукты для сохранения
        products_to_save = []
        not_found = []
        warning_products = []
        
        for product in products:
            if product.get("found_name"):
                # Приводим к единому формату
                product_for_db = {
                    "name": product["found_name"],
                    "protein": product.get("protein", 0),
                    "fat": product.get("fat", 0),
                    "carbohydrates": product.get("carbs", product.get("carbohydrates", 0)),
                    "calories": product.get("calories", 0),
                    "quantity": product.get("quantity", 1.0),
                    "unit": product.get("unit", "г"),
                    "confidence": product.get("confidence", "medium")
                }
                products_to_save.append(product_for_db)
                
                if product.get("confidence") == "low":
                    warning_products.append(product_for_db)
            else:
                not_found.append(product)
        
        # Сохраняем все найденные продукты в базу (batch insert)
        if products_to_save:
            user_db.add_meals_batch(user_id, products_to_save)
            logger.info(f"Saved {len(products_to_save)} products for user {user_id}")
        
        # Получаем обновлённую статистику
        stats = user_db.get_today_stats(user_id)
        
        # Формируем ответ пользователю
        response_lines = []
        
        if products_to_save:
            response_lines.append("📋 *Добавлено в дневник:*\n")
            for p in products_to_save:
                quantity_text = f"{p['quantity']:.1f} {p['unit']}" if p['quantity'] != 1 else p['unit']
                warning = " ⚠️" if p.get("confidence") == "low" else ""
                response_lines.append(
                    f"• {p['name']}{warning} — {quantity_text} — {p['calories'] * p['quantity']:.0f} ккал"
                )
            
            response_lines.append("")
            response_lines.append("━━━━━━━━━━━━━━━━━━━━━")
            response_lines.append(
                f"*ИТОГО ЗА СЕГОДНЯ:* 🔥 {stats['calories']:.0f} ккал | "
                f"🥩 {stats['protein']:.1f} г | 🧈 {stats['fat']:.1f} г | 🍚 {stats['carbs']:.1f} г"
            )
        
        if warning_products:
            response_lines.append("")
            response_lines.append("⚠️ *Внимание:* следующие продукты подобраны приблизительно:")
            for p in warning_products:
                response_lines.append(f"• {p['name']} — проверьте точность")
        
        if not_found:
            response_lines.append("")
            response_lines.append("❓ *Не найдено в базе:*")
            for p in not_found:
                response_lines.append(f"• {p.get('user_input', p.get('product_name', '?'))} — {p.get('quantity', 1):.1f} {p.get('unit', 'порция')}")
            response_lines.append("")
            response_lines.append("💡 *Совет:* попробуйте написать название точнее")
        
        # Добавляем подсказки
        response_lines.append("")
        response_lines.append("📝 *Что дальше?*")
        response_lines.append("• Введите ещё один приём пищи")
        response_lines.append("• /stats — посмотреть статистику")
        response_lines.append("• /history — история записей")
        
        await message.answer("\n".join(response_lines), parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        await message.answer(
            "😕 Произошла ошибка при обработке сообщения.\n\n"
            "Попробуйте написать проще или обратитесь позже.",
            parse_mode="Markdown"
        )


async def handle_quantity_input(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод количества (для обратной совместимости,
    когда DeepSeek не использовался)
    """
    quantity_text = message.text.strip()
    data = await state.get_data()
    product = data.get("last_product")
    
    if not product:
        await state.clear()
        await message.answer("❌ Произошла ошибка. Попробуйте ввести продукт заново.")
        return
    
    # Парсим количество
    try:
        import re
        match = re.search(r'(\d+(?:[.,]\d+)?)', quantity_text)
        if match:
            quantity = float(match.group(1).replace(',', '.'))
        else:
            raise ValueError("Не найдено число")
        
        if quantity <= 0:
            raise ValueError("Количество должно быть больше 0")
        
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите корректное количество (например: 150, 2.5, 3 шт)",
            parse_mode="Markdown"
        )
        return
    
    # Добавляем в базу
    product_for_db = {
        "name": product.get("product_name", product.get("name")),
        "protein": product.get("protein", 0),
        "fat": product.get("fat", 0),
        "carbohydrates": product.get("carbohydrates", product.get("carbs", 0)),
        "calories": product.get("calories", 0),
        "quantity": quantity
    }
    
    user_db.add_meals_batch(message.from_user.id, [product_for_db])
    
    # Получаем обновлённую статистику
    stats = user_db.get_today_stats(message.from_user.id)
    
    # Формируем ответ
    response = format_nutrients(product_for_db, quantity)
    response += "\n✅ *Добавлено в дневник!*\n"
    response += format_daily_stats(stats)
    response += "\n\n📝 *Что дальше?*\n"
    response += "• Введите ещё один продукт\n"
    response += "• /stats — посмотреть статистику\n"
    response += "• /history — история записей"
    
    await message.answer(response, parse_mode="Markdown")
    await state.clear()


async def main():
    """Запуск бота"""
    logger.info("🤖 Бот запущен...")
    logger.info(f"Bot token: {BOT_TOKEN[:10]}...")
    
    # Запускаем polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())