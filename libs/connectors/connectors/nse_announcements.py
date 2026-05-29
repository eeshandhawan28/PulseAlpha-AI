from __future__ import annotations

import logging
from datetime import date
from typing import Any

import httpx
from schemas.connectors import ConnectorError, ConnectorResult

from connectors.base import BaseConnector

logger = logging.getLogger(__name__)

_HOME_URL = "https://www.nseindia.com/"
_API_URL = (
    "https://www.nseindia.com/api/corporates-announcements"
    "?index=equities&symbol={symbol}"
)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}


class NSEAnnouncementsConnector(BaseConnector):
    """Fetches recent corporate announcements from NSE India JSON API.

    Requires a two-step HTTP flow: first GET the homepage to obtain session
    cookies, then GET the announcements API using those cookies.
    """

    def __init__(self, as_of_date: date | None = None) -> None:
        super().__init__(
            source_name="nse_announcements",
            max_retries=2,
            timeout_seconds=20.0,
        )
        self._as_of_date = as_of_date

    async def _fetch(self, ticker: str) -> dict[str, Any]:
        symbol = ticker.replace(".NS", "").replace(".BO", "").upper()
        async with httpx.AsyncClient(
            headers=_HEADERS, follow_redirects=True
        ) as client:
            # Step 1: Establish session — NSE checks for cookies
            await client.get(_HOME_URL, timeout=10.0)
            # Step 2: Fetch announcements with session cookies in place
            url = _API_URL.format(symbol=symbol)
            r = await client.get(url, timeout=self.timeout_seconds)
            r.raise_for_status()
            content_type = r.headers.get("content-type", "")
            if "application/json" not in content_type:
                raise ValueError(
                    "NSE returned non-JSON response (rate-limited or geo-blocked)"
                )
            return self._parse(r.json())

    def _parse(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, list):
            raise ValueError("Unexpected NSE response format — expected list")
        announcements = []
        for item in data[:8]:
            subject = item.get("subject") or item.get("desc") or ""
            date_str = item.get("an_dt") or item.get("sort_date") or ""
            category = item.get("desc") or ""
            attachment = item.get("attchmntFile") or ""
            if subject:
                announcements.append(
                    {
                        "date": date_str,
                        "subject": subject,
                        "category": category,
                        "url": (
                            f"https://www.nseindia.com{attachment}"
                            if attachment
                            else ""
                        ),
                    }
                )
        if not announcements:
            raise ValueError("No announcements parsed from NSE response")
        return {"announcements": announcements}

    def _confidence(self, data: dict[str, Any]) -> float:
        n = len(data.get("announcements", []))
        return min(0.9, 0.3 * n) if n else 0.0

    async def fetch(self, ticker: str) -> ConnectorResult:
        if self._as_of_date is not None:
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={"announcements": []},
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
                error=ConnectorError(code="PARSE_ERROR", message=str(exc)),
            )
        except Exception as exc:
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(code="FETCH_ERROR", message=str(exc)),
            )
