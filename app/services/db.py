import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Tuple
from app.config import DATABASE_PATH

logger = logging.getLogger("tech-agent.db")


def get_db_connection() -> sqlite3.Connection:
    """Connects to the SQLite database, ensuring directory exists."""
    db_path = Path(DATABASE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initializes the database schema if it doesn't exist."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seen_urls (
                    url TEXT PRIMARY KEY,
                    title TEXT,
                    seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            logger.info("Database initialized successfully at %s", DATABASE_PATH)
    except Exception as e:
        logger.error("Failed to initialize database: %s", e)


def is_url_seen(url: str, days: int = 7) -> bool:
    """Checks if a URL was recorded in seen_urls within the last `days` days."""
    if not url:
        return False
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM seen_urls WHERE url = ? AND seen_at >= ?",
                (url.strip(), cutoff)
            )
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error("Error checking URL seen status: %s", e)
        return False


def filter_unseen_items(items: list, days: int = 7) -> list:
    """Filters out items whose URL has been recorded in seen_urls within the last `days` days."""
    if not items:
        return []
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT url FROM seen_urls WHERE seen_at >= ?", (cutoff,))
            seen_set = {row[0] for row in cursor.fetchall()}
            
        unseen = [item for item in items if getattr(item, 'url', '') not in seen_set]
        logger.info("Filtered out %d previously seen URLs, %d remaining.", len(items) - len(unseen), len(unseen))
        return unseen
    except Exception as e:
        logger.error("Error filtering unseen items: %s", e)
        return items


def add_seen_urls(url_title_pairs: List[Tuple[str, str]]) -> None:
    """Adds a list of (url, title) pairs to the seen_urls database."""
    if not url_title_pairs:
        return
    now_str = datetime.now(timezone.utc).isoformat()
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for url, title in url_title_pairs:
                if not url:
                    continue
                cursor.execute(
                    "INSERT OR REPLACE INTO seen_urls (url, title, seen_at) VALUES (?, ?, ?)",
                    (url.strip(), title.strip() if title else "", now_str)
                )
            conn.commit()
            logger.info("Recorded %d URLs into seen_urls table.", len(url_title_pairs))
    except Exception as e:
        logger.error("Failed to insert seen URLs: %s", e)
