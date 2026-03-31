import json
import asyncio
import aiohttp
from typing import Dict, Any
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

class FoodSearch:
    async def parse_and_calculate(self, message: str) -> Dict[str, Any]:
        prompt = f"""Ты — профессиональный диетолог-нутрициолог.

Пользователь написал: "{message}"

Твоя задача:
1. Разобрать сообщение на отдельные продукты
2. Для каждого продукта рассчитать КБЖУ, используя ТОЛЬКО свои знания (не выдумывай)
3. Учитывай вес:
   - 1 яйцо = 50г
   - 1 ложка сахара = 10г
   - 1 кусок хлеба = 30г
   - 1 яблоко = 150г
   - 1 банан = 120г
   - Если пользователь указал вес (200г, 150г) — используй его
4. Формула расчёта: калории = (калорийность_на_100г / 100) * вес_в_граммах

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
    }},
    "user_text": "краткий текст для пользователя"
}}

Пример user_text:
Яйцо куриное — 4 шт (200г) — Калории: 314, Белки: 25.4, Жиры: 21.8, Углеводы: 1.4
Кофе чёрный — 1 порция — Калории: 2, Белки: 0, Жиры: 0, Углеводы: 0
Сахар — 2 ч.л. (20г) — Калории: 80, Белки: 0, Жиры: 0, Углеводы: 20
━━━━━━━━━━━━━━━━━━━━━
ИТОГО: 396 ккал | Белки: 25.4г | Жиры: 21.8г | Углеводы: 21.4г

Не используй эмодзи. Будь краток и точен."""

        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": "Ты — диетолог. Отвечаешь ТОЛЬКО JSON. Никакого текста вне JSON. Не выдумывай цифры. Используй только свои знания."},
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
                    return {"success": True, "data": parsed}
                    
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}