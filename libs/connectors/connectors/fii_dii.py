from __future__ import annotations

import logging
from datetime import date
from typing import Any

import httpx
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
    """Fetches FII/DII daily net flows from NSE India via JSON API."""

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
            return self._parse(r.json())

    def _parse(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Parse NSE JSON response — each row has category, buyValue, sellValue, netValue."""
        data: dict[str, Any] = {}
        for row in rows:
            cat = row.get("category", "").lower()
            try:
                buy = float(str(row.get("buyValue", "0")).replace(",", ""))
                sell = float(str(row.get("sellValue", "0")).replace(",", ""))
                net = float(str(row.get("netValue", "0")).replace(",", ""))
            except (ValueError, TypeError):
                continue
            if "fii" in cat or "fpi" in cat:
                data.update({"fii_buy": buy, "fii_sell": sell, "fii_net": net})
            elif "dii" in cat:
                data.update({"dii_buy": buy, "dii_sell": sell, "dii_net": net})

        if not data:
            raise ValueError("No FII/DII rows parsed from response")
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
