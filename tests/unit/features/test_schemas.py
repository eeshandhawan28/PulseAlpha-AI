from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError
from schemas.features import (
    DivergenceResult,
    FlowStrengthResult,
    IPOGMPResult,
    RRGPoint,
    RRGResult,
)
from schemas.state import AnalysisState

# ── RRGPoint ──────────────────────────────────────────────────────────────────


def test_rrg_point_valid_quadrant() -> None:
    p = RRGPoint(
        ticker="RELIANCE.NS",
        rs_ratio=105.0,
        rs_momentum=1.5,
        quadrant="Leading",
        benchmark="^NSEI",
        as_of=date.today(),
    )
    assert p.quadrant == "Leading"


def test_rrg_point_rejects_invalid_quadrant() -> None:
    with pytest.raises(ValidationError):
        RRGPoint(
            ticker="RELIANCE.NS",
            rs_ratio=105.0,
            rs_momentum=1.5,
            quadrant="Sideways",  # invalid
            benchmark="^NSEI",
            as_of=date.today(),
        )


# ── RRGResult ─────────────────────────────────────────────────────────────────


def test_rrg_result_nested_point_roundtrip() -> None:
    point = RRGPoint(
        ticker="TCS.NS",
        rs_ratio=98.0,
        rs_momentum=-0.5,
        quadrant="Lagging",
        benchmark="^NSEI",
        as_of=date.today(),
    )
    result = RRGResult(points=[point], smoothing=10, momentum_lag=1)
    assert len(result.points) == 1
    assert result.points[0].ticker == "TCS.NS"
    assert result.points[0].quadrant == "Lagging"


# ── FlowStrengthResult ────────────────────────────────────────────────────────


def test_flow_strength_streak_sign_convention() -> None:
    """Positive streak = buying (fii_streak > 0), negative = selling (fii_streak < 0)."""
    f = FlowStrengthResult(
        as_of=date.today(),
        fii_zscore=1.2,
        fii_ratio=0.3,
        fii_streak=5,
        dii_zscore=-0.4,
        dii_ratio=-0.1,
        dii_streak=-2,
        net_institutional=1500.0,
    )
    assert f.fii_streak > 0, "positive streak means FII buying"
    assert f.dii_streak < 0, "negative streak means DII selling"


# ── IPOGMPResult ──────────────────────────────────────────────────────────────


def test_ipo_gmp_result_valid() -> None:
    r = IPOGMPResult(
        company_name="Test IPO",
        issue_price=500.0,
        gmp=75.0,
        gmp_implied_return=0.15,
        institutional_signal=0.8,
        retail_signal=0.6,
        disagreement_score=0.35,
        data_available=True,
    )
    assert r.data_available is True
    assert r.institutional_signal == 0.8


def test_ipo_gmp_rejects_out_of_range_institutional_signal() -> None:
    with pytest.raises(ValidationError):
        IPOGMPResult(
            company_name="Test",
            issue_price=500.0,
            gmp=75.0,
            gmp_implied_return=0.15,
            institutional_signal=1.5,  # > 1.0 — invalid
            retail_signal=0.6,
            disagreement_score=0.35,
            data_available=True,
        )


def test_ipo_gmp_rejects_negative_retail_signal() -> None:
    with pytest.raises(ValidationError):
        IPOGMPResult(
            company_name="Test",
            issue_price=500.0,
            gmp=75.0,
            gmp_implied_return=0.15,
            institutional_signal=0.8,
            retail_signal=-0.1,  # < 0.0 — invalid
            disagreement_score=0.35,
            data_available=True,
        )


def test_ipo_gmp_implied_return_can_exceed_one() -> None:
    """High-premium IPOs can have GMP implied return > 100% — must not be rejected."""
    r = IPOGMPResult(
        company_name="Hot IPO",
        issue_price=100.0,
        gmp=150.0,
        gmp_implied_return=1.5,  # 150% premium — allowed
        institutional_signal=0.9,
        retail_signal=0.95,
        disagreement_score=0.6,
        data_available=True,
    )
    assert r.gmp_implied_return == 1.5


# ── DivergenceResult ──────────────────────────────────────────────────────────


def test_divergence_result_rejects_score_above_one() -> None:
    with pytest.raises(ValidationError):
        DivergenceResult(
            divergence_score=1.5,
            contradictions=[],
            majority_direction="bullish",
            signal_votes={},
        )


def test_divergence_result_rejects_invalid_direction() -> None:
    with pytest.raises(ValidationError):
        DivergenceResult(
            divergence_score=0.5,
            contradictions=[],
            majority_direction="sideways",  # invalid
            signal_votes={},
        )


def test_divergence_result_valid() -> None:
    r = DivergenceResult(
        divergence_score=0.45,
        contradictions=["rrg=bearish conflicts with sentiment=bullish"],
        majority_direction="bullish",
        signal_votes={"rrg": "bearish", "sentiment": "bullish"},
    )
    assert r.divergence_score == 0.45
    assert len(r.contradictions) == 1


# ── AnalysisState ─────────────────────────────────────────────────────────────


def test_analysis_state_divergence_score_defaults_to_zero() -> None:
    state = AnalysisState(
        user_query="Analyze RELIANCE.NS",
        ticker_universe=["RELIANCE.NS"],
    )
    assert state.divergence_score == 0.0


def test_analysis_state_divergence_score_rejects_out_of_range() -> None:
    with pytest.raises(ValidationError):
        AnalysisState(
            user_query="Analyze RELIANCE.NS",
            ticker_universe=["RELIANCE.NS"],
            divergence_score=1.5,  # > 1.0
        )
