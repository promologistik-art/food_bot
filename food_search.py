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

ГЛАВНОЕ ПРАВИЛО:
Если пользователь назвал БЛЮДО (яичница, омлет, борщ, салат, каша, суп), ты должен вернуть ЭТО БЛЮДО ОДНОЙ СТРОКОЙ, а не разбивать на ингредиенты.

Ты обладаешь точными знаниями КБЖУ всех продуктов и блюд. Используй их.

СТАНДАРТНЫЙ ВЕС:
- 1 порция борща = 400г
- 1 порция яичницы из 4 яиц = 220г (200г яйца + 20г масла)
- 1 стакан кефира = 250г
- 1 яблоко = 150г
- 1 банан = 120г

Если пользователь указал вес (200г, 150г) — используй его.

Верни ТОЛЬКО JSON в этом формате:
{{
    "products": [
        {{
            "name": "название продукта или блюда",
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

Не используй эмодзи в ответе. Только JSON."""

        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": "Ты — диетолог. Отвечаешь ТОЛЬКО JSON. Ты точно знаешь КБЖУ всех продуктов и блюд. Если пользователь назвал блюдо — верни его одной строкой."},
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