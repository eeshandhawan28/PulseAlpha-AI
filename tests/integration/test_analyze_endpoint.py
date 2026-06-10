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
        error=ConnectorError(code="FETCH_ERROR", message="mocked failure"),
    )


@pytest.fixture()
def mock_connectors():
    ohlcv = [{"date": f"2026-01-{i + 1:02d}", "close": 100.0 + i} for i in range(30)]
    bench_ohlcv = [{"date": f"2026-01-{i + 1:02d}", "close": 200.0 + i} for i in range(30)]

    with (
        patch("worker.nodes.ingest.FundamentalsConnector") as MockFund,
        patch("worker.nodes.ingest.MarketDataConnector") as MockMD,
        patch("worker.nodes.ingest.FIIDIIConnector") as MockFII,
        patch("worker.nodes.ingest.SentimentConnector") as MockSent,
        patch("worker.nodes.ingest.IPOGMPConnector") as MockGMP,
    ):

        async def md_side_effect(ticker: str) -> ConnectorResult:
            if ticker == "^NSEI":
                return _ok("md", "^NSEI", {"ohlcv": bench_ohlcv})
            return _ok("md", ticker, {"ohlcv": ohlcv})

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
        yield


@pytest.mark.asyncio
async def test_analyze_returns_200(mock_connectors):
    from api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/analyze",
            json={
                "ticker_universe": ["RELIANCE.NS"],
                "user_query": "Analyze Reliance",
            },
        )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_analyze_returns_valid_state_fields(mock_connectors):
    from api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/analyze",
            json={
                "ticker_universe": ["RELIANCE.NS"],
                "user_query": "Analyze Reliance",
            },
        )
    body = r.json()
    assert "run_id" in body
    assert "divergence_score" in body
    assert "confidence" in body
    assert "audit_log" in body
    assert isinstance(body["audit_log"], list)
    assert len(body["audit_log"]) > 0


@pytest.mark.asyncio
async def test_analyze_missing_ticker_universe_returns_422():
    from api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/analyze", json={"user_query": "test"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_analyze_empty_ticker_universe_returns_422():
    from api.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/analyze",
            json={
                "ticker_universe": [],
                "user_query": "test",
            },
        )
    assert r.status_code == 422
