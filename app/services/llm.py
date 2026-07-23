import json
import re
import time
import logging
import requests
from typing import List, Dict, Any, Optional, Tuple
from app.config import GEMINI_API_KEY
from app.models import ConsolidatedItem, ProcessedItem

logger = logging.getLogger("tech-agent.llm")

# Spec Categories
VALID_CATEGORIES = [
    "Artificial Intelligence", "Large Language Models", "GitHub Trending", "AI Research",
    "General Developer Buzz", "Programming Languages", "Web Development", "Technology Companies",
    "Cloud", "Cybersecurity", "Developer Tools", "Mobile Development", "Game Engines",
    "YouTube", "Podcasts", "Engineering Blogs", "Jobs"
]

ITEM_PROMPT = """
You are a senior tech intelligence analyst. Analyze this news item and return ONLY valid JSON matching this schema exactly:
{{
  "headline": "concise headline, max 12 words",
  "summary": "2-3 sentences explaining what happened clearly",
  "why_it_matters": "1-2 sentences on why this is significant for the tech industry",
  "developer_impact": "1-2 sentences on how software developers are affected or what action they should take",
  "importance": "Critical" | "High" | "Medium" | "Low",
  "category": "{category_options}"
}}

Item Title: {title}
Item Source: {sources}
Item Category Hint: {cat_hint}
Raw Details/Summary: {raw_summary}
"""

BATCH_ITEM_PROMPT = """
You are a senior tech intelligence analyst. Analyze the following news items and return ONLY a valid JSON array of objects matching this schema for each item, in the EXACT SAME ORDER as provided.

Schema for each object in the JSON array:
{{
  "headline": "concise headline, max 12 words",
  "summary": "2-3 sentences explaining what happened clearly",
  "why_it_matters": "1-2 sentences on why this is significant for the tech industry",
  "developer_impact": "1-2 sentences on how software developers are affected or what action they should take",
  "importance": "Critical" | "High" | "Medium" | "Low",
  "category": "{category_options}"
}}

Items to analyze:
{items_json_text}
"""

FINAL_SUMMARY_PROMPT = """
You are the Chief Editor of "Tech Intelligence Daily".
Below are today's top tech headlines:
{headlines_text}

Return ONLY valid JSON matching this exact schema:
{{
  "executive_summary": "2-3 sentence high-level executive briefing summarizing today's key themes and major breakthroughs.",
  "learning_recommendation": {{
    "topic": "Key technology/concept developers should study today based on these headlines",
    "reason": "Why this topic is important right now",
    "resources": ["Resource or search query 1", "Resource or search query 2"]
  }}
}}
"""

_last_call_timestamp: float = 0.0
MIN_CALL_INTERVAL: float = 4.5  # Throttle for Gemini 15 RPM free tier limit


def _throttle():
    """Module-level throttle to stay comfortably under Gemini free-tier RPM limit."""
    global _last_call_timestamp
    now = time.time()
    elapsed = now - _last_call_timestamp
    if elapsed < MIN_CALL_INTERVAL:
        sleep_time = MIN_CALL_INTERVAL - elapsed
        logger.debug("Throttling Gemini API call: sleeping for %.2f seconds", sleep_time)
        time.sleep(sleep_time)
    _last_call_timestamp = time.time()


def _is_rate_limit_error(e: Exception) -> bool:
    """Checks if an exception indicates an HTTP 429 or rate limit error."""
    err_str = str(e).lower()
    return "429" in err_str or "quota" in err_str or "resourceexhausted" in err_str or "rate limit" in err_str


