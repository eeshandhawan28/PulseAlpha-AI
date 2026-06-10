import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from schemas.connectors import ConnectorError, ConnectorResult

_MOCK_REPORT = """\
## Executive Summary
Reliance shows bullish momentum [SRC:COUNCIL_STANCES:Contrarian] overall.

## Market Context
FII net inflows [SRC:FII_DII_FLOWS:fii_net] support the bullish case.

## Per-Ticker Analysis
RELIANCE.NS PE of 28 [SRC:RELIANCE.NS_FUNDAMENTALS:pe_ratio] is fair value.

## Council Debate Summary
All personas [SRC:COUNCIL_STANCES:Synthesizer] agreed after round one.

## Contradictions & Risk Flags
No major contradictions [SRC:DIVERGENCE_SUMMARY:score] found.

## Recommended Actions
Buy RELIANCE.NS [SRC:COUNCIL_STANCES:Expansionist] on momentum.

## Confidence & Data Provenance
Confidence 0.75 [SRC:DIVERGENCE_SUMMARY:confidence]. All sources high quality.
"""


def _ok(source: str, ticker: str, data: dict) -> ConnectorResult:
    return ConnectorResult(source=source, ticker=ticker, data=data, confidence=0.9)


def _err(source: str, ticker: str) -> ConnectorResult:
    return ConnectorResult(
        source=source,
        ticker=ticker,
        data={},
        confidence=0.0,
        error=ConnectorError(code="FETCH_ERROR", message="mocked"),
    )


def _bullish_json(persona: str = "TestPersona") -> str:
    return json.dumps(
        {
            "persona": persona,
            "stance": "bullish",
            "rationale": f"{persona} analysis complete.",
            "confidence": 0.8,
            "citations": ["test data point"],
        }
    )


@pytest.fixture()
def mock_all():
    ohlcv = [{"date": f"2026-01-{i + 1:02d}", "close": 100.0 + i} for i in range(30)]
    bench = [{"date": f"2026-01-{i + 1:02d}", "close": 200.0 + i} for i in range(30)]

    async def md_side_effect(ticker: str) -> ConnectorResult:
        if ticker == "^NSEI":
            return _ok("md", "^NSEI", {"ohlcv": bench})
        return _ok("md", ticker, {"ohlcv": ohlcv})

    with (
        patch("worker.nodes.ingest.FundamentalsConnector") as MockFund,
        patch("worker.nodes.ingest.MarketDataConnector") as MockMD,
        patch("worker.nodes.ingest.FIIDIIConnector") as MockFII,
        patch("worker.nodes.ingest.SentimentConnector") as MockSent,
        patch("worker.nodes.ingest.IPOGMPConnector") as MockGMP,
        patch("worker.nodes.council.call_llm", new_callable=AsyncMock) as MockCouncilLLM,
        patch("worker.nodes.report.call_report_llm", new_callable=AsyncMock) as MockReportLLM,
    ):
        MockFund.return_value.fetch = AsyncMock(
            return_value=_ok("fund", "RELIANCE.NS", {"pe_ratio": 28.0, "sector": "Energy"})
        )
        MockMD.return_value.fetch = AsyncMock(side_effect=md_side_effect)
        MockFII.return_value.fetch = AsyncMock(
            return_value=_ok(
                "fii",
                "MARKET",
                {
                    "fii_net": 500.0,
                    "fii_buy": 1000.0,
                    "fii_sell": 500.0,
                    "dii_net": -100.0,
                    "dii_buy": 200.0,
                    "dii_sell": 300.0,
                },
            )
        )
        MockSent.return_value.fetch = AsyncMock(
            return_value=_ok("sent", "RELIANCE.NS", {"headlines": []})
        )
        MockGMP.return_value.fetch = AsyncMock(return_value=_err("gmp", "RELIANCE"))
        MockCouncilLLM.side_effect = lambda sys, usr, tier: _bullish_json()
        MockReportLLM.return_value = _MOCK_REPORT
        yield


@pytest.mark.asyncio
async def test_analyze_returns_report_field(mock_all):
    from api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/analyze",
            json={"ticker_universe": ["RELIANCE.NS"], "user_query": "Analyze Reliance"},
        )
    assert r.status_code == 200
    body = r.json()
    assert "report" in body
    assert isinstance(body["report"], str)
    assert len(body["report"]) > 0


@pytest.mark.asyncio
async def test_analyze_returns_citations_list(mock_all):
    from api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/analyze",
            json={"ticker_universe": ["RELIANCE.NS"], "user_query": "Analyze Reliance"},
        )
    body = r.json()
    assert "citations" in body
    assert isinstance(body["citations"], list)


@pytest.mark.asyncio
async def test_citations_have_required_fields(mock_all):
    from api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/analyze",
            json={"ticker_universe": ["RELIANCE.NS"], "user_query": "Analyze Reliance"},
        )
    body = r.json()
    for citation in body["citations"]:
        assert "claim" in citation
        assert "source" in citation


@pytest.mark.asyncio
async def test_audit_log_contains_report_entry(mock_all):
    from api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/analyze",
            json={"ticker_universe": ["RELIANCE.NS"], "user_query": "Analyze Reliance"},
        )
    body = r.json()
    report_entries = [e for e in body["audit_log"] if e["node"] == "generate_report"]
    assert len(report_entries) >= 1
