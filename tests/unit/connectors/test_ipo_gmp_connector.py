from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from connectors.ipo_gmp import IPOGMPConnector

SAMPLE_HTML = """
<table>
  <tr>
    <th>Company</th><th>Issue Price</th><th>GMP</th>
    <th>QIB</th><th>HNI</th><th>Retail</th>
  </tr>
  <tr>
    <td>Reliance Infra IPO</td><td>500</td><td>75</td>
    <td>45.23</td><td>120.5</td><td>8.3</td>
  </tr>
  <tr>
    <td>SBI Life IPO</td><td>800</td><td>20</td>
    <td>5.1</td><td>3.2</td><td>1.1</td>
  </tr>
</table>
"""

NO_TABLE_HTML = "<html><body>No IPO data today</body></html>"


def _mock_client(html: str) -> MagicMock:
    resp = MagicMock()
    resp.text = html
    resp.raise_for_status = MagicMock()
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(return_value=resp)
    return client


@pytest.mark.asyncio
async def test_ipo_gmp_connector_parses_matching_ipo() -> None:
    with patch("connectors.ipo_gmp.httpx.AsyncClient", return_value=_mock_client(SAMPLE_HTML)):
        result = await IPOGMPConnector().fetch("Reliance")
    assert result.ok
    assert result.data["issue_price"] == 500.0
    assert result.data["gmp"] == 75.0
    assert result.data["qib_subscription"] == pytest.approx(45.23)


@pytest.mark.asyncio
async def test_ipo_gmp_connector_second_ipo_found() -> None:
    with patch("connectors.ipo_gmp.httpx.AsyncClient", return_value=_mock_client(SAMPLE_HTML)):
        result = await IPOGMPConnector().fetch("SBI")
    assert result.ok
    assert result.data["issue_price"] == 800.0
    assert result.data["gmp"] == 20.0


@pytest.mark.asyncio
async def test_ipo_gmp_connector_not_found_returns_error() -> None:
    with patch("connectors.ipo_gmp.httpx.AsyncClient", return_value=_mock_client(SAMPLE_HTML)):
        result = await IPOGMPConnector().fetch("NONEXISTENT_COMPANY")
    assert not result.ok
    assert result.error is not None
    assert result.error.code == "NOT_FOUND"
    assert result.error.retryable is False


@pytest.mark.asyncio
async def test_ipo_gmp_connector_parse_error_on_no_table() -> None:
    with patch("connectors.ipo_gmp.httpx.AsyncClient", return_value=_mock_client(NO_TABLE_HTML)):
        result = await IPOGMPConnector().fetch("Any")
    assert not result.ok
    assert result.error is not None
    assert result.error.code == "PARSE_ERROR"
    assert result.error.retryable is False
