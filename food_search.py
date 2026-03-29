import json
import asyncio
import aiohttp
from typing import Dict, Any
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, FOOD_DB_PATH

class FoodSearch:
    def __init__(self):
        with open(FOOD_DB_PATH, 'r', encoding='utf-8') as f:
            self.food_db = json.load(f)
        print(f"Загружено продуктов: {len(self.food_db)}")
        
        self.food_list = []
        for name, nutrients in list(self.food_db.items())[:3000]:
            self.food_list.append({
                "name": name,
                "calories": nutrients["calories"],
                "protein": nutrients["protein"],
                "fat": nutrients["fat"],
                "carbs": nutrients["carbohydrates"]
            })
    
    async def parse_and_calculate(self, message: str) -> Dict[str, Any]:
        prompt = f"""Ты — помощник по учёту питания. Твоя задача — разобрать сообщение пользователя и вернуть JSON с продуктами.

БАЗА ПРОДУКТОВ (КБЖУ на 100г):
{json.dumps(self.food_list, ensure_ascii=False, indent=2)[:10000]}

Пользователь: "{message}"

ВАЖНЫЕ ПРАВИЛА:
1. Если пользователь указал вес (например "200г", "150 грамм", "2 шт"), ты ОБЯЗАН использовать этот вес.
2. "200г" = 200 грамм. Не игнорируй это!
3. 1 шт яблока = 150г (если не указан вес)
4. 1 шт яйца = 50г
5. 1 ложка сахара = 10г

ФОРМУЛА РАСЧЁТА:
калории = (калории_из_базы / 100) * вес_в_граммах

ПРИМЕР:
Пользователь: "гречка 200г"
Правильный ответ: {{"found_name": "гречневая каша", "weight_grams": 200, "calories": 202}}
(101 ккал/100г, значит 200г = 202 ккал)

Пользователь: "яичница 4 яйца"
Правильный ответ: {{"found_name": "яйцо куриное", "quantity": 4, "weight_grams": 200, "calories": 314}}

Верни ТОЛЬКО JSON. НИКАКОГО ТЕКСТА.

Формат ответа:
{{
    "products": [
        {{
            "found_name": "название из базы",
            "quantity": 4,
            "unit": "шт",
            "weight_grams": 200,
            "calories": 314,
            "protein": 25.0,
            "fat": 23.0,
            "carbs": 1.4
        }}
    ],
    "total": {{
        "calories": 314,
        "protein": 25.0,
        "fat": 23.0,
        "carbs": 1.4
    }}
}}

Теперь разбери сообщение пользователя. ОБЯЗАТЕЛЬНО учитывай указанный вес!"""

        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": "Ты — помощник по учёту питания. Отвечаешь только JSON. Обязательно используй вес, указанный пользователем."},
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
                        return {"success": False, "data": {"response_text": "Ошибка API"}}
                    
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
            return {"success": False, "data": {"response_text": "Ошибка"}}