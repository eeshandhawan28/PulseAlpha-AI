from __future__ import annotations

import asyncio
import logging
from typing import Any

from connectors.document_rag import DocumentRAGConnector
from connectors.fii_dii import FIIDIIConnector
from connectors.fundamentals import FundamentalsConnector
from connectors.ipo_gmp import IPOGMPConnector
from connectors.market_data import MarketDataConnector
from connectors.news_aggregator import NewsAggregatorConnector
from connectors.nse_announcements import NSEAnnouncementsConnector
from connectors.screener import ScreenerConnector
from connectors.sentiment import SentimentConnector
from schemas.connectors import ConnectorError, ConnectorResult
from schemas.state import AnalysisState


async def _fetch_yf_news(ticker: str) -> list[dict[str, Any]]:
    """Fetch recent Yahoo Finance news for a ticker. Returns [] on any error."""
    import asyncio

    try:
        import yfinance as yf

        loop = asyncio.get_event_loop()
        news = await loop.run_in_executor(None, lambda: yf.Ticker(ticker).news)
        if not isinstance(news, list):
            return []
        return [
            {
                "title": item.get("title", ""),
                "publisher": item.get("publisher", ""),
                "link": item.get("link", ""),
                "published": item.get("providerPublishTime", ""),
            }
            for item in news[:8]
            if item.get("title")
        ]
    except Exception:
        return []


logger = logging.getLogger(__name__)


def _data_or_none(result: ConnectorResult) -> dict[str, Any] | None:
    return result.data if result.ok else None


async def _safe_fetch(
    connector: Any, ticker: str, node: str, state: AnalysisState
) -> ConnectorResult:
    """Fetch from connector, catching all exceptions and returning an error result."""
    try:
        return await connector.fetch(ticker)
    except Exception as exc:
        state.append_audit(node, f"connector fetch raised: {exc}", ticker=ticker)
        source = getattr(connector, "source_name", None)
        return ConnectorResult(
            source=source if isinstance(source, str) else "unknown",
            ticker=ticker,
            data={},
            confidence=0.0,
            error=ConnectorError(code="UNEXPECTED_ERROR", message=str(exc)),
        )


