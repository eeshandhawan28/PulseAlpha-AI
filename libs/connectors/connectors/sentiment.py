from __future__ import annotations

import asyncio
import logging
from typing import Any

import feedparser

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

    def __init__(self) -> None:
        super().__init__(
            source_name="rss_sentiment",
            max_retries=2,
            timeout_seconds=10.0,
        )

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
                                entry.get("published", "")
                                if hasattr(entry, "get")
                                else ""
                            ),
                        }
                    )
        return {"headlines": headlines, "ticker": ticker}
