import json
from unittest.mock import AsyncMock, patch

import pytest
from schemas.state import AnalysisState
from worker.nodes.council import run_council


def _make_state(divergence: float = 0.0) -> AnalysisState:
    state = AnalysisState(user_query="Analyze Reliance", ticker_universe=["RELIANCE.NS"])
    state.divergence_score = divergence
    state.confidence = 0.6
    state.market_data = {
        "RELIANCE.NS": {"fundamentals": {"pe_ratio": 28.0, "roe": 0.12}}
    }
    state.sentiment = {"RELIANCE.NS": {"headlines": [{"title": "Strong Q4 results"}]}}
    state.rotation = {
        "points": [{"ticker": "RELIANCE.NS", "rs_ratio": 105.0, "rs_momentum": 102.0}]
    }
    state.alt_data = {"fii_dii": {"fii_net": 500.0, "dii_net": -100.0}}
    return state


def _bullish_json(persona: str = "TestPersona") -> str:
    return json.dumps({
        "persona": persona,
        "stance": "bullish",
        "rationale": f"{persona} sees bullish signals.",
        "confidence": 0.8,
        "citations": ["FII net positive"],
    })


@pytest.mark.asyncio
async def test_run_council_produces_five_outputs():
    with patch("worker.nodes.council.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = lambda sys, usr, tier: _bullish_json()
        state = await run_council(_make_state())
    assert len(state.council_outputs) == 5


@pytest.mark.asyncio
async def test_run_council_updates_confidence_upward_when_unanimous():
    # Unanimous bullish → disagreement=0.0 → confidence = 0.5*(1-0) + 0.5*0.6 = 0.8
    with patch("worker.nodes.council.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = lambda sys, usr, tier: _bullish_json()
        state = _make_state()
        state.confidence = 0.6
        result = await run_council(state)
    assert result.confidence == pytest.approx(0.8, abs=0.01)


@pytest.mark.asyncio
async def test_reconciliation_terminates_and_returns_five_outputs():
    """Verify the reconciliation loop always terminates regardless of LLM responses."""
    calls: list[int] = []

    async def mixed_llm(sys_prompt: str, user_msg: str, tier: object) -> str:
        calls.append(1)
        # Alternate stance to force persistent disagreement
        stance = "bullish" if len(calls) % 2 == 1 else "bearish"
        return json.dumps({
            "persona": "TestPersona",
            "stance": stance,
            "rationale": "test",
            "confidence": 0.7,
            "citations": [],
        })

    with patch("worker.nodes.council.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = mixed_llm
        state = await run_council(_make_state())

    assert len(state.council_outputs) == 5
    # 5 initial + up to 3 rounds * up to 4 dissenters + retries = bounded
    assert len(calls) <= 30


@pytest.mark.asyncio
async def test_parse_failure_does_not_crash_node():
    with patch("worker.nodes.council.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "this is not json at all"
        state = await run_council(_make_state())
    # All outputs fall back to neutral — node must not raise
    assert len(state.council_outputs) == 5
    assert all(o.stance == "neutral" for o in state.council_outputs)


@pytest.mark.asyncio
async def test_audit_log_has_council_entries():
    with patch("worker.nodes.council.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = lambda sys, usr, tier: _bullish_json()
        state = await run_council(_make_state())
    council_entries = [e for e in state.audit_log if e.node == "run_council"]
    assert len(council_entries) >= 2  # at minimum: "starting" and "complete"


@pytest.mark.asyncio
async def test_llm_exception_returns_neutral_does_not_crash():
    """If call_llm raises, the node must not raise — returns neutral outputs."""
    with patch("worker.nodes.council.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = ConnectionError("LLM unavailable")
        state = await run_council(_make_state())
    assert len(state.council_outputs) == 5
    assert all(o.stance == "neutral" for o in state.council_outputs)
