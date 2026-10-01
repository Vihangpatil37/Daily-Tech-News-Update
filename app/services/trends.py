import collections
import re
from datetime import datetime, timedelta, timezone
import logging
from app.services.db import get_db_connection

logger = logging.getLogger("tech-agent.trends")

STOPWORDS = {"the", "and", "to", "of", "in", "for", "a", "on", "with", "is", "that", "by", "as", "it", "at", "from", "an", "this", "are", "be", "was", "or", "not", "but"}

def detect_trends(items: list) -> list[str]:
    """Identifies 2-3 surging technical topics from current batch and compares with history."""
    if not items:
        return []

    words = []
    for item in items:
        text = f"{getattr(item, 'title', '')} {getattr(item, 'summary', '')}".lower()
        tokens = re.findall(r'\b[a-z]{3,}\b', text)
        words.extend([w for w in tokens if w not in STOPWORDS])
    
    if not words:
        return []

    word_counts = collections.Counter(words)
    current_top = word_counts.most_common(10)
    surging = []

    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT topic, SUM(frequency) FROM historical_topics WHERE recorded_at >= ? GROUP BY topic", (cutoff,))
            historical = dict(cursor.fetchall())
            
            for word, count in current_top:
                hist_count = historical.get(word, 0)
                if count > hist_count:
                    surging.append(word)
                if len(surging) >= 3:
                    break
            
            now_str = datetime.now(timezone.utc).isoformat()
            for word, count in current_top[:5]:
                cursor.execute(
                    "INSERT INTO historical_topics (topic, frequency, recorded_at) VALUES (?, ?, ?)",
                    (word, count, now_str)
                )
            conn.commit()
    except Exception as e:
        logger.error(f"Error detecting trends: {e}")
        surging = [w for w, c in current_top[:3]]

    return surging[:3]
