import json
import asyncio
import aiohttp
import re
from typing import Dict, Any, List
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, FOOD_DB_PATH

class FoodSearch:
    def __init__(self):
        with open(FOOD_DB_PATH, 'r', encoding='utf-8') as f:
            self.food_db = json.load(f)
        print(f"Загружено продуктов: {len(self.food_db)}")
    
    async def parse_and_calculate(self, message: str) -> Dict[str, Any]:
        """DeepSeek возвращает JSON с продуктами для сохранения и текст для пользователя"""
        
        full_db_json = json.dumps(self.food_db, ensure_ascii=False, indent=2)
        
        prompt = f"""Ты — помощник по учёту питания.

БАЗА ПРОДУКТОВ (КБЖУ на 100 грамм). ИСПОЛЬЗУЙ ТОЛЬКО ЭТИ ДАННЫЕ:
{full_db_json[:15000]}

Пользователь: "{message}"

ПРАВИЛА:
1. Найди каждый продукт в базе. Если точного совпадения нет — выбери максимально похожий.
2. Рассчитай вес:
   - 1 яйцо = 50г
   - 1 кусок хлеба = 30г
   - 1 ложка сахара = 10г
   - 1 яблоко = 150г
   - 1 банан = 120г
   - Если пользователь указал вес (200г, 150г) — используй его.
3. Рассчитай КБЖУ: (значение_из_базы / 100) * вес_в_граммах

Верни ТОЛЬКО JSON в этом формате:
{{
    "products": [
        {{
            "found_name": "название из базы",
            "quantity": число,
            "unit": "шт/г",
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
    "user_text": "КРАТКИЙ текст для пользователя с итогами (без лишней воды)"
}}

Пример user_text:
🥚 Яйцо куриное — 4 шт (200г) — 314 ккал
☕ Кофе чёрный — 1 порция — 2 ккал
🍬 Сахар — 2 ч.л. (20г) — 80 ккал
🍚 Гречневая каша — 200г — 202 ккал
🍗 Куриная грудка — 150г — 170 ккал
🍎 Яблоко — 2 шт (300г) — 156 ккал
━━━━━━━━━━━━━━━━━━━━━
ИТОГО: 924 ккал | Белки: 65г | Жиры: 28г | Углеводы: 110г"""

        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": "Ты — помощник по учёту питания. Отвечаешь ТОЛЬКО JSON. Никакого текста вне JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 3000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{OPENAI_BASE_URL}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=90
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