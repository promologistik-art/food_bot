import json
import aiohttp
import asyncio
from typing import Dict, List, Optional
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL,
    FOOD_DB_PATH, MAX_CANDIDATES, SEARCH_TEMPERATURE
)

class FoodSearch:
    def __init__(self):
        # Загружаем базу продуктов
        with open(FOOD_DB_PATH, 'r', encoding='utf-8') as f:
            self.food_db = json.load(f)
        self.food_names = list(self.food_db.keys())
        print(f"📦 Загружено продуктов: {len(self.food_names)}")
    
    def find_candidates(self, query: str, limit: int = MAX_CANDIDATES) -> List[Dict]:
        """Находит кандидатов по ключевым словам (синхронно, быстро)"""
        query_lower = query.lower()
        candidates = []
        
        for name, nutrients in self.food_db.items():
            if query_lower in name.lower():
                candidates.append({
                    "name": name,
                    **nutrients
                })
                if len(candidates) >= limit:
                    break
        
        # Если мало кандидатов, ищем по отдельным словам
        if len(candidates) < limit:
            words = query_lower.split()
            for name, nutrients in self.food_db.items():
                if any(word in name.lower() for word in words):
                    candidate = {"name": name, **nutrients}
                    if candidate not in candidates:
                        candidates.append(candidate)
                        if len(candidates) >= limit:
                            break
        
        return candidates[:limit]
    
    async def search_product(self, query: str) -> Optional[Dict]:
        """Ищет продукт через API DeepSeek (асинхронно)"""
        candidates = self.find_candidates(query)
        
        if not candidates:
            return None
        
        # Формируем промпт
        prompt = f"""Ты — помощник для учёта питания. Пользователь хочет узнать КБЖУ продукта.

Пользователь сказал: "{query}"

Вот список возможных продуктов из базы данных:
{json.dumps(candidates, ensure_ascii=False, indent=2)}

Найди наиболее подходящий продукт и верни его данные в строго указанном JSON формате.
Если ни один продукт не подходит, установи "product_name": null.

Ответь ТОЛЬКО JSON без пояснений в формате:
{{
    "product_name": "точное название из базы или null",
    "protein": число,
    "fat": число,
    "carbohydrates": число,
    "calories": число,
    "match_confidence": "high/medium/low",
    "note": "краткое пояснение, если нужно"
}}"""

        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": "Ты — точный помощник по питанию. Отвечаешь только JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": SEARCH_TEMPERATURE,
            "max_tokens": 500
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30) as response:
                    if response.status != 200:
                        print(f"API Error: {response.status}")
                        return self._fallback_search(query, candidates)
                    
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
                    
                    product_data = json.loads(content)
                    
                    if product_data.get("product_name"):
                        # Находим полные данные из базы
                        full_data = self.food_db.get(product_data["product_name"])
                        if full_data:
                            product_data["protein"] = full_data["protein"]
                            product_data["fat"] = full_data["fat"]
                            product_data["carbohydrates"] = full_data["carbohydrates"]
                            product_data["calories"] = full_data["calories"]
                        return product_data
                    else:
                        return self._fallback_search(query, candidates)
                        
        except Exception as e:
            print(f"API Error: {e}")
            return self._fallback_search(query, candidates)
    
    def _fallback_search(self, query: str, candidates: List[Dict]) -> Optional[Dict]:
        """Резервный поиск в случае ошибки API"""
        if not candidates:
            return None
        
        return {
            "product_name": candidates[0]["name"],
            "protein": candidates[0]["protein"],
            "fat": candidates[0]["fat"],
            "carbohydrates": candidates[0]["carbohydrates"],
            "calories": candidates[0]["calories"],
            "match_confidence": "low",
            "note": "Автоматически выбран из-за ошибки API. Проверьте точность."
        }