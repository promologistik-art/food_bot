import json
import aiohttp
import os
from typing import Dict, List, Optional
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL,
    FOOD_DB_PATH, MAX_CANDIDATES, SEARCH_TEMPERATURE, DEBUG
)

class FoodSearch:
    def __init__(self):
        print(f"🔍 Загрузка базы продуктов из: {FOOD_DB_PATH}")
        
        # Проверяем существование файла
        if not os.path.exists(FOOD_DB_PATH):
            raise FileNotFoundError(f"Файл базы не найден: {FOOD_DB_PATH}")
        
        # Загружаем JSON
        try:
            with open(FOOD_DB_PATH, 'r', encoding='utf-8') as f:
                self.food_db = json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка в JSON файле: {e}")
            # Пробуем прочитать первые строки для диагностики
            with open(FOOD_DB_PATH, 'r', encoding='utf-8') as f:
                first_lines = [next(f) for _ in range(5)]
            print(f"Первые строки файла:")
            for line in first_lines:
                print(f"  {line[:100]}")
            raise e
        
        print(f"✅ База загружена! Всего продуктов: {len(self.food_db)}")
        
        # Выводим несколько примеров для проверки
        sample = list(self.food_db.keys())[:5]
        print(f"📝 Примеры: {sample}")
        
        self.food_names = list(self.food_db.keys())
    
    def find_candidates(self, query: str, limit: int = MAX_CANDIDATES) -> List[Dict]:
        """Находит кандидатов по ключевым словам"""
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
        
        # Если мало кандидатов, ищем по словам
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
        """Ищет продукт через API DeepSeek"""
        candidates = self.find_candidates(query)
        
        if not candidates:
            print(f"⚠️ Нет кандидатов для запроса: {query}")
            return None
        
        print(f"🔍 Найдено {len(candidates)} кандидатов для '{query}'")
        
        prompt = f"""Ты — помощник для учёта питания. Пользователь хочет узнать КБЖУ продукта.

Пользователь сказал: "{query}"

Вот список возможных продуктов из базы данных:
{json.dumps(candidates, ensure_ascii=False, indent=2)}

Найди наиболее подходящий продукт и верни JSON.
Если ни один не подходит, установи "product_name": null.

Ответь ТОЛЬКО JSON:
{{
    "product_name": "точное название из базы или null",
    "match_confidence": "high/medium/low",
    "note": "пояснение при необходимости"
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
            "max_tokens": 300
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30) as response:
                    if response.status != 200:
                        print(f"⚠️ API вернул статус {response.status}")
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
                    
                    if product_data.get("product_name") and product_data["product_name"] in self.food_db:
                        # Получаем полные данные из базы
                        full_data = self.food_db[product_data["product_name"]]
                        return {
                            "product_name": product_data["product_name"],
                            "protein": full_data["protein"],
                            "fat": full_data["fat"],
                            "carbohydrates": full_data["carbohydrates"],
                            "calories": full_data["calories"],
                            "match_confidence": product_data.get("match_confidence", "medium"),
                            "note": product_data.get("note", "")
                        }
                    else:
                        return self._fallback_search(query, candidates)
                        
        except Exception as e:
            print(f"⚠️ Ошибка API: {e}")
            return self._fallback_search(query, candidates)
    
    def _fallback_search(self, query: str, candidates: List[Dict]) -> Optional[Dict]:
        """Резервный поиск"""
        if not candidates:
            return None
        
        return {
            "product_name": candidates[0]["name"],
            "protein": candidates[0]["protein"],
            "fat": candidates[0]["fat"],
            "carbohydrates": candidates[0]["carbohydrates"],
            "calories": candidates[0]["calories"],
            "match_confidence": "low",
            "note": "Автоматический выбор"
        }