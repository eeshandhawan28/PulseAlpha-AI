import pytest
from unittest.mock import patch
from connectors.nse_quotes import NSEQuotesConnector

MOCK_QUOTE = {
    "companyName": "Reliance Industries",
    "lastPrice": 2950.5,
    "change": 45.2,
    "pChange": 1.55,
    "open": 2905.0,
    "dayHigh": 2960.0,
    "dayLow": 2890.0,
    "totalTradedVolume": 5_200_000,
    "previousClose": 2905.3,
}


@pytest.mark.asyncio
async def test_nse_quotes_returns_normalized():
    with patch("connectors.nse_quotes.Nse") as M:
        M.return_value.get_quote.return_value = MOCK_QUOTE
        result = await NSEQuotesConnector().fetch("RELIANCE")
    assert result.source == "nsetools_quotes"
    assert result.data["last_price"] == 2950.5
    assert result.data["pct_change"] == 1.55


@pytest.mark.asyncio
async def test_nse_quotes_not_found():
    with patch("connectors.nse_quotes.Nse") as M:
        M.return_value.get_quote.return_value = None
        result = await NSEQuotesConnector().fetch("BADTICKER")
    assert result.error is not None
    assert result.error.code == "NOT_FOUND"
