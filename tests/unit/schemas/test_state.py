import uuid
import pytest
from datetime import datetime, timezone
from schemas.state import AnalysisState, AuditEntry
from schemas.connectors import ConnectorResult, ConnectorError
from schemas.models import ModelTier, RoutingConfig


def make_run_id() -> str:
    return str(uuid.uuid4())


def test_analysis_state_defaults():
    state = AnalysisState(
        run_id=make_run_id(),
        user_query="Analyze RELIANCE.NS",
        ticker_universe=["RELIANCE.NS"],
    )
    assert state.market_data == {}
    assert state.council_outputs == []
    assert state.confidence == 0.0
    assert state.report is None
    assert state.audit_log == []


def test_analysis_state_rejects_empty_tickers():
    with pytest.raises(ValueError, match="ticker_universe"):
        AnalysisState(
            run_id=make_run_id(),
            user_query="q",
            ticker_universe=[],
        )


def test_audit_entry_has_timestamp():
    entry = AuditEntry(node="ingest_fundamentals", message="fetched 5 tickers")
    assert isinstance(entry.timestamp, datetime)


def test_connector_result_envelope():
    result = ConnectorResult(
        source="yfinance",
        ticker="RELIANCE.NS",
        data={"price": 2950.0},
        confidence=0.95,
    )
    assert result.freshness_utc is not None
    assert result.error is None
    assert result.ok is True


def test_connector_result_with_error():
    result = ConnectorResult(
        source="nsetools",
        ticker="INVALID",
        data={},
        confidence=0.0,
        error=ConnectorError(code="NOT_FOUND", message="Ticker not found"),
    )
    assert result.ok is False
    assert result.error.code == "NOT_FOUND"


def test_routing_config_defaults():
    config = RoutingConfig()
    assert config.default_tier == ModelTier.HF_API
    assert config.daily_paid_cap_usd > 0


def test_ticker_normalisation():
    state = AnalysisState(
        run_id=make_run_id(),
        user_query="q",
        ticker_universe=["reliance.ns", " infy "],
    )
    assert state.ticker_universe == ["RELIANCE.NS", "INFY"]


def test_ticker_whitespace_only_rejected():
    with pytest.raises(ValueError, match="non-empty"):
        AnalysisState(
            run_id=make_run_id(),
            user_query="q",
            ticker_universe=["  "],
        )
