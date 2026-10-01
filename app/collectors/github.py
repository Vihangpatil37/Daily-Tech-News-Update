import asyncio
from datetime import datetime, timezone, timedelta
from typing import List
import re
from bs4 import BeautifulSoup

from app.collectors.base import BaseCollector
from app.models import RawItem
from app.config import GITHUB_TOKEN

WATCHLIST_REPOS = [
    "openai/openai-python",
    "anthropic-experimental/anthropic-sdk-python",
    "langchain-ai/langchain",
    "vllm-project/vllm",
    "huggingface/transformers",
    "ollama/ollama"
]

MIN_STARS = 50

class GithubCollector(BaseCollector):

    @property
    def name(self) -> str:
        return "github"

    async def _scrape_trending(self) -> List[RawItem]:
        url = "https://github.com/trending"
        html_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        response = await self.fetch_with_retry(url, headers=html_headers)
        if not response:
            return []
            
        items = []
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
            
            stars_today_elem = article.find(string=re.compile(r'stars today'))
            stars_today_str = stars_today_elem.parent.text.strip() if stars_today_elem else "0"
            stars_today_num = int(re.sub(r'[^0-9]', '', stars_today_str) or 0)
            
            stars_a = article.find("a", href=re.compile(r'/stargazers'))
            total_stars_str = stars_a.text.strip() if stars_a else "0"
            
            if stars_today_num < MIN_STARS:
                continue
            
            title = f"{repo_name}: {description}"
            
            items.append(RawItem(
                title=title,
                url=repo_url,
                source="GitHub Trending",
                published_at=datetime.now(timezone.utc).isoformat(),
                raw_summary=f"Trending today with {stars_today_num} new stars. Total stars: {total_stars_str}. Description: {description}",
                engagement_score=float(stars_today_num),
                category_hint="GitHub Trending"
            ))
            
        return items

    async def _check_release(self, repo_slug: str, cutoff_time: datetime, headers: dict) -> List[RawItem]:
        rel_url = f"https://api.github.com/repos/{repo_slug}/releases/latest"
        response = await self.fetch_with_retry(rel_url, headers=headers)
        if not response:
            return []
            
        try:
            rel_data = response.json()
        except Exception:
            return []
            
        published_str = rel_data.get("published_at", "")
        if not published_str:
            return []
        
        try:
            p_dt = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except ValueError:
            return []
            
        if p_dt < cutoff_time:
            return []

        title = f"{repo_slug} Release {rel_data.get('tag_name')}: {rel_data.get('name') or ''}"
        url = rel_data.get("html_url", f"https://github.com/{repo_slug}/releases")
        body = rel_data.get("body", "")[:800]

        return [RawItem(
            title=title,
            url=url,
            source="GitHub Release",
            published_at=p_dt.isoformat(),
            raw_summary=body,
            engagement_score=150.0,
            category_hint="Developer Tools"
        )]

    async def fetch(self, lookback_hours: int = 24) -> List[RawItem]:
        self.logger.info("Fetching GitHub trending repositories and releases (lookback=%d hours)...", lookback_hours)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        
        api_headers = {"Accept": "application/vnd.github+json"}
        if GITHUB_TOKEN:
            api_headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

        # Run trending and all release checks concurrently
        tasks = [self._scrape_trending()]
        for repo_slug in WATCHLIST_REPOS:
            tasks.append(self._check_release(repo_slug, cutoff_time, api_headers))
            
        results = await asyncio.gather(*tasks)
        
        raw_items = []
        for res in results:
            raw_items.extend(res)

        self.logger.info("GitHub collector completed: fetched %d raw items.", len(raw_items))
        return raw_items
