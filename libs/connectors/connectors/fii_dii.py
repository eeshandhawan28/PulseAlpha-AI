from __future__ import annotations

import logging
from datetime import date
from typing import Any

import httpx
from bs4 import BeautifulSoup
from schemas.connectors import ConnectorError, ConnectorResult

from connectors.base import BaseConnector

logger = logging.getLogger(__name__)

_NSE_URL = "https://www.nseindia.com/api/fiidiiTradeReact"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com/",
}


class FIIDIIConnector(BaseConnector):
    """Fetches FII/DII daily net flows from NSE India via HTML scraping."""

    def __init__(self, as_of_date: date | None = None) -> None:
        super().__init__(
            source_name="nse_fii_dii",
            max_retries=3,
            timeout_seconds=15.0,
        )
        self._as_of_date = as_of_date

    async def _fetch(self, ticker: str) -> dict[str, Any]:
        async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True) as client:
            r = await client.get(_NSE_URL, timeout=self.timeout_seconds)
            r.raise_for_status()
            return self._parse(r.text)

    def _parse(self, html: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            raise ValueError("FII/DII table not found in response")

        data: dict[str, Any] = {}
        for row in table.find_all("tr")[1:]:  # skip header
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 4:
                continue
            cat = cells[0].lower()
            try:
                buy, sell, net = (float(c.replace(",", "")) for c in cells[1:4])
            except ValueError:
                continue
            if "fii" in cat or "fpi" in cat:
                data.update({"fii_buy": buy, "fii_sell": sell, "fii_net": net})
            elif "dii" in cat:
                data.update({"dii_buy": buy, "dii_sell": sell, "dii_net": net})

        if not data:
            raise ValueError("No FII/DII rows parsed from table")
        return data

    async def fetch(self, ticker: str) -> ConnectorResult:
        """Override to convert ValueError from _parse into PARSE_ERROR ConnectorError."""
        if self._as_of_date is not None:
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
            )
        try:
            data = await self._fetch(ticker)
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data=data,
                confidence=1.0 if {"fii_net", "dii_net"}.issubset(data) else 0.5,
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
