"""Tests for DocumentRAGConnector.

Strategy: mock _fetch (the private async method) in every test that calls
connector.fetch() — this ensures chromadb, pdfplumber, and sentence-transformers
are NEVER imported.  Only the pure-Python helpers (_chunk_text, _confidence)
are tested directly without mocking.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from connectors.document_rag import DocumentRAGConnector

_SAMPLE_CHUNKS = [
    "Revenue from operations increased 18% to ₹1,23,456 crore.",
    "The O2C business maintained its leadership position with record throughput.",
    "The business faces commodity price volatility.",
    "A 10% decline in margins would reduce EBITDA by ₹2,400 crore.",
    "The Company actively hedges its exposure through diversified procurement.",
]


# ---------------------------------------------------------------------------
# fetch() behaviour — _fetch is always mocked so no libraries load
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rag_returns_chunks_on_happy_path():
    connector = DocumentRAGConnector(user_query="What are the key risks?")
    with patch.object(
        connector, "_fetch", new_callable=AsyncMock,
        return_value={"chunks": _SAMPLE_CHUNKS, "year": "2024-25", "cache_hit": False},
    ):
        result = await connector.fetch("RELIANCE.NS")

    assert result.ok
    assert result.data["chunks"] == _SAMPLE_CHUNKS
    assert result.data["year"] == "2024-25"
    assert result.confidence == 0.85  # 5 chunks → top tier


@pytest.mark.asyncio
async def test_rag_degrades_silently_on_no_pdf():
    """NO_DOCUMENT error returned when PDF cannot be found."""
    connector = DocumentRAGConnector(user_query="revenue growth")
    with patch.object(
        connector, "_fetch", new_callable=AsyncMock,
        side_effect=ValueError("No annual report PDF found for FAKECO"),
    ):
        result = await connector.fetch("FAKECO.NS")

    assert not result.ok
    assert result.error.code == "NO_DOCUMENT"
    assert result.error.retryable is False
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_rag_degrades_silently_on_unexpected_error():
    """RAG_ERROR returned on any non-ValueError exception."""
    connector = DocumentRAGConnector(user_query="guidance")
    with patch.object(
        connector, "_fetch", new_callable=AsyncMock,
        side_effect=RuntimeError("disk full"),
    ):
        result = await connector.fetch("TCS.NS")

    assert not result.ok
    assert result.error.code == "RAG_ERROR"
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_rag_uses_cache_hit_path():
    """cache_hit=True is propagated through when collection was fresh."""
    connector = DocumentRAGConnector(user_query="revenue growth")
    with patch.object(
        connector, "_fetch", new_callable=AsyncMock,
        return_value={"chunks": _SAMPLE_CHUNKS[:1], "year": "2024-25", "cache_hit": True},
    ):
        result = await connector.fetch("TCS.NS")

    assert result.ok
    assert result.data["cache_hit"] is True


@pytest.mark.asyncio
async def test_rag_returns_zero_confidence_on_empty_chunks():
    """Confidence is 0 when retrieved chunks list is empty."""
    connector = DocumentRAGConnector(user_query="revenue")
    with patch.object(
        connector, "_fetch", new_callable=AsyncMock,
        return_value={"chunks": [], "year": "2024-25", "cache_hit": False},
    ):
        result = await connector.fetch("INFY.NS")

    assert result.ok
    assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# Pure-Python helpers — no I/O, safe to call directly
# ---------------------------------------------------------------------------

def test_chunk_text_produces_overlap():
    """Consecutive chunks share content from the overlap window."""
    connector = DocumentRAGConnector(user_query="test")
    long_text = "word " * 2000  # ~10,000 chars
    chunks = connector._chunk_text(long_text)
    assert len(chunks) >= 3, f"Expected ≥3 chunks, got {len(chunks)}"
    if len(chunks) >= 2:
        tail_words = chunks[0][-200:].split()
        head_text = chunks[1][:500]
        assert any(w in head_text for w in tail_words[-5:]), (
            "Expected overlap between chunk[0] tail and chunk[1] head"
        )


def test_confidence_tiers():
    connector = DocumentRAGConnector(user_query="test")
    assert connector._confidence({"chunks": []}) == 0.0
    assert connector._confidence({"chunks": ["a"]}) == 0.35
    assert connector._confidence({"chunks": ["a", "b"]}) == 0.6
    assert connector._confidence({"chunks": ["a", "b", "c", "d"]}) == 0.85


def test_nse_document_fetcher_parse_pdf_urls():
    """NSEDocumentFetcher._parse_pdf_urls returns URLs sorted by year desc."""
    from connectors.nse_document_fetcher import NSEDocumentFetcher

    fetcher = NSEDocumentFetcher()
    sample = [
        {"fileName": "/corporates/annualreports/RELIANCE-2023-24.pdf", "year": "2023-24"},
        {"fileName": "/corporates/annualreports/RELIANCE-2024-25.pdf", "year": "2024-25"},
        {"fileName": "/corporates/annualreports/RELIANCE-2022-23.pdf", "year": "2022-23"},
    ]
    urls = fetcher._parse_pdf_urls(sample)
    assert len(urls) == 3
    assert urls[0]["year"] == "2024-25"
    assert "nseindia.com" in urls[0]["pdf_url"]
    assert urls[0]["pdf_url"].endswith("RELIANCE-2024-25.pdf")
