import logging
import time
from datetime import datetime, timezone, timedelta
from typing import List
import socket
import requests
import feedparser
from app.models import RawItem

logger = logging.getLogger("tech-agent.blog")

# Configured RSS Feeds with fallback URLs
RSS_FEEDS = [
    {
        "name": "OpenAI Blog",
        "urls": [
            "https://openai.com/news/rss.xml",
            "https://openai.com/index/rss.xml",
            "https://openai.com/blog/rss.xml"
        ],
        "category_hint": "Large Language Models"
    },
    {
        "name": "Anthropic News",
        "urls": [
            "https://www.anthropic.com/news/feed",
            "https://www.anthropic.com/rss.xml"
        ],
        "category_hint": "Artificial Intelligence"
    },
    {
        "name": "Google DeepMind",
        "urls": [
            "https://deepmind.google/blog/rss.xml"
        ],
        "category_hint": "Artificial Intelligence"
    },
    {
        "name": "Hugging Face Blog",
        "urls": [
            "https://huggingface.co/blog/feed.xml"
        ],
        "category_hint": "Artificial Intelligence"
    }
]


def fetch(lookback_hours: int = 24) -> List[RawItem]:
    """
    Fetches blog posts published within lookback_hours from AI company blogs via RSS.
    Guaranteed not to throw unhandled exceptions.
    """
    logger.info("Fetching blog RSS feeds (lookback=%d hours)...", lookback_hours)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    raw_items: List[RawItem] = []

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for feed_info in RSS_FEEDS:
        feed_name = feed_info["name"]
        cat_hint = feed_info.get("category_hint")
        parsed_successfully = False

        for feed_url in feed_info["urls"]:
            try:
                logger.debug("Parsing feed %s at %s", feed_name, feed_url)
                resp = requests.get(feed_url, headers=headers, timeout=5)
                if resp.status_code != 200:
                    continue

                feed = feedparser.parse(resp.content)
                
                if feed.bozo and not feed.entries:
                    continue

                if not feed.entries:
                    continue

                parsed_successfully = True
                items_from_feed = 0

                for entry in feed.entries:
                    title = entry.get("title", "").strip()
                    link = entry.get("link", "").strip()
                    if not title or not link:
                        continue

                    # Parse published date
                    published_dt = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        published_dt = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
                    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                        published_dt = datetime.fromtimestamp(time.mktime(entry.updated_parsed), tz=timezone.utc)

                    # If date parsing failed or within lookback window
                    if published_dt and published_dt < cutoff_time:
                        continue

                    published_str = published_dt.isoformat() if published_dt else datetime.now(timezone.utc).isoformat()
                    summary = entry.get("summary", entry.get("description", "")).strip()

                    raw_items.append(RawItem(
                        title=title,
                        url=link,
                        source=feed_name,
                        published_at=published_str,
                        raw_summary=summary[:1000],
                        engagement_score=100.0,  # Official blogs get high base engagement weight
                        category_hint=cat_hint
                    ))
                    items_from_feed += 1

                logger.info("Successfully fetched %d items from %s (%s)", items_from_feed, feed_name, feed_url)
                break  # Stop trying fallback URLs once one works

            except Exception as e:
                logger.warning("Error fetching RSS feed %s (%s): %s", feed_name, feed_url, e)

        if not parsed_successfully:
            logger.warning("Could not fetch any valid feed for %s", feed_name)

    logger.info("Blog agent completed: fetched %d total raw items.", len(raw_items))
    return raw_items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = fetch(72)
    print(f"Fetched {len(res)} items")
    for r in res[:5]:
        print(f"- [{r.source}] {r.title} ({r.url})")
