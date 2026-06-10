from datetime import date
from unittest.mock import patch

import pytest
from schemas.features import (
    DivergenceResult,
    FlowStrengthResult,
    RRGPoint,
    RRGResult,
)
from schemas.state import AnalysisState
from worker.nodes.divergence import compute_divergence_node


def _make_state(with_flow: bool = True, rrg_points: int = 1) -> AnalysisState:
    state = AnalysisState(user_query="test", ticker_universe=["RELIANCE.NS", "TCS.NS"])
    points = [
        RRGPoint(
            ticker=f"TICK{i}.NS",
            rs_ratio=105.0,
            rs_momentum=1.0,
            quadrant="Leading",
            benchmark="^NSEI",
            as_of=date(2026, 1, 30),
        ).model_dump()
        for i in range(rrg_points)
    ]
    state.rotation = RRGResult(
        points=[RRGPoint(**p) for p in points],
        smoothing=10,
        momentum_lag=1,
    ).model_dump()

    if with_flow:
        state.alt_data["flow"] = FlowStrengthResult(
            as_of=date(2026, 1, 30),
            fii_zscore=1.0,
            fii_ratio=0.3,
            fii_streak=3,
            dii_zscore=0.8,
            dii_ratio=0.2,
            dii_streak=2,
            net_institutional=500.0,
        ).model_dump()
    else:
        state.alt_data["flow"] = None
    return state


@pytest.mark.asyncio
async def test_divergence_node_writes_score_and_contradictions():
    state = _make_state(with_flow=True)
    mock_result = DivergenceResult(
        divergence_score=0.15,
        contradictions=["fii_zscore=bullish conflicts with dii_zscore=bearish"],
        majority_direction="bullish",
        signal_votes={
            "rrg": "bullish",
            "fii_zscore": "bullish",
            "fii_ratio": "bullish",
            "dii_zscore": "bullish",
            "sentiment": "neutral",
        },
    )
    with patch("worker.nodes.divergence.compute_divergence", return_value=mock_result):
        result = await compute_divergence_node(state)

    assert result.divergence_score == pytest.approx(0.15)
    assert isinstance(result.contradictions, list)


@pytest.mark.asyncio
async def test_divergence_node_zero_score_when_no_flow():
    state = _make_state(with_flow=False)
    result = await compute_divergence_node(state)

    assert result.divergence_score == 0.0
    assert isinstance(result.contradictions, list)
    assert any("flow" in e.message.lower() for e in result.audit_log)


@pytest.mark.asyncio
async def test_divergence_node_averages_multiple_rrg_points():
    state = _make_state(with_flow=True, rrg_points=2)
    results = [
        DivergenceResult(
            divergence_score=0.2,
            contradictions=[],
            majority_direction="bullish",
            signal_votes={
                "rrg": "bullish",
                "fii_zscore": "bullish",
                "fii_ratio": "bullish",
                "dii_zscore": "bullish",
                "sentiment": "neutral",
            },
        ),
        DivergenceResult(
            divergence_score=0.4,
            contradictions=[],
            majority_direction="bullish",
            signal_votes={
                "rrg": "bullish",
                "fii_zscore": "bullish",
                "fii_ratio": "bullish",
                "dii_zscore": "bullish",
                "sentiment": "neutral",
            },
        ),
    ]
    with patch("worker.nodes.divergence.compute_divergence", side_effect=results):
        result = await compute_divergence_node(state)

    assert result.divergence_score == pytest.approx(0.3)


@pytest.mark.asyncio
async def test_divergence_node_empty_rrg_writes_zero():
    state = _make_state(with_flow=True, rrg_points=0)
    result = await compute_divergence_node(state)
    assert result.divergence_score == 0.0
