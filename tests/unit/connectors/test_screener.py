from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from connectors.screener import ScreenerConnector

SAMPLE_HTML = """
<html><body>
  <section id="pros-cons">
    <ul class="pros">
      <li>Company is almost debt free</li>
      <li>Strong ROE consistently above 15%</li>
      <li>Good profit growth of 21% CAGR over last 5 years</li>
    </ul>
    <ul class="cons">
      <li>Promoter holding has decreased over last quarter</li>
      <li>PE ratio higher than industry average</li>
    </ul>
  </section>
  <ul id="top-ratios">
    <li><span class="name">Stock P/E</span><span class="number">20.3</span></li>
    <li><span class="name">Market Cap</span><span class="number">12,32,456</span></li>
    <li><span class="name">ROCE</span><span class="number">17.8 %</span></li>
    <li><span class="name">ROE</span><span class="number">16.9 %</span></li>
  </ul>
  <section>
    <h2>Compounded Sales Growth</h2>
    <table><tbody>
      <tr><td>Sales Growth</td><td>TTM</td><td>18 %</td><td>15 %</td></tr>
      <tr><td>Profit Growth</td><td>TTM</td><td>21 %</td><td>18 %</td></tr>
    </tbody></table>
  </section>
</body></html>
"""

EMPTY_HTML = "<html><body><p>Company not found</p></body></html>"


def _mock_client(html: str, status_code: int = 200):
    resp = MagicMock()
    resp.text = html
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(return_value=resp)
    return client


@pytest.mark.asyncio
async def test_screener_parses_pros_cons():
    with patch("connectors.screener.httpx.AsyncClient", return_value=_mock_client(SAMPLE_HTML)):
        result = await ScreenerConnector().fetch("HDFCBANK.NS")
    assert result.ok
    assert len(result.data["pros"]) == 3
    assert "debt free" in result.data["pros"][0]
    assert len(result.data["cons"]) == 2


@pytest.mark.asyncio
async def test_screener_parses_ratios():
    with patch("connectors.screener.httpx.AsyncClient", return_value=_mock_client(SAMPLE_HTML)):
        result = await ScreenerConnector().fetch("HDFCBANK.NS")
    assert result.ok
    assert "stock_p_e" in result.data["ratios"] or "p_e" in " ".join(result.data["ratios"])
    assert result.confidence >= 0.8


@pytest.mark.asyncio
async def test_screener_404_returns_not_found():
    resp = MagicMock()
    resp.status_code = 404
    resp.text = ""
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(return_value=resp)
    with patch("connectors.screener.httpx.AsyncClient", return_value=client):
        result = await ScreenerConnector().fetch("FAKECO.NS")
    assert not result.ok
    assert result.error.code == "NOT_FOUND"


@pytest.mark.asyncio
async def test_screener_empty_page_returns_parse_error():
    with patch("connectors.screener.httpx.AsyncClient", return_value=_mock_client(EMPTY_HTML)):
        result = await ScreenerConnector().fetch("RELIANCE.NS")
    assert not result.ok
    assert result.error.code == "PARSE_ERROR"


@pytest.mark.asyncio
async def test_screener_strips_ns_suffix():
    client = _mock_client(SAMPLE_HTML)
    with patch("connectors.screener.httpx.AsyncClient", return_value=client):
        await ScreenerConnector().fetch("HDFCBANK.NS")
    call_url = str(client.get.call_args_list[0])
    assert "HDFCBANK" in call_url
    assert ".NS" not in call_url
