import sqlite3
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional
from config import USER_DB_PATH, TRIAL_DAYS

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
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id INTEGER PRIMARY KEY,
                is_active BOOLEAN DEFAULT 1,
                trial_end DATE,
                paid_until DATE,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
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
                weight_grams REAL DEFAULT 100,
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
    
    def get_or_create_user(self, user_id: int, username: str = None, first_name: str = None) -> tuple:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        
        is_new = False
        if not user:
            cursor.execute(
                "INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user_id, username, first_name)
            )
            trial_end = (datetime.now() + timedelta(days=TRIAL_DAYS)).date().isoformat()
            cursor.execute(
                "INSERT INTO subscriptions (user_id, trial_end) VALUES (?, ?)",
                (user_id, trial_end)
            )
            self.conn.commit()
            is_new = True
        
        return user, is_new
    
    def get_subscription_status(self, user_id: int) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT is_active, trial_end, paid_until FROM subscriptions WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            return {"is_active": True, "trial_end": None, "paid_until": None, "days_left": TRIAL_DAYS}
        
        is_active = row[0]
        trial_end = row[1]
        paid_until = row[2]
        
        today = date.today()
        days_left = 0
        
        if trial_end:
            trial_end_date = date.fromisoformat(trial_end)
            if trial_end_date >= today:
                days_left = (trial_end_date - today).days
        
        if paid_until:
            paid_until_date = date.fromisoformat(paid_until)
            if paid_until_date >= today:
                days_left = max(days_left, (paid_until_date - today).days)
        
        return {
            "is_active": is_active and days_left > 0,
            "trial_end": trial_end,
            "paid_until": paid_until,
            "days_left": days_left
        }
    
    def activate_subscription(self, user_id: int, days: int = 30):
        cursor = self.conn.cursor()
        paid_until = (datetime.now() + timedelta(days=days)).date().isoformat()
        cursor.execute(
            "UPDATE subscriptions SET is_active = 1, paid_until = ? WHERE user_id = ?",
            (paid_until, user_id)
        )
        self.conn.commit()
    
    def add_meal(self, user_id: int, product: Dict[str, Any]):
        cursor = self.conn.cursor()
        
        product_name = product.get("name", "Unknown")
        protein = product.get("protein", 0)
        fat = product.get("fat", 0)
        carbs = product.get("carbs", 0)
        calories = product.get("calories", 0)
        weight_grams = product.get("weight_grams", 100)
        
        cursor.execute('''
            INSERT INTO meals (user_id, product_name, protein, fat, carbohydrates, calories, weight_grams)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, product_name, protein, fat, carbs, calories, weight_grams))
        
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
            protein, fat, carbs, calories,
            protein, fat, carbs, calories
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
            SELECT product_name, protein, fat, carbohydrates, calories, weight_grams, meal_time
            FROM meals
            WHERE user_id = ?
            ORDER BY meal_time DESC
            LIMIT ?
        ''', (user_id, limit))
        rows = cursor.fetchall()
        return [{
            "product_name": row[0],
            "protein": row[1],
            "fat": row[2],
            "carbohydrates": row[3],
            "calories": row[4],
            "weight_grams": row[5],
            "meal_time": row[6]
        } for row in rows]
    
    def clear_today(self, user_id: int):
        cursor = self.conn.cursor()
        today = date.today().isoformat()
        cursor.execute("DELETE FROM meals WHERE user_id = ? AND DATE(meal_time) = ?", (user_id, today))
        cursor.execute("DELETE FROM daily_stats WHERE user_id = ? AND date = ?", (user_id, today))
        self.conn.commit()
    
    def get_all_users(self) -> List[dict]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT u.user_id, u.username, u.first_name, u.created_at,
                   s.trial_end, s.paid_until
            FROM users u
            LEFT JOIN subscriptions s ON u.user_id = s.user_id
            ORDER BY u.created_at DESC
        ''')
        rows = cursor.fetchall()
        return [{
            "user_id": r[0],
            "username": r[1],
            "first_name": r[2],
            "created_at": r[3],
            "trial_end": r[4],
            "paid_until": r[5]
        } for r in rows]
    
    def close(self):
        self.conn.close()