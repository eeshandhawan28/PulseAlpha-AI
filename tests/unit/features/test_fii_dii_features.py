from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from features.fii_dii import compute_flow_strength
from schemas.features import FlowStrengthResult


def make_flow_df(
    n: int = 25,
    fii_net: float = 1000.0,
    dii_net: float = -500.0,
    fii_buy: float = 5000.0,
    dii_buy: float = 3000.0,
) -> pd.DataFrame:
    """Constant-value flow DataFrame for deterministic tests."""
    return pd.DataFrame(
        {
            "fii_net": [fii_net] * n,
            "fii_buy": [fii_buy] * n,
            "fii_sell": [fii_buy - fii_net] * n,
            "dii_net": [dii_net] * n,
            "dii_buy": [dii_buy] * n,
            "dii_sell": [dii_buy - dii_net] * n,
        }
    )


def test_flow_strength_returns_result() -> None:
    result = compute_flow_strength(make_flow_df())
    assert isinstance(result, FlowStrengthResult)
    assert isinstance(result.as_of, date)


def test_flow_strength_zscore_zero_for_constant_series() -> None:
    """Constant series → std=0 → zscore must be 0.0, never NaN."""
    result = compute_flow_strength(make_flow_df(fii_net=1000.0))
    assert result.fii_zscore == 0.0


def test_flow_strength_ratio_in_range() -> None:
    result = compute_flow_strength(make_flow_df(fii_net=1000.0))
    assert -1.0 <= result.fii_ratio <= 1.0


def test_flow_strength_buying_streak() -> None:
    """All positive fii_net → streak equals number of rows."""
    result = compute_flow_strength(make_flow_df(n=25, fii_net=500.0))
    assert result.fii_streak == 25


def test_flow_strength_selling_streak() -> None:
    """All negative fii_net → streak is negative and equal to -n."""
    result = compute_flow_strength(make_flow_df(n=25, fii_net=-500.0))
    assert result.fii_streak == -25


def test_flow_strength_mixed_streak() -> None:
    """Last 3 days positive, preceded by negatives → streak = 3."""
    vals = [-100.0] * 22 + [200.0] * 3
    df = pd.DataFrame(
        {
            "fii_net": vals,
            "fii_buy": [5000.0] * 25,
            "fii_sell": [4000.0] * 25,
            "dii_net": [100.0] * 25,
            "dii_buy": [3000.0] * 25,
            "dii_sell": [2900.0] * 25,
        }
    )
    result = compute_flow_strength(df)
    assert result.fii_streak == 3


def test_flow_strength_insufficient_history_raises() -> None:
    df = make_flow_df(n=5)
    with pytest.raises(ValueError, match="at least"):
        compute_flow_strength(df, zscore_window=20)


def test_flow_strength_net_institutional() -> None:
    result = compute_flow_strength(make_flow_df(fii_net=1000.0, dii_net=-500.0))
    assert result.net_institutional == pytest.approx(500.0)
