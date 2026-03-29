prompt = f"""Ты — умный помощник по учёту питания.

БАЗА ПРОДУКТОВ (реальные КБЖУ на 100г продукта):
{json.dumps(food_sample, ensure_ascii=False, indent=2)[:8000]}

Пользователь: "{message}"

Твоя задача — умный поиск:
1. Понять, что имел в виду пользователь
2. Найти в базе наиболее подходящий продукт
3. ПРАВИЛЬНО пересчитать КБЖУ с учётом веса/количества

ПРАВИЛА УМНОГО ПОИСКА:
- "яичница из 4 яиц" → это 4 шт "яйцо куриное" (1 яйцо ≈ 50г)
- "кофе с 2 ложками сахара" → это "кофе чёрный" + "сахар" (1 ложка ≈ 10г)
- "бутерброд с авокадо" → это "хлеб" (1 кусок ≈ 30г) + "авокадо" (≈ 50г)
- "гречка" → это "гречневая каша"
- "курица" → это "куриная грудка"

ФОРМУЛЫ РАСЧЁТА:
- Для весовых продуктов: (ккал_из_базы / 100) × вес_в_граммах
- Для штучных: (ккал_из_базы / 100) × вес_1_штуки × количество

СТАНДАРТНЫЙ ВЕС:
- 1 яйцо = 50г
- 1 кусок хлеба = 30г
- 1 ложка сахара = 10г
- 1 порция кофе = 200мл
- 1 яблоко = 150г
- 1 банан = 120г

Верни JSON с результатами:
{{
    "products": [
        {{
            "found_name": "название из базы",
            "user_input": "что написал пользователь",
            "quantity": число,
            "unit": "г/шт",
            "weight_grams": число (общий вес в граммах),
            "protein": число (реальный белок),
            "fat": число (реальный жир),
            "carbs": число (реальные углеводы),
            "calories": число (реальные калории)
        }}
    ],
    "total": {{
        "calories": сумма,
        "protein": сумма,
        "fat": сумма,
        "carbs": сумма
    }}
}}

Пример:
"яичница 4 яйца" →
{{
    "products": [
        {{
            "found_name": "яйцо куриное",
            "user_input": "яйца",
            "quantity": 4,
            "unit": "шт",
            "weight_grams": 200,
            "protein": 25.0,
            "fat": 23.0,
            "carbs": 1.4,
            "calories": 314
        }}
    ],
    "total": {{"calories": 314, "protein": 25.0, "fat": 23.0, "carbs": 1.4}}
}}

Теперь разбери сообщение пользователя. Верни ТОЛЬКО JSON!"""

## Вот полный исправленный food_search.py с умным поиском:

```python
import json
import asyncio
from typing import Dict, List, Any
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, FOOD_DB_PATH

class FoodSearch:
    def __init__(self):
        with open(FOOD_DB_PATH, 'r', encoding='utf-8') as f:
            self.food_db = json.load(f)
        print(f"✅ Загружено продуктов: {len(self.food_db)}")
        
        self.client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL
        )
        
        # Подготавливаем базу для передачи в промпт
        self.food_list = []
        for name, nutrients in list(self.food_db.items())[:3000]:  # Ограничиваем для токенов
            self.food_list.append({
                "name": name,
                "calories": nutrients["calories"],
                "protein": nutrients["protein"],
                "fat": nutrients["fat"],
                "carbs": nutrients["carbohydrates"]
            })
    
    async def parse_and_calculate(self, message: str) -> Dict[str, Any]:
        """Умный поиск: DeepSeek парсит, находит в базе и пересчитывает КБЖУ"""
        
        prompt = f"""Ты — умный помощник по учёту питания.

БАЗА ПРОДУКТОВ (КБЖУ на 100г):
{json.dumps(self.food_list, ensure_ascii=False, indent=2)[:10000]}

Пользователь: "{message}"

ПРАВИЛА УМНОГО ПОИСКА:
1. "яичница 4 яйца" → это "яйцо куриное" (1 шт = 50г)
2. "кофе с 2 ложками сахара" → "кофе чёрный" + "сахар" (1 ложка = 10г)
3. "бутерброд с авокадо" → "хлеб" (1 кусок = 30г) + "авокадо" (50г)
4. "гречка" → "гречневая каша"
5. "курица" → "куриная грудка"

СТАНДАРТНЫЙ ВЕС:
- 1 яйцо = 50г
- 1 кусок хлеба = 30г
- 1 ложка сахара = 10г
- 1 порция кофе = 200г
- 1 яблоко = 150г
- 1 банан = 120г

ФОРМУЛА: калории = (ккал_из_базы / 100) × вес_в_граммах

Верни ТОЛЬКО JSON:
{{
    "products": [
        {{
            "found_name": "название из базы",
            "quantity": число,
            "unit": "г/шт",
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

Теперь разбери сообщение."""

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "Ты — умный помощник по учёту питания. Ищешь продукты в базе, пересчитываешь КБЖУ с учётом веса. Отвечаешь только JSON."},
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
            return self._get_error_response(message)
    
    def _get_error_response(self, message: str) -> Dict:
        return {
            "success": False,
            "data": {
                "response_text": f"""😕 Не удалось разобрать сообщение.

Попробуйте:
• `яичница 4 яйца`
• `гречка 200г`
• `кофе с сахаром`
• `бутерброд с авокадо`"""
            }
        }