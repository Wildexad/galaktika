import aiosqlite
import datetime

DB_NAME = "loyalty.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                balance INTEGER DEFAULT 0,
                registered_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                admin_id INTEGER,
                amount INTEGER,
                description TEXT,
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        await db.commit()

async def get_or_create_user(user_id: int, username: str, full_name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id, username, full_name, balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"user_id": row[0], "username": row[1], "full_name": row[2], "balance": row[3]}
        
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await db.execute(
            "INSERT INTO users (user_id, username, full_name, balance, registered_at) VALUES (?, ?, ?, 0, ?)",
            (user_id, username, full_name, now)
        )
        await db.commit()
        return {"user_id": user_id, "username": username, "full_name": full_name, "balance": 0}

async def get_user_by_id(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id, username, full_name, balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"user_id": row[0], "username": row[1], "full_name": row[2], "balance": row[3]}
        return None

async def update_balance(user_id: int, admin_id: int, amount: int, description: str = "Начисление/списание"):
    async with aiosqlite.connect(DB_NAME) as db:
        # Check current balance
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None, "Пользователь не найден в базе данных."
            current_balance = row[0]
        
        new_balance = current_balance + amount
        if new_balance < 0:
            return None, f"Недостаточно баллов у клиента! Текущий баланс: {current_balance} баллов."
        
        await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await db.execute(
            "INSERT INTO transactions (user_id, admin_id, amount, description, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, admin_id, amount, description, now)
        )
        await db.commit()
        return new_balance, None

async def get_user_transactions(user_id: int, limit: int = 10):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT amount, description, created_at FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [{"amount": r[0], "description": r[1], "created_at": r[2]} for r in rows]
