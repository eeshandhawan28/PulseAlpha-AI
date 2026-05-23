import pytest
from unittest.mock import AsyncMock, patch
from connectors.fii_dii import FIIDIIConnector

SAMPLE_HTML = """
<table>
  <tr><th>Category</th><th>Buy</th><th>Sell</th><th>Net</th></tr>
  <tr><td>FII/FPI</td><td>45234.56</td><td>38921.12</td><td>6313.44</td></tr>
  <tr><td>DII</td><td>28456.78</td><td>31234.90</td><td>-2778.12</td></tr>
</table>
"""


@pytest.mark.asyncio
async def test_fii_dii_parses_flows():
    with patch("connectors.fii_dii.httpx.AsyncClient") as M:
        resp = AsyncMock()
        resp.text = SAMPLE_HTML
        resp.raise_for_status = AsyncMock()
        M.return_value.__aenter__.return_value.get = AsyncMock(return_value=resp)
        result = await FIIDIIConnector().fetch("MARKET")
    assert result.data["fii_net"] == 6313.44
    assert result.data["dii_net"] == -2778.12


@pytest.mark.asyncio
async def test_fii_dii_parse_error():
    with patch("connectors.fii_dii.httpx.AsyncClient") as M:
        resp = AsyncMock()
        resp.text = "<html>no table</html>"
        resp.raise_for_status = AsyncMock()
        M.return_value.__aenter__.return_value.get = AsyncMock(return_value=resp)
        result = await FIIDIIConnector().fetch("MARKET")
    assert result.error.code == "PARSE_ERROR"
