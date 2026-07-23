import re
import uuid
import logging
from urllib.parse import urlparse
from typing import List, Dict
from rapidfuzz import fuzz
from app.models import RawItem, ConsolidatedItem
from app.services import db

logger = logging.getLogger("tech-agent.dedup")


def _normalize_title(title: str) -> str:
    """Lowercases and strips non-alphanumeric characters for fuzzy comparison."""
    if not title:
        return ""
    # Remove prefix tags like [arXiv] or [Ask HN]
    title = re.sub(r"^\[.*?\]\s*", "", title)
    title = title.lower()
    title = re.sub(r"[^\w\s]", "", title)
    return " ".join(title.split())


def _extract_url_slug(url: str) -> str:
    """Extracts domain and path slug from URL for exact cross-source match."""
    if not url:
        return ""
    parsed = urlparse(url)
    netloc = parsed.netloc.lower().replace("www.", "")
    path = parsed.path.rstrip("/")
    return f"{netloc}{path}"


def deduplicate(items: List[RawItem], enable_cross_day: bool = True, lookback_days: int = 7) -> List[ConsolidatedItem]:
    """
    Deduplicates raw items within the current batch and across past days.
    Clustered items are merged into a ConsolidatedItem.
    """
    if not items:
        return []

    logger.info("Starting deduplication on %d items...", len(items))

    # Step 1: Cross-day deduplication via database seen_urls
    if enable_cross_day:
        items = db.filter_unseen_items(items, days=lookback_days)

    if not items:
        logger.info("No new items remaining after cross-day deduplication.")
        return []

    clusters: List[List[RawItem]] = []

    # Step 2: Intra-batch clustering by domain+slug OR title similarity (>85%)
    for item in items:
        norm_title = _normalize_title(item.title)
        slug = _extract_url_slug(item.url)
        matched_cluster = None

        for cluster in clusters:
            first_item = cluster[0]
            first_norm_title = _normalize_title(first_item.title)
            first_slug = _extract_url_slug(first_item.url)

            # Match criteria 1: Same domain+slug (if slug is not trivial)
            if slug and first_slug and len(slug) > 10 and slug == first_slug:
                matched_cluster = cluster
                break

            # Match criteria 2: Rapidfuzz token sort ratio > 85
            if norm_title and first_norm_title:
                ratio = fuzz.token_sort_ratio(norm_title, first_norm_title)
                if ratio >= 85:
                    matched_cluster = cluster
                    break

        if matched_cluster is not None:
            matched_cluster.append(item)
        else:
            clusters.append([item])

    # Step 3: Merge each cluster into a ConsolidatedItem
    consolidated_items: List[ConsolidatedItem] = []

    for cluster in clusters:
        # Highest engagement score
        max_engagement = max((it.engagement_score for it in cluster), default=0.0)

        # Contributing sources without duplicates
        sources = list(dict.fromkeys(it.source for it in cluster))

        # Earliest published_at date
        earliest_pub = min((it.published_at for it in cluster if it.published_at), default="")

        # Primary item (prefer official blogs or highest engagement)
        primary = max(cluster, key=lambda x: (x.engagement_score, len(x.title)))

        # Combine raw summaries
        combined_summaries = "\n---\n".join(
            f"[{it.source}]: {it.raw_summary}" for it in cluster if it.raw_summary
        )

        cat_hint = next((it.category_hint for it in cluster if it.category_hint), primary.category_hint)

        consolidated_items.append(ConsolidatedItem(
            id=str(uuid.uuid4())[:8],
            title=primary.title,
            url=primary.url,
            sources=sources,
            published_at=earliest_pub,
            raw_summary=combined_summaries,
            engagement_score=max_engagement,
            category_hint=cat_hint
        ))

    logger.info("Deduplication finished: reduced %d raw items to %d consolidated items.", len(items), len(consolidated_items))
    return consolidated_items
