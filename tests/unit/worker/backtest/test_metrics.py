from __future__ import annotations

from datetime import date

import pytest
from schemas.backtest import PredictionRecord
from worker.backtest.metrics import (
    confidence_calibration,
    divergence_correlation,
    hit_rate,
    persona_accuracy,
)


def _make_record(
    stance: str,
    confidence: float,
    divergence_score: float,
    correct_30: bool | None,
    persona_stances: dict[str, str] | None = None,
    outcome_30: float | None = None,
) -> PredictionRecord:
    if outcome_30 is None:
        if correct_30 is True:
            outcome_30 = 0.02
        elif correct_30 is False:
            outcome_30 = -0.02
    return PredictionRecord(
        as_of_date=date(2022, 1, 3),
        ticker="RELIANCE.NS",
        stance=stance,
        confidence=confidence,
        divergence_score=divergence_score,
        persona_stances=persona_stances or {},
        outcomes={30: outcome_30},
        correct={30: correct_30},
    )


# ── hit_rate ──────────────────────────────────────────────────────────────────

def test_hit_rate_overall() -> None:
    records = [
        _make_record("bullish", 0.7, 0.2, True),
        _make_record("bullish", 0.7, 0.2, False),
        _make_record("bearish", 0.6, 0.3, True),
        _make_record("neutral", 0.5, 0.1, None),
    ]
    result = hit_rate(records, 30)
    assert result["overall"] == pytest.approx(2 / 3, abs=1e-6)
    assert result["n_evaluated"] == 3
    assert result["n_excluded_neutral"] == 1


def test_hit_rate_excludes_neutral() -> None:
    records = [_make_record("neutral", 0.5, 0.1, None) for _ in range(5)]
    result = hit_rate(records, 30)
    assert result["overall"] == 0.0
    assert result["n_evaluated"] == 0
    assert result["n_excluded_neutral"] == 5


def test_hit_rate_empty_returns_zeroed() -> None:
    result = hit_rate([], 30)
    assert result["overall"] == 0.0
    assert result["n_evaluated"] == 0


# ── confidence_calibration ────────────────────────────────────────────────────

def test_confidence_calibration_buckets() -> None:
    records = [
        _make_record("bullish", 0.5, 0.2, True),    # bucket 0.4-0.6
        _make_record("bullish", 0.5, 0.2, False),   # bucket 0.4-0.6
        _make_record("bullish", 0.7, 0.2, True),    # bucket 0.6-0.8
        _make_record("bullish", 0.7, 0.2, True),    # bucket 0.6-0.8
    ]
    buckets = confidence_calibration(records, 30)
    by_label = {b["bucket"]: b for b in buckets}
    assert by_label["0.4-0.6"]["n"] == 2
    assert by_label["0.4-0.6"]["accuracy"] == pytest.approx(0.5, abs=1e-6)
    assert by_label["0.6-0.8"]["n"] == 2
    assert by_label["0.6-0.8"]["accuracy"] == pytest.approx(1.0, abs=1e-6)


def test_confidence_calibration_empty_bucket_excluded() -> None:
    records = [_make_record("bullish", 0.9, 0.2, True)]
    buckets = confidence_calibration(records, 30)
    labels = [b["bucket"] for b in buckets]
    assert "0.8-1.0" in labels
    assert "0.0-0.4" not in labels


# ── persona_accuracy ──────────────────────────────────────────────────────────

def test_persona_accuracy_per_persona() -> None:
    # Record 1: outcome positive (0.02), Contrarian=bullish (correct), Momentum=bearish (wrong)
    # Record 2: outcome positive (0.02), Contrarian=bearish (wrong), Momentum=bullish (correct)
    records = [
        _make_record("bullish", 0.7, 0.2, True,
                     persona_stances={"Contrarian": "bullish", "Momentum": "bearish"},
                     outcome_30=0.02),
        _make_record("bullish", 0.7, 0.2, True,
                     persona_stances={"Contrarian": "bearish", "Momentum": "bullish"},
                     outcome_30=0.02),
    ]
    result = persona_accuracy(records, 30)
    assert result["Contrarian"]["n"] == 2
    assert result["Contrarian"]["accuracy"] == pytest.approx(0.5, abs=1e-6)
    assert result["Momentum"]["n"] == 2
    assert result["Momentum"]["accuracy"] == pytest.approx(0.5, abs=1e-6)


# ── divergence_correlation ────────────────────────────────────────────────────

def test_divergence_correlation_negative_sign() -> None:
    # Lower divergence → more correct → negative correlation
    records = [
        _make_record("bullish", 0.8, 0.1, True),
        _make_record("bullish", 0.8, 0.1, True),
        _make_record("bullish", 0.5, 0.9, False),
        _make_record("bullish", 0.5, 0.9, False),
    ]
    result = divergence_correlation(records, 30)
    assert result["n"] == 4
    assert result["correlation"] < 0


def test_divergence_correlation_returns_zero_for_constant() -> None:
    # All correct → variance in correct=0 → StatisticsError → returns 0.0
    records = [_make_record("bullish", 0.7, 0.2, True) for _ in range(4)]
    result = divergence_correlation(records, 30)
    assert result["correlation"] == 0.0
