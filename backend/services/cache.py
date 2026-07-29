import aiosqlite
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
DB_PATH = "space_weather.db"


async def init_db():
    """Initialize SQLite database tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS prediction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                quiet_prob REAL,
                c_class_prob REAL,
                m_class_prob REAL,
                x_class_prob REAL,
                predicted_class TEXT,
                confidence REAL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS flare_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flr_id TEXT UNIQUE,
                begin_time TEXT,
                peak_time TEXT,
                class_type TEXT,
                source_location TEXT,
                active_region INTEGER,
                recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
    logger.info("✅ Database initialized")


async def cache_get(key: str):
    """Get cached value if not expired."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT value, expires_at FROM cache WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                expires_at = datetime.fromisoformat(row[1])
                if datetime.utcnow() < expires_at:
                    return json.loads(row[0])
    return None


async def cache_set(key: str, value, ttl_seconds: int = 300):
    """Set a cache entry with TTL."""
    expires_at = (datetime.utcnow() + timedelta(seconds=ttl_seconds)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
            (key, json.dumps(value), expires_at),
        )
        await db.commit()


async def save_prediction(pred: dict):
    """Save a prediction to the history table."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO prediction_history
            (timestamp, quiet_prob, c_class_prob, m_class_prob, x_class_prob, predicted_class, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.utcnow().isoformat(),
            pred.get("quiet", 0),
            pred.get("c_class", 0),
            pred.get("m_class", 0),
            pred.get("x_class", 0),
            pred.get("predicted_class", "Quiet"),
            pred.get("confidence", 0),
        ))
        await db.commit()


async def get_prediction_history(hours: int = 48) -> list:
    """Get recent prediction history."""
    since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT timestamp, quiet_prob, c_class_prob, m_class_prob, x_class_prob, predicted_class, confidence
            FROM prediction_history
            WHERE timestamp > ?
            ORDER BY timestamp ASC
        """, (since,)) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "timestamp": r[0],
                    "quiet": r[1],
                    "c_class": r[2],
                    "m_class": r[3],
                    "x_class": r[4],
                    "predicted_class": r[5],
                    "confidence": r[6],
                }
                for r in rows
            ]
