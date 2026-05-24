import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from connectors.market_data import MarketDataConnector
from schemas.connectors import ConnectorResult


def _make_history() -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=60, freq="B")
    return pd.DataFrame({
        "Open": [100.0] * 60,
        "High": [105.0] * 60,
        "Low": [98.0] * 60,
        "Close": [102.0] * 60,
        "Volume": [1_000_000] * 60,
    }, index=dates)


@pytest.mark.asyncio
async def test_market_data_returns_ohlcv_records():
    with patch("connectors.market_data.yf.Ticker") as MockTicker:
        MockTicker.return_value.history.return_value = _make_history()
        result = await MarketDataConnector().fetch("RELIANCE.NS")
    assert isinstance(result, ConnectorResult)
    assert result.ok
    assert result.source == "yfinance_market_data"
    records = result.data["ohlcv"]
    assert isinstance(records, list)
    assert len(records) == 60
    assert "date" in records[0]
    assert "close" in records[0]


@pytest.mark.asyncio
async def test_market_data_confidence_based_on_row_count():
    short_history = _make_history().iloc[:5]
    with patch("connectors.market_data.yf.Ticker") as MockTicker:
        MockTicker.return_value.history.return_value = short_history
        result = await MarketDataConnector().fetch("THIN.NS")
    assert result.ok
    assert result.confidence < 0.5


@pytest.mark.asyncio
async def test_market_data_empty_history_returns_error():
    with patch("connectors.market_data.yf.Ticker") as MockTicker:
        MockTicker.return_value.history.return_value = pd.DataFrame()
        result = await MarketDataConnector().fetch("EMPTY.NS")
    assert not result.ok
    assert result.error is not None
    assert result.error.code == "NO_DATA"


@pytest.mark.asyncio
async def test_market_data_network_error():
    with patch("connectors.market_data.yf.Ticker", side_effect=Exception("network")):
        result = await MarketDataConnector().fetch("ERR.NS")
    assert not result.ok
