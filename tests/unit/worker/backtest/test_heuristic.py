from __future__ import annotations

from schemas.state import AnalysisState
from worker.backtest.heuristic import heuristic_stance

_PERSONAS = ["Contrarian", "FirstPrinciples", "Momentum", "Quant", "Macro"]


def _make_state(leading_count: int, total: int = 3) -> AnalysisState:
    tickers = [f"TICK{i}.NS" for i in range(total)]
    rotation = {}
    for i, t in enumerate(tickers):
        rotation[t] = {"quadrant": "Leading" if i < leading_count else "Lagging"}
    return AnalysisState(
        user_query="backtest",
        ticker_universe=tickers,
        rotation=rotation,
    )


def test_majority_leading_produces_bullish() -> None:
    state = _make_state(leading_count=2, total=3)
    result = heuristic_stance(state)
    assert result.confidence == 0.5
    assert result.council_outputs[0].stance == "bullish"
    assert len(result.council_outputs) == 5


def test_minority_leading_produces_bearish() -> None:
    state = _make_state(leading_count=1, total=3)
    result = heuristic_stance(state)
    assert result.council_outputs[0].stance == "bearish"


def test_all_five_personas_written() -> None:
    state = _make_state(leading_count=2, total=3)
    result = heuristic_stance(state)
    personas = [o.persona for o in result.council_outputs]
    for p in _PERSONAS:
        assert p in personas


def test_all_persona_stances_match_overall_stance() -> None:
    state = _make_state(leading_count=2, total=3)
    result = heuristic_stance(state)
    for output in result.council_outputs:
        assert output.stance == "bullish"
        assert output.confidence == 0.5


def test_audit_log_has_entry() -> None:
    state = _make_state(leading_count=2, total=3)
    result = heuristic_stance(state)
    assert any("heuristic" in e.node for e in result.audit_log)
