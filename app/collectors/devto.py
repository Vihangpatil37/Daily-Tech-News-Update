import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from app.collectors.base import BaseCollector
from app.models import RawItem

TAGS_TO_POLL = [
    {"tag": "ai", "top": "1", "category_hint": "Artificial Intelligence"},
    {"tag": "machinelearning", "top": "1", "category_hint": "Artificial Intelligence"},
    {"tag": "architecture", "top": "1", "category_hint": "Software Architecture"},
    {"tag": "webdev", "top": "1", "category_hint": "Frontend / Web"}
]

class DevToCollector(BaseCollector):

    @property
    def name(self) -> str:
        return "devto"

    async def _fetch_tag(self, tag_info: Dict[str, str], cutoff_time: datetime, seen_ids: set) -> List[RawItem]:
        tag = tag_info["tag"]
        top_param = tag_info["top"]
        cat_hint = tag_info["category_hint"]
        
        url = f"https://dev.to/api/articles?tag={tag}&top={top_param}"
        headers = {"Accept": "application/vnd.forem.api-v1+json"}
        
        response = await self.fetch_with_retry(url, headers=headers)
        if not response:
            return []
            
        try:
            articles = response.json()
        except Exception:
            return []
            
        if not isinstance(articles, list):
            return []
            
        items = []
        for article in articles:
            article_id = article.get("id")
            if article_id and article_id in seen_ids:
                continue

            title = article.get("title", "").strip()
            article_url = article.get("canonical_url", "").strip() or article.get("url", "").strip()
            published_str = article.get("published_at") or article.get("created_at") or ""

            if not title or not article_url or not published_str:
                continue

            try:
                published_dt = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            except ValueError:
                continue

            if published_dt < cutoff_time:
                continue

            description = article.get("description", "").strip()
            if not description:
                body_md = article.get("body_markdown", "").strip()
                description = body_md[:500] if body_md else title

            pos_reactions = float(article.get("positive_reactions_count") or article.get("public_reactions_count") or 0)
            comments_cnt = float(article.get("comments_count") or 0)
            engagement = pos_reactions + (comments_cnt * 2.0)

            if article_id:
                seen_ids.add(article_id)

            items.append(RawItem(
                title=title,
                url=article_url,
                source="Dev.to",
                published_at=published_dt.isoformat(),
                raw_summary=description,
                engagement_score=engagement,
                category_hint=cat_hint
            ))
            
        return items

    async def fetch(self, lookback_hours: int = 24) -> List[RawItem]:
        self.logger.info("Fetching Dev.to top articles (lookback=%d hours)...", lookback_hours)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        seen_ids = set()
        
        tasks = [self._fetch_tag(t, cutoff_time, seen_ids) for t in TAGS_TO_POLL]
        results = await asyncio.gather(*tasks)
        
        raw_items = []
        for res in results:
            raw_items.extend(res)

        self.logger.info("Dev.to collector completed: fetched %d raw items.", len(raw_items))
        return raw_items
