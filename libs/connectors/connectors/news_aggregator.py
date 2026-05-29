from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

import feedparser
import httpx
from bs4 import BeautifulSoup
from schemas.connectors import ConnectorError, ConnectorResult

from connectors.base import BaseConnector

logger = logging.getLogger(__name__)

_GNEWS_URL = (
    "https://news.google.com/rss/search"
    "?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
)
_MAX_ARTICLES = 5
_ARTICLE_TIMEOUT = 6.0
_SUMMARY_CHARS = 500

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "en-IN,en;q=0.9",
}

# Priority-ordered CSS selectors to locate article body paragraphs
_ARTICLE_SELECTORS = [
    "article p",
    ".article-body p",
    ".story-body p",
    ".content-body p",
    '[itemprop="articleBody"] p',
    ".articleText p",
    ".article_content p",
    "#article-content p",
    "main p",
]

_KNOWN_NAMES: dict[str, str] = {
    "HDFCBANK": "HDFC Bank",
    "RELIANCE": "Reliance Industries",
    "TCS": "TCS Tata Consultancy",
    "INFY": "Infosys",
    "ICICIBANK": "ICICI Bank",
    "SBIN": "State Bank of India SBI",
    "WIPRO": "Wipro",
    "AXISBANK": "Axis Bank",
    "KOTAKBANK": "Kotak Mahindra Bank",
    "HINDUNILVR": "Hindustan Unilever HUL",
    "BHARTIARTL": "Bharti Airtel",
    "ITC": "ITC Limited",
    "BAJFINANCE": "Bajaj Finance",
    "TITAN": "Titan Company",
    "NESTLEIND": "Nestle India",
    "DRREDDY": "Dr Reddy Laboratories",
    "TATASTEEL": "Tata Steel",
    "TATAMOTORS": "Tata Motors",
    "MARUTI": "Maruti Suzuki",
    "ASIANPAINT": "Asian Paints",
    "ULTRACEMCO": "UltraTech Cement",
    "LT": "Larsen Toubro",
    "ONGC": "ONGC Oil Natural Gas",
    "POWERGRID": "Power Grid Corporation",
    "NTPC": "NTPC Limited",
    "COALINDIA": "Coal India",
}


def _company_name(ticker: str) -> str:
    """Derive a human-readable search term from a ticker symbol."""
    base = ticker.replace(".NS", "").replace(".BO", "").upper()
    return _KNOWN_NAMES.get(base, base)


async def _fetch_article_summary(client: httpx.AsyncClient, url: str) -> str:
    """Fetch an article URL and return the first ~500 chars of body text."""
    try:
        r = await asyncio.wait_for(
            client.get(url, follow_redirects=True, timeout=_ARTICLE_TIMEOUT),
            timeout=_ARTICLE_TIMEOUT + 1.0,
        )
        soup = BeautifulSoup(r.text, "html.parser")
        for selector in _ARTICLE_SELECTORS:
            paras = soup.select(selector)
            if paras:
                text = " ".join(p.get_text(strip=True) for p in paras[:3])
                return text[:_SUMMARY_CHARS]
    except Exception:
        pass  # Slow or broken article — return empty summary, don't fail
    return ""


class NewsAggregatorConnector(BaseConnector):
    """Two-phase news connector.

    Phase 1: Discover article URLs via Google News RSS search.
    Phase 2: Fetch each article page and extract a 2-paragraph summary.
    """

    def __init__(self, as_of_date: date | None = None) -> None:
        super().__init__(
            source_name="news_aggregator",
            max_retries=1,
            timeout_seconds=35.0,
        )
        self._as_of_date = as_of_date

    async def _fetch(self, ticker: str) -> dict[str, Any]:
        company = _company_name(ticker)
        query = f"{company} stock India"
        feed_url = _GNEWS_URL.format(query=query.replace(" ", "+"))

        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(None, feedparser.parse, feed_url)

        entries = feed.entries[: _MAX_ARTICLES + 2]
        if not entries:
            raise ValueError(f"No news entries found for {ticker}")

        async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True) as client:
            summaries = await asyncio.gather(
                *[_fetch_article_summary(client, getattr(e, "link", "") or "") for e in entries[:_MAX_ARTICLES]]
            )

        articles = []
        for entry, summary in zip(entries[:_MAX_ARTICLES], summaries):
            title = getattr(entry, "title", "") or ""
            if not title:
                continue
            source_info = entry.get("source", {})
            source = (
                source_info.get("title", "")
                if isinstance(source_info, dict)
                else ""
            )
            articles.append(
                {
                    "title": title,
                    "summary": summary,
                    "source": source,
                    "url": getattr(entry, "link", "") or "",
                    "published": getattr(entry, "published", "") or "",
                }
            )

        if not articles:
            raise ValueError("No valid articles parsed")
        return {"articles": articles}

    def _confidence(self, data: dict[str, Any]) -> float:
        n = len(data.get("articles", []))
        if n >= 3:
            return 0.8
        if n >= 1:
            return 0.5
        return 0.0

    async def fetch(self, ticker: str) -> ConnectorResult:
        if self._as_of_date is not None:
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={"articles": []},
                confidence=0.0,
            )
        try:
            data = await self._fetch(ticker)
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data=data,
                confidence=self._confidence(data),
            )
        except ValueError as exc:
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(code="NO_RESULTS", message=str(exc)),
            )
        except Exception as exc:
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(code="FETCH_ERROR", message=str(exc)),
            )
