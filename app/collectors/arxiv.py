import time
import feedparser
from datetime import datetime, timezone, timedelta
from typing import List

from app.collectors.base import BaseCollector
from app.models import RawItem

ARXIV_API_URL = "http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.CL+OR+cat:cs.LG&sortBy=submittedDate&sortOrder=descending&max_results=30"

class ArxivCollector(BaseCollector):

    @property
    def name(self) -> str:
        return "arxiv"

    async def fetch(self, lookback_hours: int = 24) -> List[RawItem]:
        self.logger.info("Fetching arXiv papers (lookback=%d hours)...", lookback_hours)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        
        response = await self.fetch_with_retry(ARXIV_API_URL)
        if not response:
            return []
            
        feed = feedparser.parse(response.text)
        items = []
        
        if not feed.entries:
            self.logger.warning("arXiv feed parser returned 0 entries.")
            return []
            
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

            title = " ".join(title.split())

            items.append(RawItem(
                title=f"[arXiv] {title}",
                url=link,
                source="arXiv",
                published_at=published_str,
                raw_summary=summary,
                engagement_score=50.0,
                category_hint="AI Research"
            ))

        self.logger.info("arXiv collector completed: fetched %d raw items.", len(items))
        return items
