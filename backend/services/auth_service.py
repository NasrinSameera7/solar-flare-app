"""
Database service — Supabase (PostgreSQL) for users & login history
SQLite is kept separately for weather cache only.

Tables managed here:
  - users         : registered accounts
  - login_history : every login event with timestamp + IP
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

import asyncpg
from jose import JWTError, jwt
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# ─── CONFIG ────────────────────────────────────────────────────────────────
SECRET_KEY   = os.getenv("JWT_SECRET_KEY", "solar-sentinel-super-secret-key-change-in-production-2026")
ALGORITHM    = "HS256"
TOKEN_EXPIRE = 60 * 24 * 7   # 7 days in minutes

DATABASE_URL = os.getenv("DATABASE_URL", "")   # Set this on Render!

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ─── CONNECTION POOL ────────────────────────────────────────────────────────
_pool: Optional[asyncpg.Pool] = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        # asyncpg needs postgresql:// not postgres://
        url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        _pool = await asyncpg.create_pool(url, min_size=1, max_size=5, ssl="require")
        logger.info("✅ Connected to Supabase PostgreSQL")
    return _pool

# ─── SCHEMA SETUP ──────────────────────────────────────────────────────────
async def init_users_table():
    """Create tables in Supabase and seed default admin."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Users table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         SERIAL PRIMARY KEY,
                email      TEXT UNIQUE NOT NULL,
                username   TEXT NOT NULL,
                password   TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Login history table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS login_history (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
                email      TEXT NOT NULL,
                username   TEXT NOT NULL,
                ip_address TEXT DEFAULT 'unknown',
                user_agent TEXT DEFAULT '',
                logged_in_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Seed default admin if not exists
        existing = await conn.fetchrow("SELECT id FROM users WHERE email = $1", "admin@solarsentinel.com")
        if not existing:
            hashed = pwd_context.hash("Solar2026!")
            await conn.execute(
                "INSERT INTO users (email, username, password) VALUES ($1, $2, $3)",
                "admin@solarsentinel.com", "Admin", hashed
            )
            logger.info("✅ Default admin seeded: admin@solarsentinel.com / Solar2026!")

# ─── USER CRUD ──────────────────────────────────────────────────────────────
async def get_user_by_email(email: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE email = $1", email)
        return dict(row) if row else None

async def get_user_by_id(user_id: int) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        return dict(row) if row else None

async def create_user(email: str, username: str, password: str) -> dict:
    hashed = pwd_context.hash(password)
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                "INSERT INTO users (email, username, password) VALUES ($1, $2, $3) RETURNING *",
                email, username, hashed
            )
            return dict(row)
        except asyncpg.UniqueViolationError:
            raise ValueError(f"Email already registered: {email}")

async def get_all_users() -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, email, username, created_at FROM users ORDER BY created_at DESC"
        )
        return [dict(r) for r in rows]

# ─── LOGIN HISTORY ──────────────────────────────────────────────────────────
async def record_login(user_id: int, email: str, username: str,
                       ip_address: str = "unknown", user_agent: str = "") -> None:
    """Record a login event in login_history."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO login_history (user_id, email, username, ip_address, user_agent)
               VALUES ($1, $2, $3, $4, $5)""",
            user_id, email, username, ip_address, user_agent[:300]
        )

async def get_login_history(limit: int = 50) -> list:
    """Get all login events, most recent first."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT lh.id, lh.email, lh.username, lh.ip_address,
                      lh.user_agent, lh.logged_in_at, u.id as user_id
               FROM login_history lh
               LEFT JOIN users u ON lh.user_id = u.id
               ORDER BY lh.logged_in_at DESC
               LIMIT $1""",
            limit
        )
        return [dict(r) for r in rows]

async def get_user_login_history(user_id: int, limit: int = 20) -> list:
    """Get login history for a specific user."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, ip_address, user_agent, logged_in_at
               FROM login_history WHERE user_id = $1
               ORDER BY logged_in_at DESC LIMIT $2""",
            user_id, limit
        )
        return [dict(r) for r in rows]

# ─── AUTH HELPERS ────────────────────────────────────────────────────────────
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=TOKEN_EXPIRE))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None

async def authenticate_user(email: str, password: str) -> Optional[dict]:
    user = await get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user["password"]):
        return None
    return user
