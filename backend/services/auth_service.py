"""
Authentication Service — JWT + bcrypt
Handles user registration, login, and token verification.
Users are stored in the same SQLite database as the cache.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

import aiosqlite
from jose import JWTError, jwt
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# ─── CONFIG ────────────────────────────────────────────────────────────────
SECRET_KEY    = os.getenv("JWT_SECRET_KEY", "solar-sentinel-super-secret-key-change-in-production-2026")
ALGORITHM     = "HS256"
TOKEN_EXPIRE  = 60 * 24 * 7   # 7 days in minutes
DB_PATH       = "solar_cache.db"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ─── DB HELPERS ────────────────────────────────────────────────────────────
async def init_users_table():
    """Create users table and seed a default admin account."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                email     TEXT    UNIQUE NOT NULL,
                username  TEXT    NOT NULL,
                password  TEXT    NOT NULL,
                created_at TEXT   DEFAULT (datetime('now'))
            )
        """)
        await db.commit()

        # Seed default admin if no users exist
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            count = (await cur.fetchone())[0]

        if count == 0:
            hashed = pwd_context.hash("Solar2026!")
            await db.execute(
                "INSERT INTO users (email, username, password) VALUES (?, ?, ?)",
                ("admin@solarsentinel.com", "Admin", hashed)
            )
            await db.commit()
            logger.info("✅ Default admin user created: admin@solarsentinel.com / Solar2026!")

async def get_user_by_email(email: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE email = ?", (email,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def get_user_by_id(user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def create_user(email: str, username: str, password: str) -> dict:
    hashed = pwd_context.hash(password)
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO users (email, username, password) VALUES (?, ?, ?)",
                (email, username, hashed)
            )
            await db.commit()
            return await get_user_by_email(email)
        except Exception as e:
            raise ValueError(f"Email already registered: {email}") from e

# ─── AUTH HELPERS ──────────────────────────────────────────────────────────
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=TOKEN_EXPIRE))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

async def authenticate_user(email: str, password: str) -> Optional[dict]:
    user = await get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user["password"]):
        return None
    return user
