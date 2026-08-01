import os
import logging
from datetime import datetime, timedelta
from typing import Optional
from asyncio import get_event_loop
from functools import partial

import psycopg2
import psycopg2.extras
from jose import JWTError, jwt
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# ─── CONFIG ─────────────────────────────────────────────────────────────────
SECRET_KEY   = os.getenv("JWT_SECRET_KEY", "solar-sentinel-super-secret-key-2026")
ALGORITHM    = "HS256"
TOKEN_EXPIRE = 60 * 24 * 7   # 7 days

DATABASE_URL = os.getenv("DATABASE_URL", "")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _bcrypt_safe(password: str) -> str:
    """
    bcrypt only uses the first 72 bytes of a password and raises/warns
    beyond that. Truncate on a UTF-8 byte boundary so we never cut a
    multi-byte character in half.
    """
    pw_bytes = password.encode("utf-8")
    if len(pw_bytes) <= 72:
        return password
    truncated = pw_bytes[:72]
    while truncated:
        try:
            return truncated.decode("utf-8")
        except UnicodeDecodeError:
            truncated = truncated[:-1]
    return ""  # extremely unlikely fallback

# ─── SYNC DB HELPER ──────────────────────────────────────────────────────────
def _run(sql: str, params=None, *, fetch_one=False, fetch_all=False):
    """Sync psycopg2 query — wrapped in executor for async callers."""
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            conn.commit()
            if fetch_one:
                row = cur.fetchone()
                return dict(row) if row else None
            if fetch_all:
                rows = cur.fetchall()
                return [dict(r) for r in rows]
            return None
    finally:
        conn.close()

async def _q(sql: str, params=None, *, fetch_one=False, fetch_all=False):
    """Async wrapper around _run using a thread executor."""
    loop = get_event_loop()
    fn   = partial(_run, sql, params, fetch_one=fetch_one, fetch_all=fetch_all)
    return await loop.run_in_executor(None, fn)

# ─── SCHEMA SETUP ───────────────────────────────────────────────────────────
async def init_users_table():
    """Create tables in Supabase and seed default admin if not present."""
    # Users table
    await _q("""
        CREATE TABLE IF NOT EXISTS users (
            id         SERIAL PRIMARY KEY,
            email      TEXT UNIQUE NOT NULL,
            username   TEXT NOT NULL,
            password   TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Login history table
    await _q("""
        CREATE TABLE IF NOT EXISTS login_history (
            id           SERIAL PRIMARY KEY,
            user_id      INTEGER REFERENCES users(id) ON DELETE CASCADE,
            email        TEXT NOT NULL,
            username     TEXT NOT NULL,
            ip_address   TEXT DEFAULT 'unknown',
            user_agent   TEXT DEFAULT '',
            logged_in_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Seed default admin once
    existing = await _q(
        "SELECT id FROM users WHERE email = %s",
        ("admin@solarsentinel.com",),
        fetch_one=True
    )
    if not existing:
        hashed = pwd_context.hash(_bcrypt_safe("Solar2026!"))
        await _q(
            "INSERT INTO users (email, username, password) VALUES (%s, %s, %s)",
            ("admin@solarsentinel.com", "Admin", hashed)
        )
        logger.info("✅ Default admin seeded: admin@solarsentinel.com / Solar2026!")

# ─── USER CRUD ───────────────────────────────────────────────────────────────
async def get_user_by_email(email: str) -> Optional[dict]:
    return await _q("SELECT * FROM users WHERE email = %s", (email,), fetch_one=True)

async def get_user_by_id(user_id: int) -> Optional[dict]:
    return await _q("SELECT * FROM users WHERE id = %s", (user_id,), fetch_one=True)

async def create_user(email: str, username: str, password: str) -> dict:
    hashed = pwd_context.hash(_bcrypt_safe(password))
    try:
        row = await _q(
            "INSERT INTO users (email, username, password) VALUES (%s, %s, %s) RETURNING *",
            (email, username, hashed),
            fetch_one=True
        )
        return row
    except psycopg2.errors.UniqueViolation:
        raise ValueError(f"Email already registered: {email}")

async def get_all_users() -> list:
    return await _q(
        "SELECT id, email, username, created_at FROM users ORDER BY created_at DESC",
        fetch_all=True
    ) or []

# ─── LOGIN HISTORY ───────────────────────────────────────────────────────────
async def record_login(user_id: int, email: str, username: str,
                        ip_address: str = "unknown", user_agent: str = "") -> None:
    await _q(
        """INSERT INTO login_history (user_id, email, username, ip_address, user_agent)
           VALUES (%s, %s, %s, %s, %s)""",
        (user_id, email, username, ip_address, user_agent[:300])
    )

async def get_login_history(limit: int = 50) -> list:
    return await _q(
        """SELECT id, email, username, ip_address, user_agent, logged_in_at
           FROM login_history ORDER BY logged_in_at DESC LIMIT %s""",
        (limit,),
        fetch_all=True
    ) or []

async def get_user_login_history(user_id: int, limit: int = 10) -> list:
    return await _q(
        """SELECT id, ip_address, user_agent, logged_in_at
           FROM login_history WHERE user_id = %s
           ORDER BY logged_in_at DESC LIMIT %s""",
        (user_id, limit),
        fetch_all=True
    ) or []

# ─── AUTH HELPERS ────────────────────────────────────────────────────────────
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(_bcrypt_safe(plain), hashed)

def create_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire    = datetime.utcnow() + (expires_delta or timedelta(minutes=TOKEN_EXPIRE))
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