import pandas as pd
import pytest
from datetime import date
from unittest.mock import patch

from schemas.connectors import ConnectorResult
from schemas.features import FlowStrengthResult, RRGPoint, RRGResult
from schemas.state import AnalysisState

from worker.nodes.features import compute_features


def _make_state_with_data(with_fii: bool = True, with_ohlcv: bool = True) -> AnalysisState:
    ohlcv = [{"date": f"2026-01-{i+1:02d}", "close": 100.0 + i} for i in range(30)]
    bench_ohlcv = [{"date": f"2026-01-{i+1:02d}", "close": 200.0 + i} for i in range(30)]
    fii_data = {
        "fii_net": 500.0, "fii_buy": 1000.0, "fii_sell": 500.0,
        "dii_net": -200.0, "dii_buy": 300.0, "dii_sell": 500.0,
    } if with_fii else None

    state = AnalysisState(user_query="test", ticker_universe=["RELIANCE.NS"])
    state.market_data = {
        "RELIANCE.NS": {
            "fundamentals": {"sector": "Energy"},
            "ohlcv": ohlcv if with_ohlcv else None,
        },
        "^NSEI": {"ohlcv": bench_ohlcv if with_ohlcv else None},
    }
    state.alt_data = {
        "fii_dii": fii_data,
        "gmp_connector": None,
    }
    return state


@pytest.mark.asyncio
async def test_compute_features_writes_rrg_result():
    state = _make_state_with_data()
    mock_rrg = RRGResult(
        points=[RRGPoint(
            ticker="RELIANCE.NS", rs_ratio=105.0, rs_momentum=1.5,
            quadrant="Leading", benchmark="^NSEI", as_of=date(2026, 1, 30),
        )],
        smoothing=10, momentum_lag=1,
    )
    with patch("worker.nodes.features.compute_rrg", return_value=mock_rrg):
        with patch("worker.nodes.features.compute_flow_strength", side_effect=ValueError("insufficient")):
            result = await compute_features(state)

    assert "points" in result.rotation
    assert result.rotation["points"][0]["ticker"] == "RELIANCE.NS"
    assert result.alt_data["flow"] is None


@pytest.mark.asyncio
async def test_compute_features_writes_flow_result():
    state = _make_state_with_data()
    mock_rrg = RRGResult(points=[], smoothing=10, momentum_lag=1)
    mock_flow = FlowStrengthResult(
        as_of=date(2026, 1, 30),
        fii_zscore=1.2, fii_ratio=0.3, fii_streak=3,
        dii_zscore=-0.5, dii_ratio=-0.1, dii_streak=-2,
        net_institutional=300.0,
    )
    with patch("worker.nodes.features.compute_rrg", return_value=mock_rrg):
        with patch("worker.nodes.features.compute_flow_strength", return_value=mock_flow):
            result = await compute_features(state)

    assert result.alt_data["flow"] is not None
    assert result.alt_data["flow"]["fii_zscore"] == 1.2


@pytest.mark.asyncio
async def test_compute_features_handles_none_gmp():
    state = _make_state_with_data()
    state.alt_data["gmp_connector"] = None
    mock_rrg = RRGResult(points=[], smoothing=10, momentum_lag=1)

    with patch("worker.nodes.features.compute_rrg", return_value=mock_rrg):
        with patch("worker.nodes.features.compute_flow_strength", side_effect=ValueError("insufficient")):
            result = await compute_features(state)

    assert result.alt_data["gmp"] is None


@pytest.mark.asyncio
async def test_compute_features_handles_missing_ohlcv():
    state = _make_state_with_data(with_ohlcv=False)
    with patch("worker.nodes.features.compute_rrg") as mock_rrg_fn:
        with patch("worker.nodes.features.compute_flow_strength", side_effect=ValueError("insufficient")):
            result = await compute_features(state)

    # compute_rrg should not be called — no prices to pass
    mock_rrg_fn.assert_not_called()
    assert result.rotation == {}
