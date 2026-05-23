from __future__ import annotations

import asyncio
import logging
from typing import Any

import yfinance as yf

from connectors.base import BaseConnector

logger = logging.getLogger(__name__)

_KEY_FIELDS = ["pe_ratio", "pb_ratio", "roe", "market_cap", "current_price"]


class FundamentalsConnector(BaseConnector):
    def __init__(self) -> None:
        super().__init__(
            source_name="yfinance_fundamentals",
            max_retries=3,
            timeout_seconds=20.0,
        )

    async def _fetch(self, ticker: str) -> dict[str, Any]:
        loop = asyncio.get_event_loop()
        info: dict[str, Any] = await loop.run_in_executor(
            None, lambda: yf.Ticker(ticker).info
        )
        return self._normalize(info)

    def _normalize(self, info: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": info.get("shortName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "pb_ratio": info.get("priceToBook"),
            "debt_to_equity": info.get("debtToEquity"),
            "roe": info.get("returnOnEquity"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "dividend_yield": info.get("dividendYield"),
            "current_price": info.get("currentPrice"),
            "week_52_high": info.get("fiftyTwoWeekHigh"),
            "week_52_low": info.get("fiftyTwoWeekLow"),
        }

    def _confidence(self, data: dict[str, Any]) -> float:
        filled = sum(1 for f in _KEY_FIELDS if data.get(f) is not None)
        return filled / len(_KEY_FIELDS)
