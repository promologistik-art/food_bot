import json
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, Any
from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

class FoodSearch:
    async def parse_and_calculate(self, message: str) -> Dict[str, Any]:
        hour = datetime.now().hour
        if 6 <= hour < 12:
            time_emoji = "🌅"
        elif 12 <= hour < 18:
            time_emoji = "☀️"
        elif 18 <= hour < 24:
            time_emoji = "🌙"
        else:
            time_emoji = "🌃"

        prompt = f"""Ты — профессиональный диетолог-нутрициолог.

Пользователь написал: "{message}"

ГЛАВНЫЕ ПРАВИЛА (НЕ НАРУШАТЬ):

1. Если пользователь назвал БЛЮДО (яичница, омлет, борщ) — верни ЕГО ОДНОЙ СТРОКОЙ:
   - "яичница из 4 яиц" = 4 яйца (200г) + масло для жарки (20г) = 220г
   - КБЖУ яичницы: 496 ккал, 25.2г белка, 42.0г жира, 1.6г углеводов

2. Если пользователь назвал НАПИТОК С ДОБАВКАМИ ("кофе с 2 ложками сахара"):
   - Верни КАЖДЫЙ компонент ОТДЕЛЬНОЙ строкой
   - "кофе чёрный" и "сахар" как разные продукты
   - 1 ложка сахара = 10г, 40 ккал

3. Пример правильного ответа на "яичница 4 яйца, кофе 2 ложки сахара":
{{
    "products": [
        {{
            "name": "яичница из 4 яиц",
            "weight_grams": 220,
            "calories": 496,
            "protein": 25.2,
            "fat": 42.0,
            "carbs": 1.6
        }},
        {{
            "name": "кофе чёрный",
            "weight_grams": 200,
            "calories": 2,
            "protein": 0.2,
            "fat": 0,
            "carbs": 0.3
        }},
        {{
            "name": "сахар",
            "weight_grams": 20,
            "calories": 80,
            "protein": 0,
            "fat": 0,
            "carbs": 20
        }}
    ],
    "total": {{
        "calories": 578,
        "protein": 25.4,
        "fat": 42.0,
        "carbs": 21.9
    }}
}}

Ты обладаешь точными знаниями КБЖУ всех продуктов и блюд.

Верни ТОЛЬКО JSON. Без пояснений. Без эмодзи."""

        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": "Ты — диетолог. Отвечаешь ТОЛЬКО JSON. Яичница = яйца + масло. Кофе с сахаром = кофе + сахар отдельно. Ты точно знаешь КБЖУ."},
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
                    
                    products = parsed.get("products", [])
                    total = parsed.get("total", {})
                    
                    lines = [f"{time_emoji} Ваш приём пищи:"]
                    lines.append("")
                    
                    for p in products:
                        name = p.get("name", "")
                        weight = p.get("weight_grams", 0)
                        cal = p.get("calories", 0)
                        prot = p.get("protein", 0)
                        fat = p.get("fat", 0)
                        carbs = p.get("carbs", 0)
                        lines.append(f"{name} - {weight}г, К {cal:.0f}, Б {prot:.1f}, Ж {fat:.1f}, У {carbs:.1f}")
                    
                    lines.append("")
                    lines.append(f"ИТОГО: {total.get('calories', 0):.0f} ккал | Б: {total.get('protein', 0):.1f}г | Ж: {total.get('fat', 0):.1f}г | У: {total.get('carbs', 0):.1f}г")
                    
                    return {
                        "success": True,
                        "data": parsed,
                        "user_text": "\n".join(lines)
                    }
                    
        except Exception as e:
            print(f"Error: {e}")
            return {"success": False, "error": str(e)}