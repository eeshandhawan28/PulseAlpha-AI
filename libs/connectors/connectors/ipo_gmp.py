from __future__ import annotations

import logging
from typing import Any

import httpx
from bs4 import BeautifulSoup
from schemas.connectors import ConnectorError, ConnectorResult

from connectors.base import BaseConnector

logger = logging.getLogger(__name__)

_IPOWATCH_URL = "https://www.ipowatch.in/ipo-gmp/"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}


class _GmpError(Exception):
    """Internal exception carrying a ConnectorError code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class IPOGMPConnector(BaseConnector):
    """Scrapes ipowatch.in for live IPO GMP data.

    The `ticker` argument to `fetch()` is a company name substring used
    to filter the scraped table — not a stock ticker symbol.
    """

    def __init__(self) -> None:
        super().__init__(source_name="ipo_gmp_ipowatch", max_retries=3, timeout_seconds=15.0)

    async def _fetch(self, ticker: str) -> dict[str, Any]:
        # Not used — fetch() is overridden to handle non-exception None returns
        return {}

    async def fetch(self, ticker: str) -> ConnectorResult:
        try:
            async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True) as client:
                r = await client.get(_IPOWATCH_URL, timeout=self.timeout_seconds)
                r.raise_for_status()
                data = self._parse(r.text, ticker)
        except _GmpError as exc:
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(code=exc.code, message=str(exc), retryable=False),
            )
        except Exception as exc:
            logger.warning("IPOGMPConnector unexpected error for %r: %s", ticker, exc)
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(code="FETCH_ERROR", message=str(exc), retryable=True),
            )
        return ConnectorResult(
            source=self.source_name,
            ticker=ticker,
            data=data,
            confidence=0.9,
        )

    def _parse(self, html: str, query: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            raise _GmpError("PARSE_ERROR", "No GMP table found on ipowatch page")

        for row in table.find_all("tr")[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 6:
                continue
            if query.lower() not in cells[0].lower():
                continue
            try:
                return {
                    "company_name": cells[0],
                    "issue_price": float(cells[1].replace(",", "")),
                    "gmp": float(cells[2].replace(",", "")),
                    "qib_subscription": float(cells[3].replace(",", "").rstrip("x")),
                    "hni_subscription": float(cells[4].replace(",", "").rstrip("x")),
                    "retail_subscription": float(cells[5].replace(",", "").rstrip("x")),
                }
            except (ValueError, IndexError):
                continue

        raise _GmpError("NOT_FOUND", f"No IPO matching {query!r} found in GMP table")
