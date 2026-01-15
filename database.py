import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

# Use DATA_DIR env var for persistent storage (Railway volumes), fallback to local
DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
DB_PATH = DATA_DIR / "pillar_bot.db"


def get_connection():
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database with required tables."""
    conn = get_connection()
    cursor = conn.cursor()

    # Store user preferences and settings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id TEXT PRIMARY KEY,
            settings TEXT DEFAULT '{}',
            last_active TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Store Google OAuth tokens
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS google_tokens (
            user_id TEXT PRIMARY KEY,
            access_token TEXT,
            refresh_token TEXT,
            token_expiry TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Store agenda items for Monday meetings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agenda_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            channel_id TEXT,
            category TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            included_in_doc INTEGER DEFAULT 0
        )
    """)

    # Cache channel summaries to avoid re-processing
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS summary_cache (
            channel_id TEXT,
            period_start TIMESTAMP,
            period_end TIMESTAMP,
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (channel_id, period_start, period_end)
        )
    """)

    conn.commit()
    conn.close()


def save_user_last_active(user_id: str):
    """Update user's last active timestamp."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_settings (user_id, last_active)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET last_active = ?
    """, (user_id, datetime.now(), datetime.now()))
    conn.commit()
    conn.close()


def get_user_last_active(user_id: str) -> Optional[datetime]:
    """Get user's last active timestamp for catch-up feature."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT last_active FROM user_settings WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row["last_active"]:
        return datetime.fromisoformat(row["last_active"])
    return None


def save_google_token(user_id: str, access_token: str, refresh_token: str, expiry: datetime):
    """Save Google OAuth token for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO google_tokens (user_id, access_token, refresh_token, token_expiry)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            access_token = ?,
            refresh_token = ?,
            token_expiry = ?
    """, (user_id, access_token, refresh_token, expiry,
          access_token, refresh_token, expiry))
    conn.commit()
    conn.close()


def get_google_token(user_id: str) -> Optional[Dict]:
    """Get Google OAuth token for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT access_token, refresh_token, token_expiry
        FROM google_tokens WHERE user_id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "access_token": row["access_token"],
            "refresh_token": row["refresh_token"],
            "token_expiry": row["token_expiry"]
        }
    return None


def add_agenda_item(user_id: str, channel_id: str, category: str, content: str):
    """Add an item to the Monday meeting agenda."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO agenda_items (user_id, channel_id, category, content)
        VALUES (?, ?, ?, ?)
    """, (user_id, channel_id, category, content))
    conn.commit()
    conn.close()


def get_pending_agenda_items() -> List[Dict]:
    """Get all agenda items not yet included in a doc."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, channel_id, category, content, created_at
        FROM agenda_items WHERE included_in_doc = 0
        ORDER BY category, created_at
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def mark_agenda_items_included(item_ids: List[int]):
    """Mark agenda items as included in a doc."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executemany(
        "UPDATE agenda_items SET included_in_doc = 1 WHERE id = ?",
        [(item_id,) for item_id in item_ids]
    )
    conn.commit()
    conn.close()


def cache_summary(channel_id: str, period_start: datetime, period_end: datetime, summary: str):
    """Cache a channel summary."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO summary_cache
        (channel_id, period_start, period_end, summary)
        VALUES (?, ?, ?, ?)
    """, (channel_id, period_start, period_end, summary))
    conn.commit()
    conn.close()


def get_cached_summary(channel_id: str, period_start: datetime, period_end: datetime) -> Optional[str]:
    """Get a cached summary if it exists."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT summary FROM summary_cache
        WHERE channel_id = ? AND period_start = ? AND period_end = ?
    """, (channel_id, period_start, period_end))
    row = cursor.fetchone()
    conn.close()
    return row["summary"] if row else None


# Initialize database on import
init_db()
