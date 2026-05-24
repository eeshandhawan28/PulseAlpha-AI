from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from features.rrg import SECTOR_INDEX_MAP, compute_rrg
from schemas.features import RRGResult


def make_price_df(n: int = 60, trend: float = 1.002) -> pd.DataFrame:
    """Synthetic price series trending at `trend` per day."""
    prices = [100.0 * (trend**i) for i in range(n)]
    return pd.DataFrame({"close": prices})


def make_flat_benchmark(n: int = 60) -> pd.DataFrame:
    return pd.DataFrame({"close": [100.0] * n})


def test_rrg_leading_quadrant() -> None:
    """Ticker outperforming flat benchmark and accelerating → Leading."""
    result = compute_rrg(
        prices={"RELIANCE.NS": make_price_df(trend=1.003)},
        benchmark_df=make_flat_benchmark(),
    )
    assert len(result.points) == 1
    p = result.points[0]
    assert p.quadrant == "Leading"
    assert p.rs_ratio > 100.0


def test_rrg_lagging_quadrant() -> None:
    """Ticker underperforming → Lagging."""
    result = compute_rrg(
        prices={"WEAK.NS": make_price_df(trend=0.997)},
        benchmark_df=make_flat_benchmark(),
    )
    assert result.points[0].quadrant == "Lagging"
    assert result.points[0].rs_ratio < 100.0


def test_rrg_skips_ticker_with_insufficient_history() -> None:
    """Fewer rows than smoothing + momentum_lag + 5 → ticker excluded from result."""
    short_df = pd.DataFrame({"close": [100.0] * 5})
    result = compute_rrg(
        prices={"SHORT.NS": short_df},
        benchmark_df=make_flat_benchmark(),
        smoothing=10,
        momentum_lag=1,
    )
    assert len(result.points) == 0


def test_rrg_benchmark_ticker_stored_in_point() -> None:
    result = compute_rrg(
        prices={"TCS.NS": make_price_df()},
        benchmark_df=make_flat_benchmark(),
        benchmark_ticker="^NSEBANK",
    )
    assert result.points[0].benchmark == "^NSEBANK"


def test_rrg_result_metadata() -> None:
    result = compute_rrg(
        prices={"INFY.NS": make_price_df()},
        benchmark_df=make_flat_benchmark(),
        smoothing=10,
        momentum_lag=1,
    )
    assert result.smoothing == 10
    assert result.momentum_lag == 1
    assert isinstance(result.points[0].as_of, date)


def test_rrg_multiple_tickers() -> None:
    result = compute_rrg(
        prices={
            "A.NS": make_price_df(trend=1.002),
            "B.NS": make_price_df(trend=0.998),
        },
        benchmark_df=make_flat_benchmark(),
    )
    assert len(result.points) == 2
    tickers = {p.ticker for p in result.points}
    assert tickers == {"A.NS", "B.NS"}


def test_sector_index_map_known_sectors() -> None:
    assert "Financial Services" in SECTOR_INDEX_MAP
    assert SECTOR_INDEX_MAP["Financial Services"] == "^NSEBANK"
    assert "Information Technology" in SECTOR_INDEX_MAP


def test_sector_index_map_fallback_for_unknown() -> None:
    assert SECTOR_INDEX_MAP.get("Unknown Sector XYZ", "^NSEI") == "^NSEI"
