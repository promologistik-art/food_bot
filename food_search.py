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
2. Для каждого продукта рассчитать КБЖУ
3. Учитывай стандартный вес: 1 яйцо=50г, 1 ложка сахара=10г, 1 яблоко=150г, 1 банан=120г
4. Если пользователь указал вес (200г, 150г) — используй его

Верни ТОЛЬКО JSON. Ключи: name, weight_grams, calories, protein, fat, carbs

Пример ответа:
{{
    "products": [
        {{"name": "Яйцо куриное", "weight_grams": 200, "calories": 314, "protein": 25.4, "fat": 21.8, "carbs": 1.4}},
        {{"name": "Кофе чёрный", "weight_grams": 200, "calories": 2, "protein": 0, "fat": 0, "carbs": 0}},
        {{"name": "Сахар", "weight_grams": 20, "calories": 80, "protein": 0, "fat": 0, "carbs": 20}}
    ],
    "total": {{"calories": 396, "protein": 25.4, "fat": 21.8, "carbs": 21.4}},
    "user_text": "Яйцо куриное — 200г — Калории: 314, Белки: 25.4, Жиры: 21.8, Углеводы: 1.4\\nКофе чёрный — 200г — Калории: 2, Белки: 0, Жиры: 0, Углеводы: 0\\nСахар — 20г — Калории: 80, Белки: 0, Жиры: 0, Углеводы: 20\\n━━━━━━━━━━━━━━━━━━━━━\\nИТОГО: 396 ккал | Белки: 25.4г | Жиры: 21.8г | Углеводы: 21.4г"
}}

Не используй эмодзи. Будь краток и точен."""

        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": "Ты — диетолог. Отвечаешь ТОЛЬКО JSON. Не выдумывай цифры."},
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