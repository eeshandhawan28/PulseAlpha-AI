from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from connectors.nse_document_fetcher import NSEDocumentFetcher

SAMPLE_API_RESPONSE = [
    {"fileName": "/corporates/annualreports/RELIANCE-2024-25.pdf", "year": "2024-25"},
    {"fileName": "/corporates/annualreports/RELIANCE-2023-24.pdf", "year": "2023-24"},
    {"fileName": "/corporates/annualreports/RELIANCE-2022-23.pdf", "year": "2022-23"},
]


# ---------------------------------------------------------------------------
# _parse_pdf_urls tests (synchronous helpers, no HTTP)
# ---------------------------------------------------------------------------


def test_parse_pdf_urls_returns_sorted_list():
    fetcher = NSEDocumentFetcher()
    # Feed unsorted input — should come back sorted by year descending
    unsorted = [
        {"fileName": "/corporates/annualreports/RELIANCE-2022-23.pdf", "year": "2022-23"},
        {"fileName": "/corporates/annualreports/RELIANCE-2024-25.pdf", "year": "2024-25"},
        {"fileName": "/corporates/annualreports/RELIANCE-2023-24.pdf", "year": "2023-24"},
    ]
    result = fetcher._parse_pdf_urls(unsorted)
    assert len(result) == 3
    assert result[0]["year"] == "2024-25"
    assert result[1]["year"] == "2023-24"
    assert result[2]["year"] == "2022-23"
    # Full URL must be constructed
    assert (
        result[0]["pdf_url"]
        == "https://www.nseindia.com/corporates/annualreports/RELIANCE-2024-25.pdf"
    )


def test_parse_pdf_urls_handles_empty_input():
    fetcher = NSEDocumentFetcher()
    result = fetcher._parse_pdf_urls([])
    assert result == []


def test_parse_pdf_urls_skips_items_missing_fields():
    fetcher = NSEDocumentFetcher()
    data = [
        {"fileName": "/corporates/annualreports/RELIANCE-2024-25.pdf", "year": "2024-25"},
        {"year": "2023-24"},  # missing fileName
        {"fileName": "/corporates/annualreports/RELIANCE-2022-23.pdf"},  # missing year
        {},  # missing both
    ]
    result = fetcher._parse_pdf_urls(data)
    assert len(result) == 1
    assert result[0]["year"] == "2024-25"


# ---------------------------------------------------------------------------
# fetch_latest_annual_report_pdf integration tests (mocked HTTP)
# ---------------------------------------------------------------------------


def _make_stream_ctx(content_type="application/pdf", data=b"%PDF-1.4 fake"):
    """Build a mock for client.stream() used as an async context manager."""
    stream_response = MagicMock()
    stream_response.headers = {"content-type": content_type}
    stream_response.raise_for_status = MagicMock()

    async def aiter_bytes(chunk_size=8192):
        yield data

    stream_response.aiter_bytes = aiter_bytes
    stream_ctx = MagicMock()
    stream_ctx.__aenter__ = AsyncMock(return_value=stream_response)
    stream_ctx.__aexit__ = AsyncMock(return_value=False)
    return stream_ctx


def _make_client_mock(
    json_payload,
    stream_content_type="application/pdf",
    stream_data=b"%PDF-1.4 fake",
):
    home_resp = AsyncMock()
    home_resp.raise_for_status = MagicMock()

    api_resp = AsyncMock()
    api_resp.headers = {"content-type": "application/json"}
    api_resp.json = MagicMock(return_value=json_payload)
    api_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=[home_resp, api_resp])
    mock_client.stream = MagicMock(return_value=_make_stream_ctx(stream_content_type, stream_data))
    return mock_client


@pytest.mark.asyncio
async def test_fetch_returns_none_on_empty_api_response():
    mock_client = _make_client_mock(json_payload=[])
    with patch("connectors.nse_document_fetcher.httpx.AsyncClient", return_value=mock_client):
        fetcher = NSEDocumentFetcher()
        result = await fetcher.fetch_latest_annual_report_pdf("RELIANCE")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_returns_none_on_http_error():
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.HTTPError("connection failed"))

    with patch("connectors.nse_document_fetcher.httpx.AsyncClient", return_value=mock_client):
        fetcher = NSEDocumentFetcher()
        result = await fetcher.fetch_latest_annual_report_pdf("RELIANCE")
    assert result is None


@pytest.mark.asyncio
async def test_download_raises_on_non_pdf_content_type():
    fetcher = NSEDocumentFetcher()
    mock_client = MagicMock()
    stream_ctx = _make_stream_ctx(content_type="text/html", data=b"<html></html>")
    mock_client.stream = MagicMock(return_value=stream_ctx)

    with pytest.raises(ValueError, match="pdf"):
        await fetcher._download_pdf(mock_client, "https://www.nseindia.com/some.pdf")
