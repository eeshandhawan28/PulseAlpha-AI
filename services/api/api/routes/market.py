"""Live market quote endpoint — current price + trend changes via yfinance."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import yfinance as yf
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market", tags=["market"])


def _pct(new: float, old: float) -> float | None:
    if old == 0:
        return None
    return round((new - old) / abs(old) * 100, 2)


def _quote_from_history(ticker: str) -> dict[str, Any]:
    """Fetch 1Y OHLCV history and derive price + trend metrics."""
    t = yf.Ticker(ticker)

    # 1Y history gives us enough for all trend windows
    df = t.history(period="1y")
    if df.empty:
        raise ValueError(f"No price data for {ticker}")

    df = df.sort_index()
    latest = df.iloc[-1]
    current_price = float(latest["Close"])

    def close_n_days_ago(n: int) -> float | None:
        if len(df) < n + 1:
            return None
        return float(df.iloc[-(n + 1)]["Close"])

    prev_close = close_n_days_ago(1)
    week_ago = close_n_days_ago(5)
    month_ago = close_n_days_ago(21)
    three_month_ago = close_n_days_ago(63)
    year_ago = float(df.iloc[0]["Close"]) if len(df) >= 2 else None

    # 52-week high / low
    high_52w = float(df["High"].max())
    low_52w = float(df["Low"].min())

    # Average volume (20-day)
    avg_vol_20d = int(df["Volume"].tail(20).mean()) if len(df) >= 20 else None

    # Today's volume
    today_vol = int(latest["Volume"]) if latest["Volume"] > 0 else None

    return {
        "ticker": ticker,
        "price": current_price,
        "currency": "INR",
        "change_1d_pct": _pct(current_price, prev_close) if prev_close else None,
        "change_1w_pct": _pct(current_price, week_ago) if week_ago else None,
        "change_1m_pct": _pct(current_price, month_ago) if month_ago else None,
        "change_3m_pct": _pct(current_price, three_month_ago) if three_month_ago else None,
        "change_1y_pct": _pct(current_price, year_ago) if year_ago else None,
        "high_52w": round(high_52w, 2),
        "low_52w": round(low_52w, 2),
        "avg_volume_20d": avg_vol_20d,
        "volume_today": today_vol,
        # OHLCV for chart — full 1Y so frontend can slice any window
        "ohlcv_1y": [
            {
                "date": idx.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            }
            for idx, row in df.iterrows()
        ],
    }


@router.get("/quote/{ticker}", response_model=dict[str, Any])
async def get_quote(ticker: str) -> dict[str, Any]:
    """Return current price, % changes (1D/1W/1M/3M/1Y), 52W range, and 1Y OHLCV."""
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, lambda: _quote_from_history(ticker))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Quote fetch failed for %s", ticker)
        raise HTTPException(status_code=502, detail=f"Price data unavailable: {exc}") from exc


@router.get("/quotes", response_model=list[dict[str, Any]])
async def get_quotes(tickers: str) -> list[dict[str, Any]]:
    """Batch quote endpoint — tickers is a comma-separated list e.g. RELIANCE.NS,TCS.NS"""
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        return []
    if len(ticker_list) > 20:
        raise HTTPException(status_code=422, detail="Max 20 tickers per request")

    loop = asyncio.get_running_loop()

    async def _fetch_one(t: str) -> dict[str, Any] | None:
        try:
            return await loop.run_in_executor(None, lambda: _quote_from_history(t))
        except Exception:
            logger.warning("Quote failed for %s", t)
            return None

    results = await asyncio.gather(*[_fetch_one(t) for t in ticker_list])
    return [r for r in results if r is not None]
