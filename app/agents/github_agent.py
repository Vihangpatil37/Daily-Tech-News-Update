import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import List
from app.config import GITHUB_TOKEN
from app.models import RawItem

logger = logging.getLogger("tech-agent.github")

WATCHLIST_REPOS = [
    "openai/openai-python",
    "anthropic-experimental/anthropic-sdk-python",
    "langchain-ai/langchain",
    "vllm-project/vllm",
    "huggingface/transformers",
    "ollama/ollama"
]

MIN_STARS = 50


def fetch(lookback_hours: int = 24) -> List[RawItem]:
    """
    Fetches GitHub trending repos and releases from the last lookback_hours.
    Guaranteed not to throw unhandled exceptions.
    """
    logger.info("Fetching GitHub trending repositories and releases (lookback=%d hours)...", lookback_hours)
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    raw_items: List[RawItem] = []

    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    # 1. Search recently created trending repositories
    try:
        created_date_str = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")
        search_url = f"https://api.github.com/search/repositories?q=created:>{created_date_str}&sort=stars&order=desc&per_page=30"
        
        response = requests.get(search_url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for repo in data.get("items", []):
                stars = float(repo.get("stargazers_count", 0))
                if stars < MIN_STARS:
                    continue

                p_str = repo.get("created_at", "")
                p_dt = datetime.fromisoformat(p_str.replace("Z", "+00:00")) if p_str else datetime.now(timezone.utc)
                
                if p_dt < cutoff_time:
                    continue

                title = f"{repo.get('full_name')}: {repo.get('description') or 'No description'}"
                url = repo.get("html_url", "")

                raw_items.append(RawItem(
                    title=title,
                    url=url,
                    source="GitHub Trending",
                    published_at=p_dt.isoformat(),
                    raw_summary=f"Language: {repo.get('language') or 'N/A'}. Stars: {int(stars)}. Description: {repo.get('description', '')}",
                    engagement_score=stars,
                    category_hint="GitHub Trending"
                ))
        else:
            logger.warning("GitHub repository search API returned status code %d: %s", response.status_code, response.text[:200])

    except Exception as e:
        logger.error("Error fetching trending GitHub repos: %s", e)

    # 2. Check releases for watchlisted AI repos
    for repo_slug in WATCHLIST_REPOS:
        try:
            rel_url = f"https://api.github.com/repos/{repo_slug}/releases/latest"
            rel_res = requests.get(rel_url, headers=headers, timeout=5)
            if rel_res.status_code != 200:
                continue

            rel_data = rel_res.json()
            published_str = rel_data.get("published_at", "")
            if not published_str:
                continue
            
            p_dt = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            if p_dt < cutoff_time:
                continue

            title = f"{repo_slug} Release {rel_data.get('tag_name')}: {rel_data.get('name') or ''}"
            url = rel_data.get("html_url", f"https://github.com/{repo_slug}/releases")
            body = rel_data.get("body", "")[:800]

            raw_items.append(RawItem(
                title=title,
                url=url,
                source="GitHub Release",
                published_at=p_dt.isoformat(),
                raw_summary=body,
                engagement_score=150.0,  # High engagement weight for releases
                category_hint="Developer Tools"
            ))

        except Exception as e:
            logger.debug("Error checking release for %s: %s", repo_slug, e)

    logger.info("GitHub agent completed: fetched %d raw items.", len(raw_items))
    return raw_items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = fetch(72)
    print(f"Fetched {len(res)} items")
    for r in res[:5]:
        print(f"- [{r.source}] {r.title} ({r.url})")
