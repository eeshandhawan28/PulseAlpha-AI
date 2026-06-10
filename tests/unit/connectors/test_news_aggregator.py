from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from connectors.news_aggregator import NewsAggregatorConnector, _company_name

# ── Unit tests for the company name resolver ──────────────────────────────


def test_company_name_known_ticker():
    assert _company_name("HDFCBANK.NS") == "HDFC Bank"


def test_company_name_unknown_ticker():
    # Unknown ticker — strips suffix and returns base
    assert _company_name("SUNPHARMA.NS") == "SUNPHARMA"


def test_company_name_strips_bo_suffix():
    assert _company_name("RELIANCE.BO") == "Reliance Industries"


# ── Integration-style tests with mocked HTTP ──────────────────────────────

SAMPLE_FEED_ENTRY = MagicMock()
SAMPLE_FEED_ENTRY.title = "HDFC Bank Q4 profit rises 23%"
SAMPLE_FEED_ENTRY.link = "https://economictimes.indiatimes.com/hdfc-bank-q4"
SAMPLE_FEED_ENTRY.published = "29 May 2026"
SAMPLE_FEED_ENTRY.get = lambda k, d=None: {"source": {"title": "Economic Times"}}.get(k, d)

SAMPLE_ARTICLE_HTML = """
<html><body>
<article>
  <p>HDFC Bank reported a 23% year-on-year rise in net profit for Q4FY26.</p>
  <p>Net interest income grew 10% to Rs 29,077 crore, beating estimates.</p>
  <p>The board declared a dividend of Rs 19 per share.</p>
</article>
</body></html>
"""


@pytest.mark.asyncio
async def test_news_aggregator_returns_articles():
    mock_feed = MagicMock()
    mock_feed.entries = [SAMPLE_FEED_ENTRY]

    mock_article_resp = MagicMock()
    mock_article_resp.text = SAMPLE_ARTICLE_HTML
    mock_article_resp.status_code = 200

    mock_http_client = MagicMock()
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)
    mock_http_client.get = AsyncMock(return_value=mock_article_resp)

    with (
        patch("connectors.news_aggregator.feedparser.parse", return_value=mock_feed),
        patch("connectors.news_aggregator.httpx.AsyncClient", return_value=mock_http_client),
    ):
        result = await NewsAggregatorConnector().fetch("HDFCBANK.NS")

    assert result.ok
    assert len(result.data["articles"]) == 1
    assert "HDFC Bank" in result.data["articles"][0]["title"]
    assert len(result.data["articles"][0]["summary"]) > 0


@pytest.mark.asyncio
async def test_news_aggregator_empty_feed_returns_error():
    mock_feed = MagicMock()
    mock_feed.entries = []

    with patch("connectors.news_aggregator.feedparser.parse", return_value=mock_feed):
        result = await NewsAggregatorConnector().fetch("HDFCBANK.NS")

    assert not result.ok
    assert result.error.code == "NO_RESULTS"


@pytest.mark.asyncio
async def test_news_aggregator_article_fetch_failure_skipped():
    """If fetching an article fails, it is skipped — not a fatal error."""
    mock_feed = MagicMock()
    mock_feed.entries = [SAMPLE_FEED_ENTRY]

    mock_http_client = MagicMock()
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)
    mock_http_client.get = AsyncMock(side_effect=Exception("timeout"))

    with (
        patch("connectors.news_aggregator.feedparser.parse", return_value=mock_feed),
        patch("connectors.news_aggregator.httpx.AsyncClient", return_value=mock_http_client),
    ):
        result = await NewsAggregatorConnector().fetch("HDFCBANK.NS")

    # Article is still returned — just with empty summary
    assert result.ok
    assert result.data["articles"][0]["summary"] == ""


@pytest.mark.asyncio
async def test_news_aggregator_backtest_mode_returns_empty():
    from datetime import date

    result = await NewsAggregatorConnector(as_of_date=date(2025, 1, 1)).fetch("TCS.NS")
    assert result.data == {}
    assert result.confidence == 0.0
    assert not result.ok
