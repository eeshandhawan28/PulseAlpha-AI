from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

import feedparser
from schemas.connectors import ConnectorResult

from connectors.base import BaseConnector

logger = logging.getLogger(__name__)

_FEEDS = [
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://www.moneycontrol.com/rss/business.xml",
]


class SentimentConnector(BaseConnector):
    """Fetches news headlines from RSS feeds and filters by ticker keyword.

    Returns raw headlines only — NLP scoring added in Phase 4.
    Cache TTL recommendation: 5-30 minutes.
    """

    def __init__(self, as_of_date: date | None = None) -> None:
        super().__init__(
            source_name="rss_sentiment",
            max_retries=2,
            timeout_seconds=10.0,
        )
        self._as_of_date = as_of_date

    async def fetch(self, ticker: str) -> ConnectorResult:
        if self._as_of_date is not None:
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={"headlines": [], "ticker": ticker},
                confidence=0.0,
            )
        return await super().fetch(ticker)

    async def _fetch(self, ticker: str) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        base = ticker.replace(".NS", "").replace(".BO", "").upper()
        headlines: list[dict[str, str]] = []
        for url in _FEEDS:
            feed = await loop.run_in_executor(None, feedparser.parse, url)
            for entry in feed.entries[:20]:
                title = getattr(entry, "title", "")
                if base in title.upper():
                    headlines.append(
                        {
                            "title": title,
                            "url": getattr(entry, "link", ""),
                            "published": (
                                entry.get("published", "") if hasattr(entry, "get") else ""
                            ),
                        }
                    )
        return {"headlines": headlines, "ticker": ticker}
