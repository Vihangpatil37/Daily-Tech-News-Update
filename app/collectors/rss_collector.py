import os
import yaml
import asyncio
from datetime import datetime, timezone, timedelta
import feedparser
from typing import List, Dict

from app.collectors.base import BaseCollector
from app.models import RawItem
from app.config import BASE_DIR

class RssCollector(BaseCollector):
    
    @property
    def name(self) -> str:
        return "rss"

    def _load_sources(self) -> List[Dict]:
        sources_path = BASE_DIR / "sources.yaml"
        if not sources_path.exists():
            self.logger.warning("sources.yaml not found at %s", sources_path)
            return []
        
        try:
            with open(sources_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data.get("rss_feeds", [])
        except Exception as e:
            self.logger.error("Failed to parse sources.yaml: %s", e)
            return []

    async def _fetch_feed(self, source_info: Dict, cutoff_time: datetime) -> List[RawItem]:
        url = source_info.get("url")
        source_name = source_info.get("name", "Unknown RSS")
        category_hint = source_info.get("category_hint", "General")
        
        if not url:
            return []
            
        response = await self.fetch_with_retry(url)
        if not response:
            return []
            
        # Parse the RSS/Atom feed from the response text
        feed = feedparser.parse(response.text)
        items = []
        
        for entry in feed.entries:
            # Attempt to parse date
            published_dt = None
            parsed_time = entry.get('published_parsed') or entry.get('updated_parsed')
            if parsed_time:
                from time import mktime
                published_dt = datetime.fromtimestamp(mktime(parsed_time), tz=timezone.utc)
                    
            if not published_dt:
                continue
                
            if published_dt < cutoff_time:
                continue
                
            summary = ""
            if hasattr(entry, 'summary'):
                summary = entry.summary
            elif hasattr(entry, 'description'):
                summary = entry.description
                
            # Strip excessive HTML if needed, but for now just pass to LLM
            if len(summary) > 2000:
                summary = summary[:2000] + "..."
                
            items.append(RawItem(
                title=entry.get('title', 'Untitled'),
                url=entry.get('link', url),
                source=source_name,
                published_at=published_dt.isoformat(),
                raw_summary=summary,
                engagement_score=1.0,  # Default for RSS feeds
                category_hint=category_hint
            ))
            
        return items

    async def fetch(self, lookback_hours: int = 24) -> List[RawItem]:
        self.logger.info("Fetching RSS feeds (lookback=%d hours)...", lookback_hours)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        sources = self._load_sources()
        
        if not sources:
            return []
            
        tasks = [self._fetch_feed(s, cutoff_time) for s in sources]
        results = await asyncio.gather(*tasks)
        
        raw_items = []
        for res in results:
            raw_items.extend(res)
            
        self.logger.info("RSS collector completed: fetched %d items.", len(raw_items))
        return raw_items
