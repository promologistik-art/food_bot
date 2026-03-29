import json
import asyncio
from typing import Dict, Any
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, FOOD_DB_PATH

class FoodSearch:
    def __init__(self):
        with open(FOOD_DB_PATH, 'r', encoding='utf-8') as f:
            self.food_db = json.load(f)
        print(f"Загружено продуктов: {len(self.food_db)}")
        
        self.client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL
        )
        
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
        prompt = f"""Ты — умный помощник по учёту питания.

БАЗА ПРОДУКТОВ (КБЖУ на 100г):
{json.dumps(self.food_list, ensure_ascii=False, indent=2)[:10000]}

Пользователь: "{message}"

ПРАВИЛА УМНОГО ПОИСКА:
1. "яичница 4 яйца" → "яйцо куриное" (1 шт = 50г)
2. "кофе с 2 ложками сахара" → "кофе чёрный" + "сахар" (1 ложка = 10г)
3. "бутерброд с авокадо" → "хлеб" (1 кусок = 30г) + "авокадо" (50г)

СТАНДАРТНЫЙ ВЕС:
- 1 яйцо = 50г
- 1 кусок хлеба = 30г
- 1 ложка сахара = 10г
- 1 порция кофе = 200г

ФОРМУЛА: калории = (ккал_из_базы / 100) × вес_в_граммах

Верни ТОЛЬКО JSON:
{
    "products": [
        {
            "found_name": "название из базы",
            "quantity": число,
            "unit": "г/шт",
            "weight_grams": число,
            "calories": число,
            "protein": число,
            "fat": число,
            "carbs": число
        }
    ],
    "total": {
        "calories": число,
        "protein": число,
        "fat": число,
        "carbs": число
    }
}"""

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "Ты — умный помощник по учёту питания. Отвечаешь только JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=2000
                )
            )
            
            content = response.choices[0].message.content
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
            return {
                "success": False,
                "data": {
                    "response_text": "Не удалось разобрать сообщение. Попробуйте написать проще."
                }
            }