async def ingest_all_data(state: AnalysisState) -> AnalysisState:
    """Fetch all data sources concurrently. Failed connectors write None — never raises."""
    node = "ingest_all_data"
    tickers = state.ticker_universe

    fund_conn = FundamentalsConnector()
    md_conn = MarketDataConnector(as_of_date=state.as_of_date)
    fii_conn = FIIDIIConnector(as_of_date=state.as_of_date)
    sent_conn = SentimentConnector(as_of_date=state.as_of_date)
    gmp_conn = IPOGMPConnector()

    # Per-ticker tasks: fundamentals + OHLCV for each ticker
    fund_tasks = [_safe_fetch(fund_conn, t, node, state) for t in tickers]
    md_tasks = [_safe_fetch(md_conn, t, node, state) for t in tickers]
    # Benchmark prices for RRG (Nifty 50)
    bench_task = _safe_fetch(md_conn, "^NSEI", node, state)
    # Market-wide connectors
    fii_task = _safe_fetch(fii_conn, "MARKET", node, state)
    sent_tasks = [_safe_fetch(sent_conn, t, node, state) for t in tickers]
    # GMP — use first ticker's name as company substring
    gmp_ticker = tickers[0].replace(".NS", "").replace(".BO", "")
    gmp_task = _safe_fetch(gmp_conn, gmp_ticker, node, state)

    results = await asyncio.gather(
        *fund_tasks,
        *md_tasks,
        bench_task,
        fii_task,
        *sent_tasks,
        gmp_task,
    )
    news_results = await asyncio.gather(*[_fetch_yf_news(t) for t in tickers])

    n = len(tickers)
    fund_results = results[:n]
    md_results = results[n : 2 * n]
    bench_result = results[2 * n]
    fii_result = results[2 * n + 1]
    sent_results = results[2 * n + 2 : 3 * n + 2]
    gmp_result = results[3 * n + 2]

    # Build market_data: ticker → {fundamentals, ohlcv}
    market_data: dict[str, Any] = {}
    for ticker, fund_r, md_r in zip(tickers, fund_results, md_results):
        if not fund_r.ok:
            state.append_audit(node, f"fundamentals failed for {ticker}: {fund_r.error}")
        if not md_r.ok:
            state.append_audit(node, f"market data failed for {ticker}: {md_r.error}")
        _md_data = _data_or_none(md_r)
        market_data[ticker] = {
            "fundamentals": _data_or_none(fund_r),
            "ohlcv": _md_data.get("ohlcv") if _md_data is not None else None,
        }

    # Benchmark OHLCV
    if not bench_result.ok:
        state.append_audit(node, f"benchmark (^NSEI) fetch failed: {bench_result.error}")
    _bench_data = _data_or_none(bench_result)
    market_data["^NSEI"] = {
        "ohlcv": _bench_data.get("ohlcv") if _bench_data is not None else None,
    }

    # FII/DII
    if not fii_result.ok:
        state.append_audit(node, f"FII/DII fetch failed: {fii_result.error}")

    # Sentiment — keyed by ticker
    sentiment: dict[str, Any] = {}
    for ticker, sent_r in zip(tickers, sent_results):
        if not sent_r.ok:
            state.append_audit(node, f"sentiment failed for {ticker}: {sent_r.error}")
        sentiment[ticker] = _data_or_none(sent_r)

    # GMP — serialize ConnectorResult to dict so it survives
    # LangGraph's model_dump/model_validate round-trip
    if not gmp_result.ok:
        state.append_audit(node, f"GMP fetch failed: {gmp_result.error}")

    state.market_data = market_data
    state.alt_data = {
        "fii_dii": _data_or_none(fii_result),
        "gmp_connector": gmp_result.model_dump() if gmp_result.ok else None,
    }
    # Add per-ticker news to alt_data
    for ticker, news_items in zip(tickers, news_results):
        state.alt_data[f"{ticker}_news"] = news_items
    state.sentiment = sentiment

    # ── Scrape: NSE announcements, news, screener.in ───────────────────
    ann_conn = NSEAnnouncementsConnector(as_of_date=state.as_of_date)
    news_conn = NewsAggregatorConnector(as_of_date=state.as_of_date)
    scr_conn = ScreenerConnector()

    ann_tasks = [_safe_fetch(ann_conn, t, node, state) for t in tickers]
    news_tasks = [_safe_fetch(news_conn, t, node, state) for t in tickers]
    scr_tasks = [_safe_fetch(scr_conn, t, node, state) for t in tickers]

    scrape_results = await asyncio.gather(*ann_tasks, *news_tasks, *scr_tasks)

    ann_results = scrape_results[:n]
    scrape_news_results = scrape_results[n : 2 * n]
    scr_results = scrape_results[2 * n :]

    for ticker, ann_r, news_r, scr_r in zip(tickers, ann_results, scrape_news_results, scr_results):
        if ann_r.error is not None:
            state.append_audit(node, f"NSE announcements failed for {ticker}: {ann_r.error}")
        if news_r.error is not None:
            state.append_audit(node, f"news aggregator failed for {ticker}: {news_r.error}")
        if scr_r.error is not None:
            state.append_audit(node, f"screener.in failed for {ticker}: {scr_r.error}")

        state.alt_data[f"{ticker}_announcements"] = _data_or_none(ann_r) or {}
        state.alt_data[f"{ticker}_screener"] = _data_or_none(scr_r) or {}

        # Merge news articles into existing sentiment dict for this ticker
        existing_sent = state.sentiment.get(ticker) or {}
        existing_sent["articles"] = (news_r.data or {}).get("articles", [])
        state.sentiment[ticker] = existing_sent

    state.append_audit(node, "scrape complete", tickers=tickers)

    # ── RAG: NSE annual report retrieval ──────────────────────────────────
    rag_conn = DocumentRAGConnector(user_query=state.user_query)
    rag_tasks = [_safe_fetch(rag_conn, t, node, state) for t in tickers]
    rag_results = await asyncio.gather(*rag_tasks)

    for ticker, rag_r in zip(tickers, rag_results):
        if rag_r.error is not None:
            state.append_audit(
                node,
                f"RAG unavailable for {ticker}: {rag_r.error.message}",
                ticker=ticker,
            )
        state.alt_data[f"{ticker}_rag_chunks"] = _data_or_none(rag_r) or {}

    state.append_audit(node, "rag phase complete", tickers=tickers)
    state.append_audit(node, "ingest complete", tickers=tickers)
    return state
