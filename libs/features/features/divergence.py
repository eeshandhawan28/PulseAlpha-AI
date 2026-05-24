from __future__ import annotations

from typing import Literal

from schemas.features import DivergenceResult, FlowStrengthResult, IPOGMPResult, RRGPoint

_Direction = Literal["bullish", "bearish", "neutral"]

_WEIGHTS: dict[str, float] = {
    "rrg": 0.30,
    "fii_zscore": 0.25,
    "fii_ratio": 0.15,
    "dii_zscore": 0.15,
    "sentiment": 0.15,
}

_ZSCORE_THRESHOLD = 0.5
_RATIO_THRESHOLD = 0.1
_SENTIMENT_THRESHOLD = 0.1


def _rrg_vote(point: RRGPoint) -> _Direction:
    if point.quadrant in ("Leading", "Improving"):
        return "bullish"
    elif point.quadrant in ("Lagging", "Weakening"):
        return "bearish"
    return "neutral"


def _zscore_vote(z: float) -> _Direction:
    if z > _ZSCORE_THRESHOLD:
        return "bullish"
    elif z < -_ZSCORE_THRESHOLD:
        return "bearish"
    return "neutral"


def _ratio_vote(r: float) -> _Direction:
    if r > _RATIO_THRESHOLD:
        return "bullish"
    elif r < -_RATIO_THRESHOLD:
        return "bearish"
    return "neutral"


def _sentiment_vote(polarity: float) -> _Direction:
    if polarity > _SENTIMENT_THRESHOLD:
        return "bullish"
    elif polarity < -_SENTIMENT_THRESHOLD:
        return "bearish"
    return "neutral"


def _majority(votes: dict[str, str]) -> _Direction:
    non_neutral = [v for v in votes.values() if v != "neutral"]
    if not non_neutral:
        return "neutral"
    bullish = sum(1 for v in non_neutral if v == "bullish")
    bearish = len(non_neutral) - bullish
    return "bullish" if bullish >= bearish else "bearish"


def _build_contradictions(votes: dict[str, str], majority_dir: str) -> list[str]:
    """Deduplicated human-readable conflict strings for signals disagreeing with majority."""
    outliers = {s: v for s, v in votes.items() if v != "neutral" and v != majority_dir}
    aligned = {s: v for s, v in votes.items() if v != "neutral" and v == majority_dir}

    seen: set[frozenset[str]] = set()
    result: list[str] = []

    for out_signal, out_vote in outliers.items():
        for aln_signal, aln_vote in aligned.items():
            key = frozenset({out_signal, aln_signal})
            if key not in seen:
                seen.add(key)
                result.append(f"{out_signal}={out_vote} conflicts with {aln_signal}={aln_vote}")

    return result


def compute_divergence(
    rrg: RRGPoint,
    flow: FlowStrengthResult,
    sentiment_polarity: float,
    gmp: IPOGMPResult | None = None,
) -> DivergenceResult:
    """Detect conflicts across technical, flow, and sentiment signals.

    Args:
        rrg: RRGPoint for the ticker (single ticker's latest quadrant position).
        flow: FII/DII flow strength metrics for the current session.
        sentiment_polarity: Aggregate sentiment polarity float in [-1, 1].
        gmp: Reserved for future use (Phase 3). GMP is a per-IPO signal
             and will be incorporated once the LangGraph node layer is wired.
             Currently excluded from signal_votes regardless of value.

    Returns:
        DivergenceResult with score [0, 1], contradiction strings, and signal votes.
    """
    votes: dict[str, str] = {
        "rrg": _rrg_vote(rrg),
        "fii_zscore": _zscore_vote(flow.fii_zscore),
        "fii_ratio": _ratio_vote(flow.fii_ratio),
        "dii_zscore": _zscore_vote(flow.dii_zscore),
        "sentiment": _sentiment_vote(sentiment_polarity),
    }

    majority_dir = _majority(votes)

    # Weighted score: sum weights of signals conflicting with majority
    score = sum(
        _WEIGHTS.get(signal, 0.0)
        for signal, vote in votes.items()
        if vote != "neutral" and vote != majority_dir
    )

    contradictions = _build_contradictions(votes, majority_dir)

    return DivergenceResult(
        divergence_score=min(score, 1.0),
        contradictions=contradictions,
        majority_direction=majority_dir,
        signal_votes=votes,
    )
