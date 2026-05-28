from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

import yfinance as yf

logger = logging.getLogger(__name__)


async def fetch_outcomes(
    ticker: str,
    as_of_date: date,
    horizons: list[int],
) -> dict[int, float | None]:
    """Fetch actual price returns at each horizon from as_of_date.

    Returns dict mapping horizon_days → return (float) or None if unavailable.
    Single yfinance download call covers all horizons.
    """
    max_horizon = max(horizons)
    start_str = as_of_date.strftime("%Y-%m-%d")
    end_date = as_of_date + timedelta(days=max_horizon + 10)
    end_str = end_date.strftime("%Y-%m-%d")

    loop = asyncio.get_running_loop()
    try:
        df = await loop.run_in_executor(
            None,
            lambda: yf.download(ticker, start=start_str, end=end_str, progress=False),
        )
    except Exception as exc:
        logger.warning("fetch_outcomes yfinance error for %s: %s", ticker, exc)
        return {h: None for h in horizons}

    if df.empty:
        return {h: None for h in horizons}

    # Flatten multi-level columns if present
    if hasattr(df.columns, "levels"):
        try:
            df.columns = df.columns.get_level_values(0)
        except Exception:
            pass

    # Build parallel lists of dates and closes
    dates = [d.date() for d in df.index]
    closes = list(df["Close"])

    # Find base price (as_of_date or first date on/after)
    base_idx: int | None
    if as_of_date in dates:
        base_idx = dates.index(as_of_date)
    else:
        base_idx = next((i for i, d in enumerate(dates) if d >= as_of_date), None)

    if base_idx is None:
        return {h: None for h in horizons}

    base_close = float(closes[base_idx])
    if base_close == 0.0:
        return {h: None for h in horizons}

    outcomes: dict[int, float | None] = {}
    for h in horizons:
        target = as_of_date + timedelta(days=h)
        horizon_idx = next((i for i, d in enumerate(dates) if d >= target), None)
        if horizon_idx is None:
            outcomes[h] = None
        else:
            horizon_close = float(closes[horizon_idx])
            outcomes[h] = (horizon_close / base_close) - 1.0

    return outcomes
