from __future__ import annotations

import asyncio
import logging
from typing import Any

from nsetools import Nse
from schemas.connectors import ConnectorError, ConnectorResult

from connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class NSEQuotesConnector(BaseConnector):
    """Live NSE quotes via nsetools.

    Note: NSE may block scrapers — use with retry.
    Ticker format: NSE symbol without .NS suffix (e.g. "RELIANCE", not "RELIANCE.NS").
    """

    def __init__(self) -> None:
        super().__init__(
            source_name="nsetools_quotes",
            max_retries=3,
            timeout_seconds=10.0,
        )
        self._nse = Nse()

    async def _fetch(self, ticker: str) -> dict[str, Any]:
        # Only called when overriding fetch() is not used — not reached in practice
        raise NotImplementedError

    async def fetch(self, ticker: str) -> ConnectorResult:
        """Override fetch() because nsetools returns None (not an exception) for missing tickers."""
        loop = asyncio.get_running_loop()
        try:
            quote = await loop.run_in_executor(None, self._nse.get_quote, ticker)
        except Exception as exc:
            logger.error("NSEQuotesConnector error for %s: %s", ticker, exc)
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(code="FETCH_ERROR", message=str(exc)),
            )

        if not quote:
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(
                    code="NOT_FOUND",
                    message=f"NSE returned no data for {ticker}",
                    retryable=False,
                ),
            )

        data = {
            "name": quote.get("companyName"),
            "last_price": quote.get("lastPrice"),
            "change": quote.get("change"),
            "pct_change": quote.get("pChange"),
            "open": quote.get("open"),
            "day_high": quote.get("dayHigh"),
            "day_low": quote.get("dayLow"),
            "volume": quote.get("totalTradedVolume"),
            "prev_close": quote.get("previousClose"),
        }
        return ConnectorResult(
            source=self.source_name,
            ticker=ticker,
            data=data,
            confidence=self._confidence(data),
        )
