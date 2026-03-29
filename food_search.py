import json
import aiohttp
from typing import Dict, List, Optional, Any
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL,
    FOOD_DB_PATH, SEARCH_TEMPERATURE
)

class FoodSearch:
    def __init__(self):
        # Загружаем базу продуктов
        with open(FOOD_DB_PATH, 'r', encoding='utf-8') as f:
            self.food_db = json.load(f)
        print(f"✅ Загружено продуктов: {len(self.food_db)}")
    
    async def parse_and_calculate(self, message: str) -> Dict[str, Any]:
        """
        Отправляет сообщение в DeepSeek и получает структурированный JSON.
        DeepSeek возвращает:
        - список продуктов с количеством
        - итоговые КБЖУ
        - красивый текст для ответа
        """
        
        # Передаём только названия продуктов для поиска (чтобы не перегружать токены)
        product_names = list(self.food_db.keys())
        # Берём первые 3000 для промпта (остальные DeepSeek будет искать по ключевым словам)
        product_sample = "\n".join(product_names[:3000])
        
        prompt = f"""Ты — помощник по учёту питания. У тебя есть база продуктов с КБЖУ.

ВОТ НЕКОТОРЫЕ ПРОДУКТЫ ИЗ БАЗЫ (всего {len(product_names)}):
{product_sample}

Пользователь написал: "{message}"

Твоя задача:
1. Разобрать сообщение на отдельные продукты
2. Для каждого продукта найти наиболее точное соответствие в базе
3. Рассчитать КБЖУ для указанного количества
4. Подсчитать итоги

Верни ТОЛЬКО JSON в указанном формате. НИКАКОГО ТЕКСТА вне JSON.

Формат ответа:
{{
    "products": [
        {{
            "found_name": "точное название из базы (если найдено)",
            "user_input": "что написал пользователь",
            "quantity": число,
            "unit": "г/шт/порция/ложка",
            "protein": число,
            "fat": число,
            "carbs": число,
            "calories": число,
            "confidence": "high/medium/low",
            "note": "примечание, если есть"
        }}
    ],
    "total": {{
        "calories": число,
        "protein": число,
        "fat": число,
        "carbs": число
    }},
    "response_text": "красивый текст для пользователя с эмодзи"
}}

Правила:
- Если продукт не найден в базе, оставь found_name = null
- Для сложных блюд (яичница, бутерброд) разбей на составляющие
- Количество указывай в граммах для весовых продуктов, в штуках для штучных
- В response_text сделай читаемый список продуктов и итоги
"""

        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": "Ты — помощник по учёту питания. Отвечаешь ТОЛЬКО JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": SEARCH_TEMPERATURE,
            "max_tokens": 2000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=45) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"API Error {response.status}: {error_text}")
                        return self._get_error_response(message)
                    
                    result = await response.json()
                    content = result["choices"][0]["message"]["content"]
                    
                    # Очищаем от markdown
                    content = content.strip()
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()
                    
                    parsed = json.loads(content)
                    
                    # Дополняем найденные продукты полными данными из базы
                    for product in parsed.get("products", []):
                        if product.get("found_name") and product["found_name"] in self.food_db:
                            db_data = self.food_db[product["found_name"]]
                            # Если DeepSeek не вернул КБЖУ, берём из базы
                            if product.get("calories", 0) == 0:
                                product["protein"] = db_data["protein"]
                                product["fat"] = db_data["fat"]
                                product["carbs"] = db_data["carbohydrates"]
                                product["calories"] = db_data["calories"]
                    
                    return {
                        "success": True,
                        "data": parsed
                    }
                    
        except Exception as e:
            print(f"Parse error: {e}")
            return self._get_error_response(message)
    
    def _get_error_response(self, message: str) -> Dict:
        """Возвращает ответ при ошибке"""
        return {
            "success": False,
            "data": {
                "response_text": f"""😕 *Не удалось обработать сообщение*

Ваше сообщение: "{message}"

Попробуйте написать проще, например:
• `яблоко 150г`
• `гречка 200г, курица 150`
• `яичница 4 яйца, кофе 2 ложки сахара`

Или просто напишите название продукта."""
            }
        }