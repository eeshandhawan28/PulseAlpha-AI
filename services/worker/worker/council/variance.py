from __future__ import annotations

from schemas.state import CouncilOutput


def compute_disagreement(outputs: list[CouncilOutput]) -> float:
    """Compute stance disagreement in [0.0, 1.0].

    0.0 = unanimous. 0.4 = 3/2 split. 0.6 = worst-case 2/2/1 split.
    Formula: 1 - (majority_count / total).
    """
    if not outputs:
        return 0.0
    counts: dict[str, int] = {"bullish": 0, "bearish": 0, "neutral": 0}
    for o in outputs:
        counts[o.stance] += 1
    majority = max(counts.values())
    return 1.0 - (majority / len(outputs))


def majority_stance(outputs: list[CouncilOutput]) -> str:
    """Return the most common stance. Alphabetical tie-breaking for determinism."""
    if not outputs:
        return "neutral"
    counts: dict[str, int] = {"bullish": 0, "bearish": 0, "neutral": 0}
    for o in outputs:
        counts[o.stance] += 1
    return max(counts, key=lambda k: (counts[k], k))
