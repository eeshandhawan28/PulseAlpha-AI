import pytest
from unittest.mock import AsyncMock, patch

from schemas.connectors import ConnectorError, ConnectorResult
from schemas.state import AnalysisState

from worker.nodes.ingest import ingest_all_data


def _ok_result(source: str, ticker: str, data: dict) -> ConnectorResult:
    return ConnectorResult(source=source, ticker=ticker, data=data, confidence=0.9)


def _err_result(source: str, ticker: str) -> ConnectorResult:
    return ConnectorResult(
        source=source,
        ticker=ticker,
        data={},
        confidence=0.0,
        error=ConnectorError(code="FETCH_ERROR", message="fail"),
    )


def _make_state() -> AnalysisState:
    return AnalysisState(user_query="test", ticker_universe=["RELIANCE.NS"])


@pytest.mark.asyncio
async def test_ingest_populates_state_on_success():
    state = _make_state()
    ohlcv = [{"date": "2026-01-01", "close": 100.0}]
    with (
        patch("worker.nodes.ingest.FundamentalsConnector") as MockFund,
        patch("worker.nodes.ingest.MarketDataConnector") as MockMD,
        patch("worker.nodes.ingest.FIIDIIConnector") as MockFII,
        patch("worker.nodes.ingest.SentimentConnector") as MockSent,
        patch("worker.nodes.ingest.IPOGMPConnector") as MockGMP,
    ):
        MockFund.return_value.fetch = AsyncMock(
            return_value=_ok_result("fund", "RELIANCE.NS", {"pe_ratio": 28.0})
        )
        MockMD.return_value.fetch = AsyncMock(
            return_value=_ok_result("md", "RELIANCE.NS", {"ohlcv": ohlcv})
        )
        MockFII.return_value.fetch = AsyncMock(
            return_value=_ok_result("fii", "MARKET", {"fii_net": 100.0, "dii_net": -50.0})
        )
        MockSent.return_value.fetch = AsyncMock(
            return_value=_ok_result("sent", "RELIANCE.NS", {"headlines": []})
        )
        MockGMP.return_value.fetch = AsyncMock(
            return_value=_ok_result("gmp", "RELIANCE", {"gmp": 50.0, "issue_price": 100.0})
        )
        result = await ingest_all_data(state)

    assert "RELIANCE.NS" in result.market_data
    assert result.market_data["RELIANCE.NS"]["fundamentals"]["pe_ratio"] == 28.0
    assert result.market_data["RELIANCE.NS"]["ohlcv"] == ohlcv
    assert result.alt_data["fii_dii"] is not None
    assert "gmp_connector" in result.alt_data  # key always present (value may be None on failure)
    assert result.sentiment["RELIANCE.NS"] is not None
    assert len(result.audit_log) > 0


@pytest.mark.asyncio
async def test_ingest_handles_partial_failure():
    state = _make_state()
    with (
        patch("worker.nodes.ingest.FundamentalsConnector") as MockFund,
        patch("worker.nodes.ingest.MarketDataConnector") as MockMD,
        patch("worker.nodes.ingest.FIIDIIConnector") as MockFII,
        patch("worker.nodes.ingest.SentimentConnector") as MockSent,
        patch("worker.nodes.ingest.IPOGMPConnector") as MockGMP,
    ):
        MockFund.return_value.fetch = AsyncMock(
            return_value=_err_result("fund", "RELIANCE.NS")
        )
        MockMD.return_value.fetch = AsyncMock(
            return_value=_ok_result("md", "RELIANCE.NS", {"ohlcv": []})
        )
        MockFII.return_value.fetch = AsyncMock(
            return_value=_err_result("fii", "MARKET")
        )
        MockSent.return_value.fetch = AsyncMock(
            return_value=_ok_result("sent", "RELIANCE.NS", {"headlines": []})
        )
        MockGMP.return_value.fetch = AsyncMock(
            return_value=_err_result("gmp", "RELIANCE")
        )
        result = await ingest_all_data(state)

    # Node must not raise — partial failures are tolerated
    assert isinstance(result, AnalysisState)
    # Failed connectors write None
    assert result.market_data["RELIANCE.NS"]["fundamentals"] is None
    assert result.alt_data["fii_dii"] is None
    # Audit log must record failures
    failure_entries = [e for e in result.audit_log if "error" in e.message.lower() or "failed" in e.message.lower()]
    assert len(failure_entries) >= 2


@pytest.mark.asyncio
async def test_ingest_never_raises_on_all_failures():
    state = _make_state()
    with (
        patch("worker.nodes.ingest.FundamentalsConnector") as MockFund,
        patch("worker.nodes.ingest.MarketDataConnector") as MockMD,
        patch("worker.nodes.ingest.FIIDIIConnector") as MockFII,
        patch("worker.nodes.ingest.SentimentConnector") as MockSent,
        patch("worker.nodes.ingest.IPOGMPConnector") as MockGMP,
    ):
        for M in [MockFund, MockMD, MockFII, MockSent, MockGMP]:
            M.return_value.fetch = AsyncMock(side_effect=Exception("total failure"))
        result = await ingest_all_data(state)

    assert isinstance(result, AnalysisState)
