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
    
    async def parse_and_calculate(self, message: str) -> Dict[str, Any]:
        full_db_json = json.dumps(self.food_db, ensure_ascii=False, indent=2)
        
        prompt = f"""Ты — помощник по учёту питания.

БАЗА ПРОДУКТОВ (КБЖУ на 100 грамм). ЭТО ЕДИНСТВЕННЫЙ ИСТОЧНИК ДАННЫХ:
{full_db_json[:15000]}

Пользователь: "{message}"

ЖЁСТКИЕ ПРАВИЛА (НАРУШЕНИЯ ЗАПРЕЩЕНЫ):
1. НЕ ВЫДУМЫВАЙ продукты. Бери ТОЛЬКО из базы выше.
2. НЕ ВЫДУМЫВАЙ цифры. Бери ТОЛЬКО из базы выше.
3. Если продукта НЕТ в базе — НЕ ПИШИ его.
4. Если точного совпадения нет — выбери МАКСИМАЛЬНО БЛИЗКИЙ из базы.

РАСЧЁТ ВЕСА:
- 1 яйцо = 50г
- 1 кусок хлеба = 30г
- 1 ложка сахара = 10г
- 1 яблоко = 150г
- 1 банан = 120г

ФОРМУЛА: калории = (калории_из_базы / 100) * вес_в_граммах

ТВОЙ ОТВЕТ — ТОЛЬКО ТЕКСТ. ПРИМЕР:
🥚 Яйцо куриное — 4 шт (200г) — 314 ккал
☕ Кофе чёрный — 1 порция — 2 ккал
🍚 Гречневая каша — 200г — 202 ккал

━━━━━━━━━━━━━━━━━━━━━
ИТОГО: 518 ккал | Белки: 32г | Жиры: 23г | Углеводы: 40г

Верни ТОЛЬКО ОТВЕТ. БЕЗ JSON. БЕЗ ПОЯСНЕНИЙ."""

        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": "Ты — помощник по учёту питания. ЗАПРЕЩЕНО выдумывать продукты и цифры. Используй ТОЛЬКО базу данных. Отвечай только текстом, без JSON."},
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
                    timeout=90
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        print(f"API Error: {text}")
                        return {"success": False, "error": "Ошибка API"}
                    
                    result = await response.json()
                    answer = result["choices"][0]["message"]["content"]
                    
                    return {"success": True, "answer": answer}
                    
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}