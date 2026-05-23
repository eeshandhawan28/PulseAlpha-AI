import pytest
from unittest.mock import patch
from connectors.fundamentals import FundamentalsConnector
from schemas.connectors import ConnectorResult

FULL_INFO = {
    "shortName": "Reliance Industries",
    "sector": "Energy",
    "industry": "Oil & Gas",
    "marketCap": 1_900_000_000_000,
    "trailingPE": 28.5,
    "priceToBook": 2.3,
    "debtToEquity": 45.2,
    "returnOnEquity": 0.12,
    "revenueGrowth": 0.08,
    "earningsGrowth": 0.11,
    "dividendYield": 0.004,
    "currentPrice": 2950.0,
    "fiftyTwoWeekHigh": 3217.0,
    "fiftyTwoWeekLow": 2220.0,
}


@pytest.mark.asyncio
async def test_fundamentals_returns_normalized_result():
    with patch("connectors.fundamentals.yf.Ticker") as MockTicker:
        MockTicker.return_value.info = FULL_INFO
        result = await FundamentalsConnector().fetch("RELIANCE.NS")
    assert isinstance(result, ConnectorResult)
    assert result.data["pe_ratio"] == 28.5
    assert result.data["sector"] == "Energy"
    assert result.confidence > 0.7


@pytest.mark.asyncio
async def test_fundamentals_low_confidence_on_sparse_data():
    with patch("connectors.fundamentals.yf.Ticker") as MockTicker:
        MockTicker.return_value.info = {"shortName": "TestCo"}
        result = await FundamentalsConnector().fetch("FAKE.NS")
    assert result.ok
    assert result.confidence < 0.5


@pytest.mark.asyncio
async def test_fundamentals_error_on_exception():
    with patch("connectors.fundamentals.yf.Ticker", side_effect=Exception("network")):
        result = await FundamentalsConnector().fetch("ERR.NS")
    assert not result.ok
    assert result.error is not None
