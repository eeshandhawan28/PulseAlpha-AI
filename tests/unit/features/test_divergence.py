from __future__ import annotations

from datetime import date

import pytest

from features.divergence import compute_divergence
from schemas.features import DivergenceResult, FlowStrengthResult, IPOGMPResult, RRGPoint


def make_rrg(quadrant: str) -> RRGPoint:
    rs_ratio = 105.0 if quadrant in ("Leading", "Weakening") else 95.0
    rs_momentum = 1.0 if quadrant in ("Leading", "Improving") else -1.0
    return RRGPoint(
        ticker="TEST.NS",
        rs_ratio=rs_ratio,
        rs_momentum=rs_momentum,
        quadrant=quadrant,  # type: ignore[arg-type]
        benchmark="^NSEI",
        as_of=date.today(),
    )


def make_flow(
    fii_zscore: float = 1.0,
    fii_ratio: float = 0.3,
    dii_zscore: float = 0.8,
    dii_ratio: float = 0.2,
) -> FlowStrengthResult:
    return FlowStrengthResult(
        as_of=date.today(),
        fii_zscore=fii_zscore,
        fii_ratio=fii_ratio,
        fii_streak=5,
        dii_zscore=dii_zscore,
        dii_ratio=dii_ratio,
        dii_streak=3,
        net_institutional=1500.0,
    )


def test_full_bullish_consensus_score_zero() -> None:
    result = compute_divergence(
        rrg=make_rrg("Leading"),
        flow=make_flow(fii_zscore=1.0, fii_ratio=0.3, dii_zscore=0.8, dii_ratio=0.2),
        sentiment_polarity=0.5,
    )
    assert result.divergence_score == pytest.approx(0.0)
    assert result.majority_direction == "bullish"
    assert result.contradictions == []


def test_rrg_outlier_raises_score() -> None:
    """RRG=Lagging but all flow signals bullish → nonzero score."""
    result = compute_divergence(
        rrg=make_rrg("Lagging"),
        flow=make_flow(fii_zscore=1.5, fii_ratio=0.4, dii_zscore=1.2, dii_ratio=0.3),
        sentiment_polarity=0.6,
    )
    assert result.divergence_score > 0.0
    assert result.signal_votes["rrg"] == "bearish"
    assert result.majority_direction == "bullish"


def test_neutral_signals_excluded_from_contradictions() -> None:
    """Near-zero flow + neutral sentiment → only RRG vote is non-neutral."""
    result = compute_divergence(
        rrg=make_rrg("Leading"),
        flow=make_flow(fii_zscore=0.1, fii_ratio=0.05, dii_zscore=0.1, dii_ratio=0.05),
        sentiment_polarity=0.0,
    )
    # Only RRG is bullish; others are neutral — no contradictions
    assert result.contradictions == []


def test_gmp_none_excluded_from_votes() -> None:
    result = compute_divergence(
        rrg=make_rrg("Leading"),
        flow=make_flow(),
        sentiment_polarity=0.3,
        gmp=None,
    )
    assert isinstance(result, DivergenceResult)
    assert "gmp" not in result.signal_votes


def test_contradictions_contain_conflicts_with_phrase() -> None:
    result = compute_divergence(
        rrg=make_rrg("Lagging"),
        flow=make_flow(fii_zscore=1.5, fii_ratio=0.4, dii_zscore=0.0, dii_ratio=0.0),
        sentiment_polarity=0.5,
    )
    for c in result.contradictions:
        assert "conflicts with" in c


def test_divergence_score_bounded_to_one() -> None:
    """Score must never exceed 1.0 regardless of weight configuration."""
    result = compute_divergence(
        rrg=make_rrg("Lagging"),
        flow=make_flow(fii_zscore=-1.5, fii_ratio=-0.4, dii_zscore=-1.2, dii_ratio=-0.3),
        sentiment_polarity=-0.6,
    )
    assert result.divergence_score <= 1.0


def test_signal_votes_contains_all_expected_keys() -> None:
    result = compute_divergence(
        rrg=make_rrg("Leading"),
        flow=make_flow(),
        sentiment_polarity=0.2,
    )
    expected_keys = {"rrg", "fii_zscore", "fii_ratio", "dii_zscore", "sentiment"}
    assert expected_keys.issubset(result.signal_votes.keys())
