import logging
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import List
import feedparser
from app.models import RawItem

logger = logging.getLogger("tech-agent.arxiv")

ARXIV_API_URL = "http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.CL+OR+cat:cs.LG&sortBy=submittedDate&sortOrder=descending&max_results=30"


def fetch(lookback_hours: int = 24) -> List[RawItem]:
    """
    Fetches recent arXiv papers in cs.AI, cs.CL, cs.LG categories.
    Guaranteed not to throw unhandled exceptions.
    """
    logger.info("Fetching arXiv papers (lookback=%d hours)...", lookback_hours)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    raw_items: List[RawItem] = []

    try:
        # Use feedparser to robustly handle arXiv Atom XML response
        feed = feedparser.parse(ARXIV_API_URL)

        if feed.entries:
            for entry in feed.entries:
                title = entry.get("title", "").replace("\n", " ").strip()
                link = entry.get("link", "").strip()
                if not title or not link:
                    continue

                published_dt = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published_dt = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)

                if published_dt and published_dt < cutoff_time:
                    continue

                summary = entry.get("summary", "").replace("\n", " ").strip()[:800]
                published_str = published_dt.isoformat() if published_dt else datetime.now(timezone.utc).isoformat()

                # Clean up title whitespace
                title = " ".join(title.split())

                raw_items.append(RawItem(
                    title=f"[arXiv] {title}",
                    url=link,
                    source="arXiv",
                    published_at=published_str,
                    raw_summary=summary,
                    engagement_score=50.0,  # Base weight for recent research papers
                    category_hint="AI Research"
                ))
        else:
            logger.warning("arXiv feed parser returned 0 entries.")

    except Exception as e:
        logger.error("Error fetching arXiv papers: %s", e)

    logger.info("arXiv agent completed: fetched %d raw items.", len(raw_items))
    return raw_items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = fetch(72)
    print(f"Fetched {len(res)} items")
    for r in res[:5]:
        print(f"- {r.title} ({r.url})")
