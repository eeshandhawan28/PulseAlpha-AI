from __future__ import annotations

import asyncio
import logging
from typing import Any

import yfinance as yf

from connectors.base import BaseConnector
from schemas.connectors import ConnectorError, ConnectorResult

logger = logging.getLogger(__name__)

_MIN_ROWS_FOR_FULL_CONFIDENCE = 60


class MarketDataConnector(BaseConnector):
    """Fetches daily OHLCV history for a ticker via yfinance.

    Args:
        period: yfinance period string (default "3mo" ≈ 63 trading days).
    """

    def __init__(self, period: str = "3mo") -> None:
        super().__init__(
            source_name="yfinance_market_data",
        )
        self._period = period

    async def fetch(self, ticker: str) -> ConnectorResult:
        loop = asyncio.get_running_loop()
        try:
            df = await loop.run_in_executor(
                None,
                lambda: yf.Ticker(ticker).history(period=self._period),
            )
        except Exception as exc:
            logger.warning("MarketDataConnector FETCH_ERROR for %s: %s", ticker, exc)
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(code="FETCH_ERROR", message=str(exc), retryable=False),
            )

        if df.empty:
            logger.warning("MarketDataConnector NO_DATA for %s: yfinance returned empty history", ticker)
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(
                    code="NO_DATA",
                    message=f"yfinance returned empty history for {ticker}",
                    retryable=False,
                ),
            )

        records = [
            {
                "date": idx.strftime("%Y-%m-%d"),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]),
            }
            for idx, row in df.iterrows()
        ]

        confidence = min(len(records) / _MIN_ROWS_FOR_FULL_CONFIDENCE, 1.0)

        return ConnectorResult(
            source=self.source_name,
            ticker=ticker,
            data={"ohlcv": records, "ticker": ticker},
            confidence=confidence,
        )

    async def _fetch(self, ticker: str) -> dict[str, Any]:
        # Not used — fetch() is overridden directly.
        raise NotImplementedError
