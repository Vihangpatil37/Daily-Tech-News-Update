import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from app.models import RawItem

logger = logging.getLogger("tech-agent.devto")

DEVTO_QUERIES = [
    {"tag": "machinelearning", "top": "1", "category_hint": "Artificial Intelligence"},
    {"tag": "ai", "top": "1", "category_hint": "Artificial Intelligence"},
    {"tag": "programming", "top": "1", "category_hint": "General Developer Buzz"},
    {"tag": "webdev", "top": "1", "category_hint": "Web Development"}
]


def fetch(lookback_hours: int = 24) -> List[RawItem]:
    """
    Fetches top tech & programming articles from Dev.to public API.
    Guaranteed not to throw unhandled exceptions.
    """
    logger.info("Fetching Dev.to top articles (lookback=%d hours)...", lookback_hours)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    raw_items: List[RawItem] = []
    seen_ids = set()

    headers = {"User-Agent": "tech-intel-agent/0.1"}

    for query in DEVTO_QUERIES:
        tag = query["tag"]
        top_param = query["top"]
        cat_hint = query["category_hint"]

        try:
            url = f"https://dev.to/api/articles?tag={tag}&top={top_param}"
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200:
                logger.warning("Dev.to fetch for tag '%s' returned status %d", tag, res.status_code)
                continue

            articles: List[Dict[str, Any]] = res.json()
            if not isinstance(articles, list):
                logger.warning("Dev.to API did not return a list for tag '%s'", tag)
                continue

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

                raw_items.append(RawItem(
                    title=title,
                    url=article_url,
                    source="Dev.to",
                    published_at=published_dt.isoformat(),
                    raw_summary=description,
                    engagement_score=engagement,
                    category_hint=cat_hint
                ))

        except Exception as e:
            logger.error("Error fetching Dev.to articles for tag '%s': %s", tag, e)

    logger.info("Dev.to agent completed: fetched %d raw items.", len(raw_items))
    return raw_items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = fetch(48)
    print(f"Fetched {len(res)} items")
    for r in res[:5]:
        print(f"- [{r.source} - score {r.engagement_score}] {r.title} ({r.url})")
