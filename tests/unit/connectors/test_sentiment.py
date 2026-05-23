from unittest.mock import MagicMock, patch

import pytest
from connectors.sentiment import SentimentConnector


@pytest.mark.asyncio
async def test_sentiment_returns_headlines():
    entry = MagicMock()
    entry.title = "Reliance posts strong Q4"
    entry.link = "http://example.com/1"
    entry.get = lambda k, d=None: "" if k == "published" else d

    mock_feed = MagicMock()
    mock_feed.entries = [entry]

    with patch("connectors.sentiment.feedparser.parse", return_value=mock_feed):
        result = await SentimentConnector().fetch("RELIANCE")

    assert result.source == "rss_sentiment"
    assert "headlines" in result.data
    assert any("Reliance" in h["title"] for h in result.data["headlines"])
