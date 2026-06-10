from __future__ import annotations

import logging

from schemas.state import AnalysisState

logger = logging.getLogger(__name__)

_NODE = "normalize_and_validate"


async def normalize_and_validate(state: AnalysisState) -> AnalysisState:
    """Validate state field coverage and set confidence heuristic.

    confidence = (connectors_ok / total_checks) * 0.5 + (1 - divergence_score) * 0.5
    """
    tickers = state.ticker_universe

    checks = [
        any(state.market_data.get(t, {}).get("fundamentals") is not None for t in tickers),
        any(state.market_data.get(t, {}).get("ohlcv") is not None for t in tickers),
        state.alt_data.get("fii_dii") is not None,
        bool(state.rotation),
        any(state.sentiment.get(t) is not None for t in tickers),
    ]

    ok_count = sum(checks)
    total = len(checks)
    connectors_ratio = ok_count / total if total > 0 else 0.0

    confidence = connectors_ratio * 0.5 + (1.0 - state.divergence_score) * 0.5
    state.confidence = round(min(max(confidence, 0.0), 1.0), 4)

    gaps = []
    labels = [
        "fundamentals missing for all tickers",
        "OHLCV missing for all tickers",
        "FII/DII data missing",
        "RRG not computed",
        "sentiment missing for all tickers",
    ]
    for ok, label in zip(checks, labels):
        if not ok:
            gaps.append(label)

    state.append_audit(
        _NODE,
        "validation complete",
        confidence=state.confidence,
        connectors_ok=ok_count,
        total_checks=total,
        gaps=gaps,
    )
    return state
