from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest
from worker.backtest.outcomes import fetch_outcomes


def _make_df(dates: list[date], closes: list[float]) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
    return pd.DataFrame({"Close": closes}, index=idx)


@pytest.mark.asyncio
async def test_fetch_outcomes_returns_correct_returns() -> None:
    # as_of_date = 2022-01-03, horizon 30d target = Feb 2, horizon 90d target = Apr 3
    # closes: Jan 3=100, Feb 2=104 (+4%), Apr 3=90 (-10%)
    as_of = date(2022, 1, 3)
    df = _make_df(
        [date(2022, 1, 3), date(2022, 2, 2), date(2022, 4, 3)],
        [100.0, 104.0, 90.0],
    )
    with patch("worker.backtest.outcomes.yf.download", return_value=df):
        outcomes = await fetch_outcomes("RELIANCE.NS", as_of, [30, 90])
    assert outcomes[30] == pytest.approx(0.04, abs=1e-6)
    assert outcomes[90] == pytest.approx(-0.10, abs=1e-6)


@pytest.mark.asyncio
async def test_fetch_outcomes_returns_none_for_missing_horizon() -> None:
    as_of = date(2022, 1, 3)
    # Only data up to 30-day horizon
    df = _make_df([date(2022, 1, 3), date(2022, 2, 2)], [100.0, 105.0])
    with patch("worker.backtest.outcomes.yf.download", return_value=df):
        outcomes = await fetch_outcomes("TCS.NS", as_of, [30, 90])
    assert outcomes[30] == pytest.approx(0.05, abs=1e-6)
    assert outcomes[90] is None


@pytest.mark.asyncio
async def test_fetch_outcomes_returns_all_none_on_empty_df() -> None:
    empty_df = pd.DataFrame()
    with patch("worker.backtest.outcomes.yf.download", return_value=empty_df):
        outcomes = await fetch_outcomes("FAKE.NS", date(2022, 1, 3), [30, 90, 180])
    assert all(v is None for v in outcomes.values())


@pytest.mark.asyncio
async def test_fetch_outcomes_single_download_call() -> None:
    empty_df = pd.DataFrame()
    with patch("worker.backtest.outcomes.yf.download", return_value=empty_df) as mock_dl:
        await fetch_outcomes("INFY.NS", date(2022, 1, 3), [30, 90, 180])
    assert mock_dl.call_count == 1
