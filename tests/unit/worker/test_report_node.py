from unittest.mock import AsyncMock, patch

import pytest
from schemas.state import AnalysisState, CouncilOutput
from worker.nodes.report import generate_report

_VALID_REPORT = """\
## Executive Summary
Reliance shows bullish momentum [SRC:COUNCIL_STANCES:Contrarian] with strong FII flows.

## Market Context
FII net inflows of 500Cr [SRC:FII_DII_FLOWS:fii_net] indicate institutional buying.

## Per-Ticker Analysis
### RELIANCE.NS
PE ratio of 28 [SRC:RELIANCE.NS_FUNDAMENTALS:pe_ratio] is below sector average.

## Council Debate Summary
Four of five personas [SRC:COUNCIL_STANCES:Synthesizer] were bullish after reconciliation.

## Contradictions & Risk Flags
No major contradictions [SRC:DIVERGENCE_SUMMARY:score] detected.

## Recommended Actions
Buy RELIANCE.NS [SRC:COUNCIL_STANCES:Expansionist] on dips.

## Confidence & Data Provenance
Overall confidence: 0.75 [SRC:DIVERGENCE_SUMMARY:confidence].
"""


def _make_state() -> AnalysisState:
    state = AnalysisState(user_query="Analyze Reliance", ticker_universe=["RELIANCE.NS"])
    state.confidence = 0.75
    state.divergence_score = 0.2
    state.market_data = {
        "RELIANCE.NS": {
            "fundamentals": {"pe_ratio": 28.0, "roe": 0.12},
            "ohlcv": [{"date": "2026-01-01", "close": 100.0}],
        }
    }
    state.alt_data = {"fii_dii": {"fii_net": 500.0, "dii_net": -100.0}}
    state.council_outputs = [
        CouncilOutput(persona="Contrarian", stance="bullish", rationale="r", confidence=0.8),
        CouncilOutput(persona="FirstPrinciples", stance="bullish", rationale="r", confidence=0.9),
        CouncilOutput(persona="Expansionist", stance="bullish", rationale="r", confidence=0.85),
        CouncilOutput(persona="Outsider", stance="neutral", rationale="r", confidence=0.6),
        CouncilOutput(persona="Synthesizer", stance="bullish", rationale="r", confidence=0.75),
    ]
    return state


@pytest.mark.asyncio
async def test_valid_llm_response_sets_report():
    with patch("worker.nodes.report.call_report_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _VALID_REPORT
        state = await generate_report(_make_state())
    assert state.report is not None
    assert len(state.report) >= 100
    assert "## Executive Summary" in state.report


@pytest.mark.asyncio
async def test_valid_llm_response_populates_citations():
    with patch("worker.nodes.report.call_report_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _VALID_REPORT
        state = await generate_report(_make_state())
    assert isinstance(state.citations, list)
    assert len(state.citations) > 0


@pytest.mark.asyncio
async def test_empty_llm_response_writes_fallback_report():
    with patch("worker.nodes.report.call_report_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = ""
        state = await generate_report(_make_state())
    assert state.report is not None
    assert "Report Generation Failed" in state.report
    assert "0.75" in state.report  # confidence injected


@pytest.mark.asyncio
async def test_short_llm_response_writes_fallback_report():
    with patch("worker.nodes.report.call_report_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "Too short"
        state = await generate_report(_make_state())
    assert "Report Generation Failed" in state.report


@pytest.mark.asyncio
async def test_llm_raises_writes_fallback_does_not_crash():
    with patch("worker.nodes.report.call_report_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = ConnectionError("LLM unavailable")
        state = await generate_report(_make_state())
    assert state.report is not None
    assert "Report Generation Failed" in state.report


@pytest.mark.asyncio
async def test_low_confidence_citation_is_flagged():
    # COUNCIL_STANCES will have low avg confidence if all outputs have confidence=0.1
    s = _make_state()
    s.council_outputs = [
        CouncilOutput(persona="Contrarian", stance="bullish", rationale="r", confidence=0.1),
        CouncilOutput(persona="FirstPrinciples", stance="bullish", rationale="r", confidence=0.1),
        CouncilOutput(persona="Expansionist", stance="bullish", rationale="r", confidence=0.1),
        CouncilOutput(persona="Outsider", stance="bullish", rationale="r", confidence=0.1),
        CouncilOutput(persona="Synthesizer", stance="bullish", rationale="r", confidence=0.1),
    ]
    report_text = "Bullish [SRC:COUNCIL_STANCES:Contrarian] overall."
    with patch("worker.nodes.report.call_report_llm", new_callable=AsyncMock) as mock_llm:
        # Pad to > 100 chars
        mock_llm.return_value = report_text + " " * 200
        state = await generate_report(s)
    assert any("⚠" in c.claim for c in state.citations)


@pytest.mark.asyncio
async def test_audit_log_has_generate_report_entries():
    with patch("worker.nodes.report.call_report_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _VALID_REPORT
        state = await generate_report(_make_state())
    entries = [e for e in state.audit_log if e.node == "generate_report"]
    assert len(entries) >= 1
