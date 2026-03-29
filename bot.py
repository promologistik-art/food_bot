import logging
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


def format_product_line(product: dict) -> str:
    """Форматирует строку продукта для ответа"""
    if product.get("confidence") == "low":
        warning = " ⚠️"
    else:
        warning = ""
    
    quantity_text = f"{product['quantity']:.1f} {product['unit']}" if product['quantity'] != 1 else f"{product['unit']}"
    
    return f"• {product['found_name'] or product['user_input']}{warning} — {quantity_text} — {product['calories']:.0f} ккал"


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

Просто напишите, что съели — я всё посчитаю!

*Примеры:*
• `яичница 4 яйца, кофе 2 ложки сахара, бутерброд с авокадо`
• `гречка 200г, куриная грудка 150`
• `яблоко 2 шт`
• `борщ 300 мл`

*Команды:*
/stats - статистика за сегодня
/history - последние записи
/clear - очистить статистику
"""
    await message.answer(welcome_text, parse_mode="Markdown")


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Статистика за сегодня"""
    stats = user_db.get_today_stats(message.from_user.id)
    response = f"""
📈 *Статистика за сегодня:*

• 🔥 Калории: {stats['calories']:.0f} ккал
• 🥩 Белки: {stats['protein']:.1f} г
• 🧈 Жиры: {stats['fat']:.1f} г
• 🍚 Углеводы: {stats['carbs']:.1f} г
"""
    await message.answer(response, parse_mode="Markdown")


@dp.message(Command("history"))
async def cmd_history(message: types.Message):
    """История записей"""
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
    """Очистка статистики"""
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data="clear_confirm"),
            InlineKeyboardButton(text="❌ Нет", callback_data="clear_cancel")
        ]
    ])
    await message.answer("⚠️ Вы уверены, что хотите очистить статистику за сегодня?", reply_markup=markup)


@dp.callback_query(lambda c: c.data.startswith("clear_"))
async def handle_clear_callback(callback: types.CallbackQuery):
    if callback.data == "clear_confirm":
        user_db.clear_today(callback.from_user.id)
        await callback.message.edit_text("✅ Статистика за сегодня очищена!")
    else:
        await callback.message.edit_text("❌ Очистка отменена.")
    await callback.answer()


@dp.message()
async def handle_message(message: types.Message):
    """Главный обработчик — всё уходит в DeepSeek"""
    
    user_id = message.from_user.id
    user_text = message.text.strip()
    
    # Отправляем уведомление о наборе
    await bot.send_chat_action(message.chat.id, "typing")
    
    # Отправляем в DeepSeek для парсинга и расчёта
    result = await food_search.parse_and_calculate(user_text)
    
    if not result["success"]:
        await message.answer(result["data"]["response_text"], parse_mode="Markdown")
        return
    
    data = result["data"]
    products = data.get("products", [])
    
    # Сохраняем каждый продукт в базу пользователя
    saved_products = []
    not_found = []
    
    for product in products:
        if product.get("found_name"):
            # Продукт найден в базе — сохраняем
            user_db.add_meal(
                user_id,
                product["found_name"],
                product["protein"],
                product["fat"],
                product["carbs"],
                product["calories"],
                product["quantity"]
            )
            saved_products.append(product)
        else:
            # Продукт не найден — запоминаем
            not_found.append(product)
    
    # Формируем ответ с учётом сохранённых продуктов
    response_lines = []
    
    if saved_products:
        response_lines.append("📋 *Добавлено в дневник:*\n")
        for p in saved_products:
            line = format_product_line(p)
            response_lines.append(line)
        
        response_lines.append("")
        response_lines.append(f"━━━━━━━━━━━━━━━━━━━━━")
        response_lines.append(f"*ИТОГО:* 🔥 {data['total']['calories']:.0f} ккал | 🥩 {data['total']['protein']:.1f} г | 🧈 {data['total']['fat']:.1f} г | 🍚 {data['total']['carbs']:.1f} г")
    
    if not_found:
        response_lines.append("")
        response_lines.append("⚠️ *Не найдено в базе:*")
        for p in not_found:
            response_lines.append(f"• {p['user_input']} — {p['quantity']:.1f} {p['unit']}")
        response_lines.append("")
        response_lines.append("💡 *Совет:* попробуйте написать точнее или добавьте продукт в базу")
    
    if data.get("response_text"):
        response_lines.append("")
        response_lines.append(data["response_text"])
    
    await message.answer("\n".join(response_lines), parse_mode="Markdown")


# Запуск
async def main():
    print("🤖 Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())