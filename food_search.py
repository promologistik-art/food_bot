import json
import asyncio
from typing import Dict, List, Any
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, FOOD_DB_PATH, SEARCH_TEMPERATURE

class FoodSearch:
    def __init__(self):
        with open(FOOD_DB_PATH, 'r', encoding='utf-8') as f:
            self.food_db = json.load(f)
        print(f"✅ Загружено продуктов: {len(self.food_db)}")
        
        self.client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL
        )
        
        self.product_names = list(self.food_db.keys())
    
    async def parse_and_calculate(self, message: str) -> Dict[str, Any]:
        """Отправляет сообщение в DeepSeek и получает структурированный ответ"""
        
        product_sample = "\n".join(self.product_names[:300])
        
        prompt = f"""Ты — помощник по учёту питания.

ВОТ НЕКОТОРЫЕ ПРОДУКТЫ ИЗ БАЗЫ (всего {len(self.product_names)}):
{product_sample}

Пользователь написал: "{message}"

Верни ТОЛЬКО JSON в этом формате:
{{
    "products": [
        {{
            "found_name": "точное название из базы или null",
            "user_input": "что написал пользователь",
            "quantity": число,
            "unit": "г/шт/порция",
            "protein": число,
            "fat": число,
            "carbs": число,
            "calories": число,
            "confidence": "high/medium/low"
        }}
    ],
    "total": {{
        "calories": число,
        "protein": число,
        "fat": число,
        "carbs": число
    }}
}}

Правила:
1. Если продукт не в базе, found_name = null
2. Для "яичница" → разбей на "яйцо куриное"
3. Для "бутерброд" → разбей на "хлеб" и то, что внутри
4. Кофе с сахаром → "кофе" и "сахар"
5. quantity: граммы для весовых, штуки для штучных
6. confidence: high (точное совпадение), medium (похожее), low (приблизительно)

Ответь ТОЛЬКО JSON. НИКАКОГО ТЕКСТА!"""

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "Ты — помощник по учёту питания. Отвечаешь только JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=SEARCH_TEMPERATURE,
                    max_tokens=2000
                )
            )
            
            content = response.choices[0].message.content
            content = content.strip()
            
            # Очищаем от markdown
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            parsed = json.loads(content)
            
            # Дополняем данными из базы
            for product in parsed.get("products", []):
                if product.get("found_name") and product["found_name"] in self.food_db:
                    db_data = self.food_db[product["found_name"]]
                    product["protein"] = db_data["protein"]
                    product["fat"] = db_data["fat"]
                    product["carbs"] = db_data["carbohydrates"]
                    product["calories"] = db_data["calories"]
            
            return {"success": True, "data": parsed}
            
        except Exception as e:
            print(f"API Error: {e}")
            return self._get_error_response(message)
    
    def _get_error_response(self, message: str) -> Dict:
        return {
            "success": False,
            "data": {
                "response_text": f"""😕 Не удалось обработать сообщение.

Попробуйте написать проще, например:
• `яблоко 150г`
• `гречка 200г, курица 150`
• `яйцо 2 шт, хлеб 1 кусок`

Или просто напишите название продукта."""
            }
        }