def _call_gemini_api(prompt: str) -> Tuple[Optional[str], str]:
    """
    Calls Gemini API via Google SDK or REST fallback with rate-limit throttling and backoff.
    Returns tuple of (response_text, status_reason).
    status_reason: "success" | "no_api_key" | "rate_limited" | "error"
    """
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is not set.")
        return None, "no_api_key"

    backoff_delays = [15, 30]

    for attempt in range(len(backoff_delays) + 1):
        _throttle()
        is_rate_limit = False

        # Method 1: Try google-genai SDK
        try:
            from google import genai
            client = genai.Client(api_key=GEMINI_API_KEY)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            if response and response.text:
                return response.text, "success"
        except Exception as e:
            if _is_rate_limit_error(e):
                is_rate_limit = True
                logger.warning("Gemini google-genai SDK rate limit (429) hit: %s", e)
            else:
                logger.debug("SDK google-genai call failed: %s", e)

        # Method 2: Try google-generativeai SDK fallback
        if not is_rate_limit:
            try:
                import google.generativeai as genai
                genai.configure(api_key=GEMINI_API_KEY)
                model = genai.GenerativeModel("gemini-1.5-flash")
                response = model.generate_content(prompt)
                if response and response.text:
                    return response.text, "success"
            except Exception as e:
                if _is_rate_limit_error(e):
                    is_rate_limit = True
                    logger.warning("Gemini google-generativeai SDK rate limit (429) hit: %s", e)
                else:
                    logger.debug("SDK google-generativeai call failed: %s", e)

        # Method 3: REST API fallback
        models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash"]
        for model_name in models_to_try:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                res = requests.post(url, json=payload, timeout=15)
                if res.status_code == 200:
                    data = res.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return text, "success"
                elif res.status_code == 429:
                    is_rate_limit = True
                    logger.warning("Gemini REST API endpoint %s returned HTTP 429 Rate Limit", model_name)
                    break
                else:
                    logger.debug("REST API call for %s returned status %d", model_name, res.status_code)
            except Exception as e:
                if _is_rate_limit_error(e):
                    is_rate_limit = True
                    logger.warning("Gemini REST API exception: %s", e)
                    break
                logger.debug("REST API call for %s failed: %s", model_name, e)

        if is_rate_limit:
            if attempt < len(backoff_delays):
                delay = backoff_delays[attempt]
                logger.warning("Rate limit (429) detected (attempt %d/%d). Applying exponential backoff of %ds...",
                               attempt + 1, len(backoff_delays) + 1, delay)
                time.sleep(delay)
                continue
            else:
                logger.error("Gemini API rate limit persisted after %d retries.", len(backoff_delays))
                return None, "rate_limited"

    return None, "error"


def _clean_json_response(text: str) -> str:
    """Extracts raw JSON string (object or array) from LLM response markdown block if present."""
    if not text:
        return ""
    text = text.strip()

    match = re.search(r"```(?:json)?\s*([\[\{].*?[\]\}])\s*```", text, re.DOTALL)
    if match:
        return match.group(1)

    first_brace = text.find("{")
    first_bracket = text.find("[")

    start = -1
    end = -1
    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        start = first_brace
        end = text.rfind("}")
    elif first_bracket != -1:
        start = first_bracket
        end = text.rfind("]")

    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    return text


def _build_processed_item_from_dict(data: dict, item: ConsolidatedItem) -> ProcessedItem:
    category = data.get("category", "").strip()
    if category not in VALID_CATEGORIES:
        category = item.category_hint if item.category_hint in VALID_CATEGORIES else "General Developer Buzz"

    importance = data.get("importance", "Medium").strip().capitalize()
    if importance not in ["Critical", "High", "Medium", "Low"]:
        importance = "Medium"

    return ProcessedItem(
        headline=data.get("headline", item.title[:80]),
        summary=data.get("summary", item.raw_summary[:200]),
        why_it_matters=data.get("why_it_matters", "Significant update in tech."),
        developer_impact=data.get("developer_impact", "No immediate breaking changes identified."),
        importance=importance,
        category=category,
        url=item.url,
        sources=item.sources,
        published_at=item.published_at,
        engagement_score=item.engagement_score
    )


def _build_heuristic_fallback(item: ConsolidatedItem, reason: str) -> ProcessedItem:
    logger.warning("LLM summarization unavailable/failed for '%s' (reason: %s). Using heuristic fallback.", item.title, reason)
    cat = item.category_hint if item.category_hint in VALID_CATEGORIES else "General Developer Buzz"
    return ProcessedItem(
        headline=item.title[:80],
        summary=item.raw_summary[:200] or item.title,
        why_it_matters="Relevant update from top tech sources.",
        developer_impact="Review source details for technical specifications.",
        importance="High" if item.pre_score > 40 else "Medium",
        category=cat,
        url=item.url,
        sources=item.sources,
        published_at=item.published_at,
        engagement_score=item.engagement_score
    )


