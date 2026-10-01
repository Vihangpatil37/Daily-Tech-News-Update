import logging
import json
from typing import List, Tuple
from app.models import ConsolidatedItem
from app.services.llm import _call_gemini_api, _clean_json_response

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
    Ranks items using heuristic pre-scoring, intelligent LLM ranking, and selects the top items,
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
    top_60_items = sorted_items[:60]

    if not top_60_items:
        return []

    formatted_items = []
    for idx, item in enumerate(top_60_items, 1):
        formatted_items.append(
            f"Item #{idx}:\n"
            f"Title: {item.title}\n"
            f"Source: {', '.join(item.sources)}\n"
            f"Raw Details: {item.raw_summary[:500]}"
        )
    
    items_json_text = "\n\n".join(formatted_items)
    
    prompt = f"""
You are a senior technical lead. Evaluate the following tech news items and score them strictly on their relevance and impact to software developers.
Return ONLY a valid JSON array of numbers, representing the relevance score (1-10) for each item, in the EXACT SAME ORDER as provided.

Schema:
[score1, score2, ..., scoreN]

Items to analyze:
{{items_json_text}}
""".format(items_json_text=items_json_text)

    raw_resp, reason = _call_gemini_api(prompt)
    
    item_scores: List[Tuple[ConsolidatedItem, float]] = []
    scores_assigned = False

    if raw_resp:
        cleaned = _clean_json_response(raw_resp)
        try:
            scores = json.loads(cleaned)
            if isinstance(scores, list) and len(scores) == len(top_60_items):
                for item, score in zip(top_60_items, scores):
                    item_scores.append((item, float(score)))
                scores_assigned = True
            else:
                logger.warning("Intelligent ranking response mismatch. Using pre_score.")
        except Exception as e:
            logger.warning("Intelligent ranking JSON decode error: %s. Using pre_score.", e)
    else:
        logger.warning("Intelligent ranking LLM call failed (reason: %s). Using pre_score.", reason)
        
    if not scores_assigned:
        for item in top_60_items:
            item_scores.append((item, item.pre_score))

    # Sort by LLM relevance score descending, then by pre-score
    item_scores.sort(key=lambda x: (x[1], x[0].pre_score), reverse=True)
    
    # Extract the sorted items back
    llm_sorted_items = [x[0] for x in item_scores]

    shortlist: List[ConsolidatedItem] = []
    source_counts: dict[str, int] = {}

    for item in llm_sorted_items:
        if len(shortlist) >= max_total:
            break

        # Check source limit constraint (cap GitHub Trending specifically at 3)
        primary_source = item.sources[0] if item.sources else "unknown"
        current_count = source_counts.get(primary_source, 0)
        source_limit = 3 if primary_source == "GitHub Trending" else max_per_source

        if current_count < source_limit:
            shortlist.append(item)
            source_counts[primary_source] = current_count + 1

    logger.info("Shortlisted top %d items (LLM top score: %.1f).",
                len(shortlist),
                item_scores[0][1] if item_scores else 0.0)

    return shortlist
