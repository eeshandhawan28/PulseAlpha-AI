from __future__ import annotations

from schemas.state import AnalysisState, CouncilOutput

_PERSONAS = ["Contrarian", "FirstPrinciples", "Momentum", "Quant", "Macro"]


def heuristic_stance(state: AnalysisState) -> AnalysisState:
    """Fast-mode stance provider: derives stance from RRG quadrant majority.

    Leading majority -> bullish; otherwise -> bearish.
    All 5 personas assigned the same stance with confidence=0.5.
    No LLM calls.
    """
    rotation = state.rotation or {}
    leading = sum(
        1 for v in rotation.values() if isinstance(v, dict) and v.get("quadrant") == "Leading"
    )
    total = len(rotation)
    stance = "bullish" if total > 0 and leading > total / 2 else "bearish"

    outputs = [
        CouncilOutput(
            persona=p,
            stance=stance,
            rationale="Heuristic: RRG quadrant majority",
            confidence=0.5,
        )
        for p in _PERSONAS
    ]

    state.council_outputs = outputs
    state.confidence = 0.5
    state.append_audit(
        "heuristic_stance",
        f"heuristic stance={stance} leading={leading}/{total}",
    )
    return state
