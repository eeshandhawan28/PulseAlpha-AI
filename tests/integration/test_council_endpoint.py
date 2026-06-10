import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from schemas.connectors import ConnectorError, ConnectorResult


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
def mock_connectors_and_llm():
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
        patch("worker.nodes.council.call_llm", new_callable=AsyncMock) as MockLLM,
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
        MockLLM.side_effect = lambda sys, usr, tier: _bullish_json()
        yield


@pytest.mark.asyncio
async def test_analyze_returns_council_outputs(mock_connectors_and_llm):
    from api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/analyze",
            json={"ticker_universe": ["RELIANCE.NS"], "user_query": "Analyze Reliance"},
        )
    assert r.status_code == 200
    body = r.json()
    assert "council_outputs" in body
    assert len(body["council_outputs"]) == 5


@pytest.mark.asyncio
async def test_council_outputs_have_required_fields(mock_connectors_and_llm):
    from api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/analyze",
            json={"ticker_universe": ["RELIANCE.NS"], "user_query": "Analyze Reliance"},
        )
    body = r.json()
    for output in body["council_outputs"]:
        assert "persona" in output
        assert "stance" in output
        assert output["stance"] in ("bullish", "bearish", "neutral")
        assert "rationale" in output
        assert "confidence" in output


@pytest.mark.asyncio
async def test_confidence_updated_after_council(mock_connectors_and_llm):
    from api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/analyze",
            json={"ticker_universe": ["RELIANCE.NS"], "user_query": "Analyze Reliance"},
        )
    body = r.json()
    # Unanimous bullish → confidence must be updated above 0
    assert body["confidence"] > 0.0


@pytest.mark.asyncio
async def test_audit_log_contains_council_entry(mock_connectors_and_llm):
    from api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/analyze",
            json={"ticker_universe": ["RELIANCE.NS"], "user_query": "Analyze Reliance"},
        )
    body = r.json()
    council_entries = [e for e in body["audit_log"] if e["node"] == "run_council"]
    assert len(council_entries) >= 2
