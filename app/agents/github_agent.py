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

    # 1. Scrape GitHub Trending Page
    try:
        url = "https://github.com/trending"
        html_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=html_headers, timeout=15)
        if response.status_code == 200:
            from bs4 import BeautifulSoup
            import re
            soup = BeautifulSoup(response.content, "html.parser")
            articles = soup.find_all("article", class_="Box-row")
            
            for article in articles:
                h2 = article.find("h2", class_="h3 lh-condensed")
                if not h2: continue
                a = h2.find("a")
                if not a: continue
                
                repo_name = "".join(a.text.split())
                repo_url = "https://github.com" + a["href"]
                
                p = article.find("p", class_="col-9 color-fg-muted my-1 pr-4")
                description = p.text.strip() if p else "No description"
                
                # Extract stars today
                stars_today_elem = article.find(string=re.compile(r'stars today'))
                stars_today_str = stars_today_elem.parent.text.strip() if stars_today_elem else "0"
                stars_today_num = int(re.sub(r'[^0-9]', '', stars_today_str) or 0)
                
                # Extract total stars
                stars_a = article.find("a", href=re.compile(r'/stargazers'))
                total_stars_str = stars_a.text.strip() if stars_a else "0"
                
                if stars_today_num < MIN_STARS:
                    continue
                
                title = f"{repo_name}: {description}"
                
                raw_items.append(RawItem(
                    title=title,
                    url=repo_url,
                    source="GitHub Trending",
                    published_at=datetime.now(timezone.utc).isoformat(),
                    raw_summary=f"Trending today with {stars_today_num} new stars. Total stars: {total_stars_str}. Description: {description}",
                    engagement_score=float(stars_today_num),
                    category_hint="GitHub Trending"
                ))
        else:
            logger.warning("GitHub trending page returned status code %d", response.status_code)
    except Exception as e:
        logger.error("Error scraping trending GitHub repos: %s", e)

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
