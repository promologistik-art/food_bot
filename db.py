import sqlite3
from datetime import date
from typing import List, Dict, Any
from config import USER_DB_PATH

class UserDB:
    def __init__(self):
        self.conn = sqlite3.connect(USER_DB_PATH)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_name TEXT,
                protein REAL,
                fat REAL,
                carbohydrates REAL,
                calories REAL,
                quantity REAL DEFAULT 1.0,
                meal_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                user_id INTEGER,
                date DATE,
                total_protein REAL DEFAULT 0,
                total_fat REAL DEFAULT 0,
                total_carbs REAL DEFAULT 0,
                total_calories REAL DEFAULT 0,
                PRIMARY KEY (user_id, date)
            )
        ''')
        self.conn.commit()
    
    def get_or_create_user(self, user_id: int, username: str = None, first_name: str = None):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        if not user:
            cursor.execute(
                "INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user_id, username, first_name)
            )
            self.conn.commit()
        return user
    
    def add_meal(self, user_id: int, product: Dict[str, Any]):
        """Добавляет один приём пищи"""
        cursor = self.conn.cursor()
        
        product_name = product.get("name", "Unknown")
        protein = product.get("protein", 0)
        fat = product.get("fat", 0)
        carbs = product.get("carbs", 0)
        calories = product.get("calories", 0)
        quantity = product.get("weight_grams", 100) / 100  # переводим граммы в сотни грамм
        
        cursor.execute('''
            INSERT INTO meals (user_id, product_name, protein, fat, carbohydrates, calories, quantity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, product_name, protein, fat, carbs, calories, quantity))
        
        self.conn.commit()
        
        today = date.today().isoformat()
        cursor.execute('''
            INSERT INTO daily_stats (user_id, date, total_protein, total_fat, total_carbs, total_calories)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, date) DO UPDATE SET
                total_protein = total_protein + ?,
                total_fat = total_fat + ?,
                total_carbs = total_carbs + ?,
                total_calories = total_calories + ?
        ''', (
            user_id, today,
            protein * quantity, fat * quantity, carbs * quantity, calories * quantity,
            protein * quantity, fat * quantity, carbs * quantity, calories * quantity
        ))
        self.conn.commit()
    
    def get_today_stats(self, user_id: int) -> dict:
        cursor = self.conn.cursor()
        today = date.today().isoformat()
        cursor.execute('''
            SELECT total_protein, total_fat, total_carbs, total_calories
            FROM daily_stats
            WHERE user_id = ? AND date = ?
        ''', (user_id, today))
        row = cursor.fetchone()
        if row:
            return {"protein": row[0] or 0, "fat": row[1] or 0, "carbs": row[2] or 0, "calories": row[3] or 0}
        return {"protein": 0, "fat": 0, "carbs": 0, "calories": 0}
    
    def get_recent_meals(self, user_id: int, limit: int = 10) -> List[dict]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT product_name, protein, fat, carbohydrates, calories, quantity, meal_time
            FROM meals
            WHERE user_id = ?
            ORDER BY meal_time DESC
            LIMIT ?
        ''', (user_id, limit))
        rows = cursor.fetchall()
        return [{"product_name": row[0], "protein": row[1], "fat": row[2], "carbohydrates": row[3], "calories": row[4], "quantity": row[5], "meal_time": row[6]} for row in rows]
    
    def clear_today(self, user_id: int):
        cursor = self.conn.cursor()
        today = date.today().isoformat()
        cursor.execute("DELETE FROM meals WHERE user_id = ? AND DATE(meal_time) = ?", (user_id, today))
        cursor.execute("DELETE FROM daily_stats WHERE user_id = ? AND date = ?", (user_id, today))
        self.conn.commit()
    
    def close(self):
        self.conn.close()