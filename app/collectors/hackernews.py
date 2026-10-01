import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from app.collectors.base import BaseCollector
from app.models import RawItem

HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{item_id}.json"

class HackerNewsCollector(BaseCollector):

    @property
    def name(self) -> str:
        return "hackernews"

    async def _fetch_single_hn_item(self, story_id: int, cutoff_time: datetime) -> Optional[RawItem]:
        url = HN_ITEM_URL.format(item_id=story_id)
        response = await self.fetch_with_retry(url)
        if not response:
            return None

        try:
            item = response.json()
        except Exception:
            return None

        if not item or item.get("type") != "story":
            return None

        title = item.get("title", "").strip()
        item_url = item.get("url", f"https://news.ycombinator.com/item?id={story_id}").strip()
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
            url=item_url,
            source="Hacker News",
            published_at=published_dt.isoformat(),
            raw_summary=f"Hacker News story with {int(score)} points and {item.get('descendants', 0)} comments.",
            engagement_score=score,
            category_hint=cat_hint
        )

    async def fetch(self, lookback_hours: int = 24) -> List[RawItem]:
        self.logger.info("Fetching Hacker News top stories (lookback=%d hours)...", lookback_hours)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        
        response = await self.fetch_with_retry(HN_TOP_STORIES_URL)
        if not response:
            self.logger.error("Failed to fetch Hacker News top stories list")
            return []

        story_ids = response.json()[:60]  # Top 60 stories
        
        tasks = [self._fetch_single_hn_item(sid, cutoff_time) for sid in story_ids]
        results = await asyncio.gather(*tasks)
        
        raw_items = [res for res in results if res is not None]

        self.logger.info("Hacker News collector completed: fetched %d items.", len(raw_items))
        return raw_items
