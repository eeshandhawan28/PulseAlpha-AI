from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from connectors.nse_document_fetcher import NSEDocumentFetcher

SAMPLE_API_RESPONSE = [
    {"fileName": "/corporates/annualreports/RELIANCE-2024-25.pdf", "year": "2024-25"},
    {"fileName": "/corporates/annualreports/RELIANCE-2023-24.pdf", "year": "2023-24"},
    {"fileName": "/corporates/annualreports/RELIANCE-2022-23.pdf", "year": "2022-23"},
]


# ---------------------------------------------------------------------------
# _parse_nse_pdf_urls — bare list (classic NSE format)
# ---------------------------------------------------------------------------


def test_parse_nse_pdf_urls_returns_sorted_list():
    fetcher = NSEDocumentFetcher()
    unsorted = [
        {"fileName": "/corporates/annualreports/RELIANCE-2022-23.pdf", "year": "2022-23"},
        {"fileName": "/corporates/annualreports/RELIANCE-2024-25.pdf", "year": "2024-25"},
        {"fileName": "/corporates/annualreports/RELIANCE-2023-24.pdf", "year": "2023-24"},
    ]
    result = fetcher._parse_nse_pdf_urls(unsorted)
    assert len(result) == 3
    assert result[0]["year"] == "2024-25"
    assert result[1]["year"] == "2023-24"
    assert result[2]["year"] == "2022-23"
    assert (
        result[0]["pdf_url"]
        == "https://www.nseindia.com/corporates/annualreports/RELIANCE-2024-25.pdf"
    )


def test_parse_nse_pdf_urls_handles_empty_list():
    fetcher = NSEDocumentFetcher()
    assert fetcher._parse_nse_pdf_urls([]) == []


def test_parse_nse_pdf_urls_skips_items_missing_fields():
    fetcher = NSEDocumentFetcher()
    data = [
        {"fileName": "/corporates/annualreports/RELIANCE-2024-25.pdf", "year": "2024-25"},
        {"year": "2023-24"},  # missing fileName
        {"fileName": "/corporates/annualreports/RELIANCE-2022-23.pdf"},  # missing year
        {},  # missing both
    ]
    result = fetcher._parse_nse_pdf_urls(data)
    assert len(result) == 1
    assert result[0]["year"] == "2024-25"


# ---------------------------------------------------------------------------
# _parse_nse_pdf_urls — dict-wrapped response {"data": [...]}
# ---------------------------------------------------------------------------


def test_parse_nse_pdf_urls_handles_dict_wrapper():
    """NSE API sometimes returns {"data": [...]} instead of a bare list."""
    fetcher = NSEDocumentFetcher()
    wrapped = {
        "data": [
            {"fileName": "/corporates/BHARTIARTL-2024-25.pdf", "year": "2024-25"},
            {"fileName": "/corporates/BHARTIARTL-2023-24.pdf", "year": "2023-24"},
        ]
    }
    result = fetcher._parse_nse_pdf_urls(wrapped)
    assert len(result) == 2
    assert result[0]["year"] == "2024-25"


def test_parse_nse_pdf_urls_handles_annualReports_wrapper():
    fetcher = NSEDocumentFetcher()
    wrapped = {
        "annualReports": [
            {"fileName": "/corporates/TCS-2024-25.pdf", "year": "2024-25"},
        ]
    }
    result = fetcher._parse_nse_pdf_urls(wrapped)
    assert len(result) == 1


def test_parse_nse_pdf_urls_returns_empty_for_unknown_dict():
    fetcher = NSEDocumentFetcher()
    result = fetcher._parse_nse_pdf_urls({"message": "No data found"})
    assert result == []


# ---------------------------------------------------------------------------
# _parse_nse_pdf_urls — alternative field names
# ---------------------------------------------------------------------------


def test_parse_nse_pdf_urls_accepts_fileUrl_field():
    fetcher = NSEDocumentFetcher()
    data = [{"fileUrl": "/corporates/INFY-2024-25.pdf", "year": "2024-25"}]
    result = fetcher._parse_nse_pdf_urls(data)
    assert len(result) == 1
    assert result[0]["pdf_url"] == "https://www.nseindia.com/corporates/INFY-2024-25.pdf"


