from __future__ import annotations

import asyncio
import logging
from typing import Any

from connectors.fii_dii import FIIDIIConnector
from connectors.fundamentals import FundamentalsConnector
from connectors.ipo_gmp import IPOGMPConnector
from connectors.market_data import MarketDataConnector
from connectors.sentiment import SentimentConnector
from schemas.connectors import ConnectorError, ConnectorResult
from schemas.state import AnalysisState

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
    md_conn = MarketDataConnector()
    fii_conn = FIIDIIConnector()
    sent_conn = SentimentConnector()
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
    state.sentiment = sentiment
    state.append_audit(node, "ingest complete", tickers=tickers)
    return state
