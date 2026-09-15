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
                registered_at TEXT,
                last_activity_at TEXT,
                last_reminder_at TEXT
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
        
        # Migrations for existing databases
        try:
            await db.execute("ALTER TABLE users ADD COLUMN last_activity_at TEXT")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN last_reminder_at TEXT")
        except Exception:
            pass

        await db.commit()

async def update_user_activity(user_id: int):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET last_activity_at = ? WHERE user_id = ?", (now, user_id))
        await db.commit()

async def get_or_create_user(user_id: int, username: str, full_name: str):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id, username, full_name, balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                await db.execute("UPDATE users SET last_activity_at = ?, username = ?, full_name = ? WHERE user_id = ?", (now, username, full_name, user_id))
                await db.commit()
                return {"user_id": row[0], "username": row[1], "full_name": row[2], "balance": row[3]}
        
        await db.execute(
            "INSERT INTO users (user_id, username, full_name, balance, registered_at, last_activity_at) VALUES (?, ?, ?, 0, ?, ?)",
            (user_id, username, full_name, now, now)
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
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
        
        await db.execute("UPDATE users SET balance = ?, last_activity_at = ? WHERE user_id = ?", (new_balance, now, user_id))
        
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

async def get_all_users():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id, username, full_name, balance FROM users") as cursor:
            rows = await cursor.fetchall()
            return [{"user_id": r[0], "username": r[1], "full_name": r[2], "balance": r[3]} for r in rows]

async def get_inactive_users(days: int = 7):
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            """
            SELECT user_id, username, full_name, balance, last_activity_at, last_reminder_at 
            FROM users 
            WHERE (last_activity_at IS NULL OR last_activity_at <= ?)
              AND (last_reminder_at IS NULL OR last_reminder_at <= ?)
            """,
            (cutoff, cutoff)
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "user_id": r[0],
                    "username": r[1],
                    "full_name": r[2],
                    "balance": r[3],
                    "last_activity_at": r[4],
                    "last_reminder_at": r[5]
                }
                for r in rows
            ]

async def update_user_reminder_time(user_id: int):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET last_reminder_at = ? WHERE user_id = ?", (now, user_id))
        await db.commit()
