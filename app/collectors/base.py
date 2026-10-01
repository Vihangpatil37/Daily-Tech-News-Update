import abc
import logging
import asyncio
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import httpx

from app.models import RawItem

class BaseCollector(abc.ABC):
    """
    Abstract base class for all asynchronous news collectors.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"tech-agent.collector.{self.name}")
        self._client: Optional[httpx.AsyncClient] = None

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Name of the collector (e.g., 'hackernews')"""
        pass

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)
        return self._client

    async def close(self):
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def fetch_with_retry(
        self, 
        url: str, 
        method: str = "GET", 
        max_retries: int = 3,
        **kwargs
    ) -> Optional[httpx.Response]:
        """
        Fetch a URL with exponential backoff and retry logic.
        """
        client = await self._get_client()
        attempt = 0
        backoff = 1.0

        while attempt < max_retries:
            try:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                attempt += 1
                if attempt >= max_retries:
                    self.logger.error("Failed to fetch %s after %d attempts: %s", url, max_retries, e)
                    return None
                
                self.logger.warning("Attempt %d failed for %s. Retrying in %.1fs...", attempt, url, backoff)
                await asyncio.sleep(backoff)
                backoff *= 2.0
                
        return None

    @abc.abstractmethod
    async def fetch(self, lookback_hours: int = 24) -> List[RawItem]:
        """
        Fetch items published within the lookback window.
        Must be implemented by subclasses.
        """
        pass