def test_parse_nse_pdf_urls_accepts_absolute_url():
    fetcher = NSEDocumentFetcher()
    data = [{"fileName": "https://external.com/report.pdf", "year": "2024-25"}]
    result = fetcher._parse_nse_pdf_urls(data)
    assert result[0]["pdf_url"] == "https://external.com/report.pdf"


# ---------------------------------------------------------------------------
# _extract_year_from_text
# ---------------------------------------------------------------------------


def test_extract_year_hyphenated():
    fetcher = NSEDocumentFetcher()
    assert fetcher._extract_year_from_text("Annual Report 2023-24") == "2023-24"


def test_extract_year_standalone():
    fetcher = NSEDocumentFetcher()
    assert fetcher._extract_year_from_text("report_2024.pdf") == "2024"


def test_extract_year_no_match():
    fetcher = NSEDocumentFetcher()
    assert fetcher._extract_year_from_text("no year here") == ""


# ---------------------------------------------------------------------------
# Fetch integration tests (mocked HTTP, NSE path only)
# ---------------------------------------------------------------------------


def _make_stream_ctx(content_type: str = "application/pdf", data: bytes = b"%PDF-1.4 fake"):
    stream_response = MagicMock()
    stream_response.headers = {"content-type": content_type}
    stream_response.raise_for_status = MagicMock()

    async def aiter_bytes(chunk_size: int = 8192):
        yield data

    stream_response.aiter_bytes = aiter_bytes
    stream_ctx = MagicMock()
    stream_ctx.__aenter__ = AsyncMock(return_value=stream_response)
    stream_ctx.__aexit__ = AsyncMock(return_value=False)
    return stream_ctx


def _make_nse_client_mock(
    json_payload: object,
    stream_content_type: str = "application/pdf",
    stream_data: bytes = b"%PDF-1.4 fake",
) -> MagicMock:
    home_resp = AsyncMock()
    home_resp.raise_for_status = MagicMock()

    api_resp = AsyncMock()
    api_resp.headers = {"content-type": "application/json"}
    api_resp.json = MagicMock(return_value=json_payload)
    api_resp.raise_for_status = MagicMock()
    api_resp.status_code = 200

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=[home_resp, api_resp])
    mock_client.stream = MagicMock(
        return_value=_make_stream_ctx(stream_content_type, stream_data)
    )
    return mock_client


@pytest.mark.asyncio
async def test_fetch_nse_succeeds_with_bare_list():
    fetcher = NSEDocumentFetcher()
    url = "https://nsearchives.nseindia.com/report.pdf"
    with patch.object(fetcher, "_fetch_from_nse", AsyncMock(return_value=(b"%PDF", "2024-25", url))):
        result = await fetcher.fetch_latest_annual_report_pdf("RELIANCE")
    assert result is not None
    assert result[1] == "2024-25"
    assert result[2] == url


@pytest.mark.asyncio
async def test_fetch_returns_none_when_all_sources_fail():
    fetcher = NSEDocumentFetcher()
    with (
        patch.object(fetcher, "_fetch_from_nse", AsyncMock(return_value=None)),
        patch.object(fetcher, "_fetch_from_screener", AsyncMock(return_value=None)),
        patch.object(fetcher, "_fetch_from_bse", AsyncMock(return_value=None)),
    ):
        result = await fetcher.fetch_latest_annual_report_pdf("UNKNOWN")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_falls_back_to_screener_when_nse_fails():
    url = "https://screener.in/annual-report.pdf"
    fetcher = NSEDocumentFetcher()
    with (
        patch.object(fetcher, "_fetch_from_nse", AsyncMock(return_value=None)),
        patch.object(
            fetcher, "_fetch_from_screener", AsyncMock(return_value=(b"%PDF", "2024-25", url))
        ),
        patch.object(fetcher, "_fetch_from_bse", AsyncMock(return_value=None)),
    ):
        result = await fetcher.fetch_latest_annual_report_pdf("BHARTIARTL")
    assert result is not None
    assert result[1] == "2024-25"
    assert result[2] == url


@pytest.mark.asyncio
async def test_download_raises_on_html_content_type():
    fetcher = NSEDocumentFetcher()
    mock_client = MagicMock()
    stream_ctx = _make_stream_ctx(content_type="text/html", data=b"<html></html>")
    mock_client.stream = MagicMock(return_value=stream_ctx)

    with pytest.raises(ValueError, match="HTML"):
        await fetcher._download_pdf(mock_client, "https://www.nseindia.com/some.pdf")
