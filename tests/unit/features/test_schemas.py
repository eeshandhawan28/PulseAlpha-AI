from datetime import date
from schemas.features import (
    RRGPoint, RRGResult,
    FlowStrengthResult,
    IPOGMPResult,
    DivergenceResult,
)
from schemas.state import AnalysisState


def test_rrg_point_quadrant_literal():
    p = RRGPoint(
        ticker="RELIANCE.NS",
        rs_ratio=105.0,
        rs_momentum=1.5,
        quadrant="Leading",
        benchmark="^NSEI",
        as_of=date.today(),
    )
    assert p.quadrant == "Leading"


def test_rrg_result_holds_points():
    r = RRGResult(points=[], smoothing=10, momentum_lag=1)
    assert r.points == []


def test_flow_strength_result_fields():
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
    assert f.fii_streak == 5
    assert f.dii_streak == -2


def test_ipo_gmp_result_fields():
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


def test_divergence_result_score_bounded():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        DivergenceResult(
            divergence_score=1.5,  # exceeds 1.0
            contradictions=[],
            majority_direction="bullish",
            signal_votes={},
        )


def test_analysis_state_has_divergence_score():
    state = AnalysisState(
        user_query="Analyze RELIANCE.NS",
        ticker_universe=["RELIANCE.NS"],
    )
    assert state.divergence_score == 0.0
