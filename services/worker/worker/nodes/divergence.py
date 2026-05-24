from __future__ import annotations

import logging
from typing import Any

from features.divergence import compute_divergence
from schemas.features import FlowStrengthResult, RRGPoint
from schemas.state import AnalysisState

logger = logging.getLogger(__name__)

_NODE = "compute_divergence"

_POSITIVE = {"gain", "rise", "rally", "bull", "buy", "surge", "strong", "growth", "profit", "up"}
_NEGATIVE = {"fall", "drop", "crash", "bear", "sell", "weak", "loss", "decline", "down", "slump"}


def _headline_polarity(sentiment: dict[str, Any]) -> float:
    """Compute aggregate sentiment polarity from headlines dict. Returns float in [-1, 1]."""
    if not sentiment:
        return 0.0
    headlines = []
    for ticker_headlines in sentiment.values():
        if isinstance(ticker_headlines, dict):
            headlines.extend(ticker_headlines.get("headlines", []))
    if not headlines:
        return 0.0
    scores = []
    for h in headlines:
        words = h.get("title", "").lower().split()
        pos = sum(1 for w in words if w in _POSITIVE)
        neg = sum(1 for w in words if w in _NEGATIVE)
        total = pos + neg
        if total > 0:
            scores.append((pos - neg) / total)
    return sum(scores) / len(scores) if scores else 0.0


async def compute_divergence_node(state: AnalysisState) -> AnalysisState:
    """Compute divergence score across all RRG points. Averages scores per ticker."""
    flow_data = state.alt_data.get("flow")
    rrg_data = state.rotation

    if not rrg_data or not rrg_data.get("points"):
        state.append_audit(_NODE, "no RRG points — divergence_score set to 0.0")
        state.divergence_score = 0.0
        return state

    if not flow_data:
        state.append_audit(_NODE, "flow data unavailable — divergence_score set to 0.0")
        state.divergence_score = 0.0
        return state

    flow = FlowStrengthResult.model_validate(flow_data)
    sentiment_polarity = _headline_polarity(state.sentiment)

    scores: list[float] = []
    all_contradictions: list[str] = []

    for point_data in rrg_data["points"]:
        point = RRGPoint.model_validate(point_data)
        result = compute_divergence(point, flow, sentiment_polarity)
        scores.append(result.divergence_score)
        all_contradictions.extend(result.contradictions)

    avg_score = sum(scores) / len(scores)
    # Deduplicate contradictions while preserving order
    seen: set[str] = set()
    unique_contradictions: list[str] = []
    for c in all_contradictions:
        if c not in seen:
            seen.add(c)
            unique_contradictions.append(c)

    state.divergence_score = round(avg_score, 4)
    state.contradictions = unique_contradictions
    state.append_audit(
        _NODE,
        "divergence computed",
        score=state.divergence_score,
        tickers_scored=len(scores),
        contradictions=len(unique_contradictions),
    )
    return state
