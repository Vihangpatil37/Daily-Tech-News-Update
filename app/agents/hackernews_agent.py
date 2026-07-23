from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import List
from app.models import RawItem

logger = logging.getLogger("tech-agent.hackernews")

HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{item_id}.json"


def _fetch_single_hn_item(story_id: int, cutoff_time: datetime) -> RawItem | None:
    try:
        item_res = requests.get(HN_ITEM_URL.format(item_id=story_id), timeout=4)
        if item_res.status_code != 200:
            return None
        item = item_res.json()
        if not item or item.get("type") != "story":
            return None

        title = item.get("title", "").strip()
        url = item.get("url", f"https://news.ycombinator.com/item?id={story_id}").strip()
        score = float(item.get("score", 0))
        item_time = item.get("time")

        if not title or not item_time:
            return None

        published_dt = datetime.fromtimestamp(item_time, tz=timezone.utc)
        if published_dt < cutoff_time:
            return None

        title_lower = title.lower()
        cat_hint = "General Developer News"
        if any(k in title_lower for k in ["llm", "gpt", "claude", "gemini", "llama", "deepmind", "openai", "ai", "machine learning", "neural"]):
            cat_hint = "Artificial Intelligence"

        return RawItem(
            title=title,
            url=url,
            source="Hacker News",
            published_at=published_dt.isoformat(),
            raw_summary=f"Hacker News story with {int(score)} points and {item.get('descendants', 0)} comments.",
            engagement_score=score,
            category_hint=cat_hint
        )
    except Exception as e:
        logger.debug("Error fetching HN item %s: %s", story_id, e)
        return None


def fetch(lookback_hours: int = 24) -> List[RawItem]:
    """
    Fetches Hacker News top stories published within lookback_hours concurrently.
    Guaranteed not to crash on network or parsing errors.
    """
    logger.info("Fetching Hacker News top stories (lookback=%d hours)...", lookback_hours)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    raw_items: List[RawItem] = []

    try:
        response = requests.get(HN_TOP_STORIES_URL, timeout=8)
        response.raise_for_status()
        story_ids = response.json()[:60]  # Top 60 stories
    except Exception as e:
        logger.error("Failed to fetch Hacker News top stories list: %s", e)
        return []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(_fetch_single_hn_item, sid, cutoff_time) for sid in story_ids]
        for future in as_completed(futures):
            res = future.result()
            if res:
                raw_items.append(res)

    logger.info("Hacker News agent completed: fetched %d items.", len(raw_items))
    return raw_items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = fetch(48)
    print(f"Fetched {len(res)} items")
    for r in res[:5]:
        print(f"- [{r.engagement_score} pts] {r.title} ({r.url})")
