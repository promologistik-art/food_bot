import json
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, Any
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

class FoodSearch:
    async def parse_and_calculate(self, message: str) -> Dict[str, Any]:
        # Определяем время суток для эмодзи
        hour = datetime.now().hour
        if 6 <= hour < 12:
            time_emoji = "🌅"  # утро
        elif 12 <= hour < 18:
            time_emoji = "☀️"  # день
        elif 18 <= hour < 24:
            time_emoji = "🌙"  # вечер
        else:
            time_emoji = "🌃"  # ночь

        prompt = f"""Ты — профессиональный диетолог-нутрициолог.

Пользователь написал: "{message}"

Твоя задача:
1. Разобрать сообщение на отдельные продукты
2. Для каждого продукта рассчитать КБЖУ на указанный вес
3. Учитывай стандартный вес: 1 яйцо=50г, 1 ложка сахара=10г, 1 яблоко=150г, 1 банан=120г, 1 кусок хлеба=30г
4. Если пользователь указал вес (200г, 150г) — используй его

Верни ТОЛЬКО JSON в этом формате:
{{
    "products": [
        {{
            "name": "название продукта",
            "weight_grams": число,
            "calories": число,
            "protein": число,
            "fat": число,
            "carbs": число
        }}
    ],
    "total": {{
        "calories": число,
        "protein": число,
        "fat": число,
        "carbs": число
    }}
}}

Не используй эмодзи в ответе. Только JSON."""

        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": "Ты — диетолог. Отвечаешь ТОЛЬКО JSON. Не выдумывай цифры. Используй стандартные значения веса."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 2000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{OPENAI_BASE_URL}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=60
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        print(f"API Error: {text}")
                        return {"success": False, "error": "Ошибка API"}
                    
                    result = await response.json()
                    content = result["choices"][0]["message"]["content"]
                    content = content.strip()
                    
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()
                    
                    parsed = json.loads(content)
                    
                    # Формируем красивый ответ с таблицей
                    products = parsed.get("products", [])
                    total = parsed.get("total", {})
                    
                    # Заголовок таблицы
                    table = f"{time_emoji} *Ваш приём пищи:*\n\n"
                    table += "┌──────────────────┬────────┬──────┬──────┬──────┬──────┐\n"
                    table += "│ Продукт          │ Вес    │ К    │ Б    │ Ж    │ У    │\n"
                    table += "├──────────────────┼────────┼──────┼──────┼──────┼──────┤\n"
                    
                    for p in products:
                        name = p.get("name", "")[:16].ljust(16)
                        weight = f"{p.get('weight_grams', 0):.0f}г".ljust(6)
                        cal = f"{p.get('calories', 0):.0f}".ljust(4)
                        prot = f"{p.get('protein', 0):.1f}".ljust(4)
                        fat = f"{p.get('fat', 0):.1f}".ljust(4)
                        carbs = f"{p.get('carbs', 0):.1f}".ljust(4)
                        table += f"│ {name} │ {weight} │ {cal} │ {prot} │ {fat} │ {carbs} │\n"
                    
                    table += "├──────────────────┼────────┼──────┼──────┼──────┼──────┤\n"
                    table += f"│ ИТОГО            │        │ {total.get('calories', 0):.0f} │ {total.get('protein', 0):.1f} │ {total.get('fat', 0):.1f} │ {total.get('carbs', 0):.1f} │\n"
                    table += "└──────────────────┴────────┴──────┴──────┴──────┴──────┘"
                    
                    return {
                        "success": True,
                        "data": parsed,
                        "user_text": table
                    }
                    
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}