def summarize_item(item: ConsolidatedItem) -> ProcessedItem:
    """Summarizes a single consolidated item via Gemini API with retry logic and fallback."""
    cat_options = ", ".join(VALID_CATEGORIES)
    prompt = ITEM_PROMPT.format(
        category_options=cat_options,
        title=item.title,
        sources=", ".join(item.sources),
        cat_hint=item.category_hint or "General",
        raw_summary=item.raw_summary[:1200]
    )

    raw_resp, reason = _call_gemini_api(prompt)
    if raw_resp:
        cleaned = _clean_json_response(raw_resp)
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return _build_processed_item_from_dict(data, item)
            else:
                reason = "parse_error"
        except json.JSONDecodeError as e:
            logger.warning("JSON decode error for item '%s': %s", item.title, e)
            reason = "parse_error"

    return _build_heuristic_fallback(item, reason)


def summarize_items_batch(items: List[ConsolidatedItem]) -> List[ProcessedItem]:
    """
    Summarizes a list of items (batch) in a single Gemini call.
    If batch call or JSON parsing fails, falls back to per-item summarization for this batch.
    """
    if not items:
        return []

    cat_options = ", ".join(VALID_CATEGORIES)
    formatted_items = []
    for idx, item in enumerate(items, 1):
        formatted_items.append(
            f"Item #{idx}:\n"
            f"Title: {item.title}\n"
            f"Source: {', '.join(item.sources)}\n"
            f"Category Hint: {item.category_hint or 'General'}\n"
            f"Raw Details: {item.raw_summary[:800]}"
        )

    items_json_text = "\n\n".join(formatted_items)
    prompt = BATCH_ITEM_PROMPT.format(category_options=cat_options, items_json_text=items_json_text)

    raw_resp, reason = _call_gemini_api(prompt)
    if raw_resp:
        cleaned = _clean_json_response(raw_resp)
        try:
            data_list = json.loads(cleaned)
            if isinstance(data_list, list) and len(data_list) == len(items):
                results = []
                for item, data in zip(items, data_list):
                    if isinstance(data, dict):
                        results.append(_build_processed_item_from_dict(data, item))
                    else:
                        results.append(_build_heuristic_fallback(item, "invalid_item_format_in_batch"))
                return results
            else:
                logger.warning("Batch LLM response array length mismatch (expected %d, got %s). Falling back to per-item calls.",
                               len(items), len(data_list) if isinstance(data_list, list) else "non-list")
        except json.JSONDecodeError as e:
            logger.warning("Batch JSON decode error: %s. Falling back to per-item calls.", e)
    else:
        logger.warning("Batch LLM call failed (reason: %s). Falling back to per-item calls.", reason)

    # Fallback: per-item calls for this batch
    results = []
    for item in items:
        p_item = summarize_item(item)
        results.append(p_item)
    return results


def batch_summarize_items(items: List[ConsolidatedItem], batch_size: int = 5) -> List[ProcessedItem]:
    """
    Splits items into batches of `batch_size` and processes each batch using `summarize_items_batch`.
    """
    processed: List[ProcessedItem] = []
    for i in range(0, len(items), batch_size):
        chunk = items[i:i + batch_size]
        batch_results = summarize_items_batch(chunk)
        processed.extend(batch_results)
    return processed


def generate_daily_briefing_meta(items: List[ProcessedItem]) -> Dict[str, Any]:
    """
    Generates overall executive summary and learning recommendation for the daily email.
    """
    if not items:
        return {
            "executive_summary": "No major tech updates recorded in the last 24 hours.",
            "learning_recommendation": {
                "topic": "General AI & System Architecture",
                "reason": "Stay updated with core software development principles.",
                "resources": ["https://news.ycombinator.com", "https://arxiv.org"]
            }
        }

    headlines_text = "\n".join(f"- [{it.category}] {it.headline} ({it.importance})" for it in items)
    prompt = FINAL_SUMMARY_PROMPT.format(headlines_text=headlines_text)

    raw_resp, reason = _call_gemini_api(prompt)
    data = None
    if raw_resp:
        cleaned = _clean_json_response(raw_resp)
        try:
            data = json.loads(cleaned)
        except Exception as e:
            logger.warning("Failed to parse overall summary JSON: %s (reason: %s)", e, reason)

    if not data or not isinstance(data, dict):
        top_headlines = [it.headline for it in items if it.importance in ["Critical", "High"]][:3]
        exec_summary = f"Today's briefing covers {len(items)} key developments across AI, research, and developer tools. Top stories include: {'; '.join(top_headlines)}."
        return {
            "executive_summary": exec_summary,
            "learning_recommendation": {
                "topic": "LLM Integration & AI Development",
                "reason": "AI technologies continue to dominate top engineering developments today.",
                "resources": ["Explore latest GitHub trending repos", "Review top arXiv papers"]
            }
        }

    return data
