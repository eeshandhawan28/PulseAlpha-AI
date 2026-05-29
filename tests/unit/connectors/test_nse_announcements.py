from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from connectors.nse_announcements import NSEAnnouncementsConnector

SAMPLE_NSE = [
    {
        "subject": "Board Meeting – Q4 Results",
        "an_dt": "29-May-2026",
        "desc": "Results",
        "attchmntFile": "/corporates/ann/abc.pdf",
    },
    {
        "subject": "Dividend Declaration",
        "an_dt": "15-May-2026",
        "desc": "Dividend",
        "attchmntFile": "",
    },
]


def _make_client_mock(json_payload, content_type="application/json"):
    home_resp = AsyncMock()
    home_resp.raise_for_status = MagicMock()
    api_resp = AsyncMock()
    api_resp.headers = {"content-type": content_type}
    api_resp.json = MagicMock(return_value=json_payload)
    api_resp.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=[home_resp, api_resp])
    return mock_client


@pytest.mark.asyncio
async def test_nse_announcements_parses_correctly():
    with patch("connectors.nse_announcements.httpx.AsyncClient", return_value=_make_client_mock(SAMPLE_NSE)):
        result = await NSEAnnouncementsConnector().fetch("HDFCBANK.NS")
    assert result.ok
    assert len(result.data["announcements"]) == 2
    assert result.data["announcements"][0]["subject"] == "Board Meeting – Q4 Results"
    assert result.data["announcements"][0]["date"] == "29-May-2026"
    assert "nseindia.com" in result.data["announcements"][0]["url"]


@pytest.mark.asyncio
async def test_nse_announcements_html_response_returns_parse_error():
    with patch("connectors.nse_announcements.httpx.AsyncClient", return_value=_make_client_mock("", "text/html")):
        result = await NSEAnnouncementsConnector().fetch("HDFCBANK.NS")
    assert not result.ok
    assert result.error.code == "PARSE_ERROR"


@pytest.mark.asyncio
async def test_nse_announcements_empty_list_returns_parse_error():
    with patch("connectors.nse_announcements.httpx.AsyncClient", return_value=_make_client_mock([])):
        result = await NSEAnnouncementsConnector().fetch("RELIANCE.NS")
    assert not result.ok
    assert result.error.code == "PARSE_ERROR"


@pytest.mark.asyncio
async def test_nse_announcements_strips_ns_suffix():
    mock_client = _make_client_mock(SAMPLE_NSE)
    with patch("connectors.nse_announcements.httpx.AsyncClient", return_value=mock_client):
        await NSEAnnouncementsConnector().fetch("HDFCBANK.NS")
    second_call_args = str(mock_client.get.call_args_list[1])
    assert "HDFCBANK" in second_call_args
    assert ".NS" not in second_call_args


@pytest.mark.asyncio
async def test_nse_announcements_backtest_mode_returns_empty():
    from datetime import date
    result = await NSEAnnouncementsConnector(as_of_date=date(2025, 1, 1)).fetch("TCS.NS")
    assert result.data == {}
    assert result.confidence == 0.0
    assert not result.ok
