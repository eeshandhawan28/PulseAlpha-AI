from __future__ import annotations

import logging
import statistics
from typing import Any

from schemas.backtest import PredictionRecord

logger = logging.getLogger(__name__)

_CALIBRATION_BUCKETS: list[tuple[float, float, str]] = [
    (0.0, 0.4, "0.0-0.4"),
    (0.4, 0.6, "0.4-0.6"),
    (0.6, 0.8, "0.6-0.8"),
    (0.8, 1.01, "0.8-1.0"),
]


def hit_rate(predictions: list[PredictionRecord], horizon: int) -> dict[str, Any]:
    """Directional hit rate at a given horizon. Neutral stances excluded."""
    correct_all: list[bool] = []
    correct_bull: list[bool] = []
    correct_bear: list[bool] = []
    n_neutral = 0

    for p in predictions:
        if p.stance == "neutral":
            n_neutral += 1
            continue
        c = p.correct.get(horizon)
        if c is None:
            continue
        correct_all.append(c)
        if p.stance == "bullish":
            correct_bull.append(c)
        elif p.stance == "bearish":
            correct_bear.append(c)

    def _rate(lst: list[bool]) -> float:
        return sum(lst) / len(lst) if lst else 0.0

    return {
        "overall": _rate(correct_all),
        "bullish": _rate(correct_bull),
        "bearish": _rate(correct_bear),
        "n_evaluated": len(correct_all),
        "n_excluded_neutral": n_neutral,
    }


def confidence_calibration(
    predictions: list[PredictionRecord], horizon: int
) -> list[dict[str, Any]]:
    """Group predictions by confidence bucket and compute accuracy per bucket."""
    buckets: dict[str, list[bool]] = {label: [] for _, _, label in _CALIBRATION_BUCKETS}

    for p in predictions:
        if p.stance == "neutral":
            continue
        c = p.correct.get(horizon)
        if c is None:
            continue
        for lo, hi, label in _CALIBRATION_BUCKETS:
            if lo <= p.confidence < hi:
                buckets[label].append(c)
                break

    result = []
    for _, _, label in _CALIBRATION_BUCKETS:
        items = buckets[label]
        if not items:
            continue
        result.append({
            "bucket": label,
            "accuracy": sum(items) / len(items),
            "n": len(items),
        })
    return result


def persona_accuracy(
    predictions: list[PredictionRecord], horizon: int
) -> dict[str, dict[str, Any]]:
    """Per-persona directional accuracy at a given horizon."""
    persona_data: dict[str, list[bool]] = {}

    for p in predictions:
        outcome = p.outcomes.get(horizon)
        if outcome is None:
            continue
        for persona, persona_stance in p.persona_stances.items():
            if persona_stance == "neutral":
                continue
            if persona not in persona_data:
                persona_data[persona] = []
            persona_correct = (
                (persona_stance == "bullish" and outcome > 0)
                or (persona_stance == "bearish" and outcome < 0)
            )
            persona_data[persona].append(persona_correct)

    return {
        persona: {
            "accuracy": sum(lst) / len(lst) if lst else 0.0,
            "n": len(lst),
        }
        for persona, lst in persona_data.items()
    }


def divergence_correlation(
    predictions: list[PredictionRecord], horizon: int
) -> dict[str, Any]:
    """Pearson correlation between divergence_score and correct (1/0) at horizon."""
    divergences: list[float] = []
    corrects: list[float] = []

    for p in predictions:
        if p.stance == "neutral":
            continue
        c = p.correct.get(horizon)
        if c is None:
            continue
        divergences.append(p.divergence_score)
        corrects.append(1.0 if c else 0.0)

    n = len(divergences)
    if n < 2:
        return {"correlation": 0.0, "n": n}

    try:
        corr = statistics.correlation(divergences, corrects)
    except statistics.StatisticsError:
        corr = 0.0

    return {"correlation": corr, "n": n}
