from __future__ import annotations

from datetime import date
from typing import Literal

import pandas as pd

from schemas.features import RRGPoint, RRGResult

SECTOR_INDEX_MAP: dict[str, str] = {
    "Financial Services": "^NSEBANK",
    "Information Technology": "^CNXIT",
    "Pharmaceuticals": "^CNXPHARMA",
    "Healthcare": "^CNXPHARMA",
    "Energy": "^CNXENERGY",
    "Utilities": "^CNXENERGY",
    "Consumer Defensive": "^CNXFMCG",
    "Consumer Cyclical": "^CNXFMCG",
    "Basic Materials": "^CNXMETAL",
    "Industrials": "^CNXINFRA",
    "Real Estate": "^CNXREALTY",
    "Communication Services": "^CNXMEDIA",
}

_Quadrant = Literal["Leading", "Weakening", "Lagging", "Improving"]


def _classify(rs_ratio: float, rs_momentum: float) -> _Quadrant:
    if rs_ratio > 100.0 and rs_momentum > 0.0:
        return "Leading"
    elif rs_ratio > 100.0:
        return "Weakening"
    elif rs_momentum > 0.0:
        return "Improving"
    return "Lagging"


def compute_rrg(
    prices: dict[str, pd.DataFrame],
    benchmark_df: pd.DataFrame,
    smoothing: int = 10,
    momentum_lag: int = 1,
    benchmark_ticker: str = "^NSEI",
) -> RRGResult:
    """Compute Relative Rotation Graph positions for a universe of tickers.

    Args:
        prices: Dict of ticker → DataFrame with a 'close' column, sorted ascending.
        benchmark_df: DataFrame with a 'close' column for the benchmark index.
        smoothing: EMA span applied to both RS ratio and RS momentum.
        momentum_lag: Shift period for the rate-of-change calculation.
        benchmark_ticker: Label stored in each RRGPoint (does not fetch data).

    Returns:
        RRGResult with one RRGPoint per ticker that had sufficient history.
        Tickers with fewer than (smoothing + momentum_lag + 5) rows are skipped.
    """
    min_rows = smoothing + momentum_lag + 5  # extra warmup rows for EMA stability
    points: list[RRGPoint] = []

    for ticker, df in prices.items():
        n = min(len(df), len(benchmark_df))
        if n < min_rows:
            continue

        ticker_close = df["close"].iloc[-n:].reset_index(drop=True)
        bench_close = benchmark_df["close"].iloc[-n:].reset_index(drop=True)

        if (bench_close == 0.0).any():
            continue  # skip: benchmark has zero/corrupt price data

        # Step 1 — smooth the raw RS ratio first (common bug: ROC before EMA)
        raw_rs = ticker_close / bench_close * 100.0
        rs_ratio = raw_rs.ewm(span=smoothing, adjust=False).mean()

        # Step 2 — compute ROC on the smoothed ratio, then smooth again
        raw_momentum = (rs_ratio / rs_ratio.shift(momentum_lag) - 1.0) * 100.0
        rs_momentum = raw_momentum.ewm(span=smoothing, adjust=False).mean()

        latest_ratio = rs_ratio.iloc[-1]
        latest_momentum = rs_momentum.iloc[-1]

        if pd.isna(latest_ratio) or pd.isna(latest_momentum):
            continue  # skip: NaN propagated through EMA — insufficient clean data

        latest_ratio = float(latest_ratio)
        latest_momentum = float(latest_momentum)

        points.append(
            RRGPoint(
                ticker=ticker,
                rs_ratio=latest_ratio,
                rs_momentum=latest_momentum,
                quadrant=_classify(latest_ratio, latest_momentum),
                benchmark=benchmark_ticker,
                as_of=date.today(),
            )
        )

    return RRGResult(points=points, smoothing=smoothing, momentum_lag=momentum_lag)
