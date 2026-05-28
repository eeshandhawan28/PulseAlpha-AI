from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from connectors.fii_dii import FIIDIIConnector

SAMPLE_JSON = [
    {"category": "FII/FPI", "buyValue": "45234.56", "sellValue": "38921.12", "netValue": "6313.44"},
    {"category": "DII", "buyValue": "28456.78", "sellValue": "31234.90", "netValue": "-2778.12"},
]


@pytest.mark.asyncio
async def test_fii_dii_parses_flows():
    with patch("connectors.fii_dii.httpx.AsyncClient") as M:
        resp = AsyncMock()
        resp.json = MagicMock(return_value=SAMPLE_JSON)
        resp.raise_for_status = MagicMock()
        M.return_value.__aenter__.return_value.get = AsyncMock(return_value=resp)
        result = await FIIDIIConnector().fetch("MARKET")
    assert result.data["fii_net"] == 6313.44
    assert result.data["dii_net"] == -2778.12


@pytest.mark.asyncio
async def test_fii_dii_parse_error():
    with patch("connectors.fii_dii.httpx.AsyncClient") as M:
        resp = AsyncMock()
        resp.json = MagicMock(return_value=[])
        resp.raise_for_status = MagicMock()
        M.return_value.__aenter__.return_value.get = AsyncMock(return_value=resp)
        result = await FIIDIIConnector().fetch("MARKET")
    assert result.error.code == "PARSE_ERROR"
