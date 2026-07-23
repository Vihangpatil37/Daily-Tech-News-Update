import logging
from typing import List
from app.models import ConsolidatedItem

logger = logging.getLogger("tech-agent.ranking")

HIGH_SIGNAL_KEYWORDS = [
    "release", "launch", "ga", "acquisition", "breach", "cve", "vulnerability",
    "gpt-4", "gpt-5", "claude", "gemini", "llama", "deepmind", "openai", "anthropic",
    "nvidia", "transformer", "agent", "sota", "breakthrough", "benchmark", "open-source",
    "architecture", "reasoning", "multimodal", "fine-tuning", "rag", "eval"
]


def _compute_item_score(item: ConsolidatedItem) -> float:
    """Computes a heuristic importance score for an item before sending to LLM."""
    score = 0.0

    # 1. Base engagement score (capped contribution)
    raw_eng = item.engagement_score
    if "Hacker News" in item.sources or any("r/" in s for s in item.sources):
        # Scale down large upvote numbers (e.g. 500 HN points -> ~25 score)
        score += min(raw_eng * 0.05, 30.0)
    elif "GitHub Trending" in item.sources:
        # Scale stars
        score += min(raw_eng * 0.02, 25.0)
    else:
        # Official blogs / arXiv
        score += min(raw_eng * 0.2, 35.0)

    # 2. Source multiplicity bonus (stories covered by multiple sources are important)
    if len(item.sources) > 1:
        score += (len(item.sources) - 1) * 20.0

    # 3. High signal keyword boost
    title_lower = item.title.lower()
    summary_lower = item.raw_summary.lower()
    
    for kw in HIGH_SIGNAL_KEYWORDS:
        if kw in title_lower:
            score += 10.0
        elif kw in summary_lower:
            score += 3.0

    return round(score, 2)


def rank_and_shortlist(items: List[ConsolidatedItem], max_total: int = 25, max_per_source: int = 6) -> List[ConsolidatedItem]:
    """
    Ranks items using heuristic pre-scoring and selects the top items,
    ensuring diversity across sources.
    """
    if not items:
        return []

    logger.info("Ranking %d consolidated items...", len(items))

    # Calculate pre-scores
    for item in items:
        item.pre_score = _compute_item_score(item)

    # Sort descending by score
    sorted_items = sorted(items, key=lambda x: x.pre_score, reverse=True)

    shortlist: List[ConsolidatedItem] = []
    source_counts: dict[str, int] = {}

    for item in sorted_items:
        if len(shortlist) >= max_total:
            break

        # Check source limit constraint (cap GitHub Trending specifically at 3)
        primary_source = item.sources[0] if item.sources else "unknown"
        current_count = source_counts.get(primary_source, 0)
        source_limit = 3 if primary_source == "GitHub Trending" else max_per_source

        if current_count < source_limit:
            shortlist.append(item)
            source_counts[primary_source] = current_count + 1

    logger.info("Shortlisted top %d items (pre-scores: %.1f to %.1f).",
                len(shortlist),
                shortlist[0].pre_score if shortlist else 0.0,
                shortlist[-1].pre_score if shortlist else 0.0)

    return shortlist
