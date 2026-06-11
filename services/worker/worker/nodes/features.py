from __future__ import annotations

import asyncio
import logging
from typing import Any

import pandas as pd
from features.fii_dii import compute_flow_strength
from features.ipo_gmp import compute_gmp_disagreement
from features.rrg import compute_rrg
from schemas.features import FlowStrengthResult, RRGResult
from schemas.state import AnalysisState

logger = logging.getLogger(__name__)


def _records_to_df(records: list[dict[str, Any]], date_col: str = "date") -> pd.DataFrame:
    """Convert list of OHLCV dicts to a DataFrame indexed by date."""
    df = pd.DataFrame(records)
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).sort_index()
    df.columns = [c.lower() for c in df.columns]
    return df


def _build_flow_history(fii_data: dict[str, Any]) -> pd.DataFrame:
    """Build a FII/DII DataFrame from the persistent 30-day history buffer.

    Falls back to a single-row DataFrame (today only) when the history file
    doesn't exist yet — flow strength will still be skipped by _run_flow_strength
    until at least 20 days are accumulated.
    """
    from datetime import date  # noqa: PLC0415

    try:
        from api.fii_dii_store import load_history  # noqa: PLC0415

        records = load_history()
        if records:
            df = pd.DataFrame(records)
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()
            for col in ("fii_net", "fii_buy", "fii_sell", "dii_net", "dii_buy", "dii_sell"):
                if col not in df.columns:
                    df[col] = 0.0
            return df
    except Exception:
        logger.debug("Could not load FII/DII history, using single-day fallback")

    # Fallback: single-row from today's ingest data
    return pd.DataFrame(
        [
            {
                "date": date.today(),
                "fii_net": fii_data.get("fii_net", 0.0),
                "fii_buy": fii_data.get("fii_buy", 0.0),
                "fii_sell": fii_data.get("fii_sell", 0.0),
                "dii_net": fii_data.get("dii_net", 0.0),
                "dii_buy": fii_data.get("dii_buy", 0.0),
                "dii_sell": fii_data.get("dii_sell", 0.0),
            }
        ]
    ).set_index("date")


async def _run_rrg(state: AnalysisState) -> RRGResult | None:
    """Build price dicts and call compute_rrg. Returns None if prices unavailable."""
    bench_ohlcv = state.market_data.get("^NSEI", {}).get("ohlcv")
    if not bench_ohlcv:
        state.append_audit("compute_features", "skipping RRG — benchmark prices unavailable")
        return None

    prices: dict[str, pd.DataFrame] = {}
    for ticker in state.ticker_universe:
        ohlcv = state.market_data.get(ticker, {}).get("ohlcv")
        if ohlcv:
            prices[ticker] = _records_to_df(ohlcv)
        else:
            state.append_audit("compute_features", f"skipping RRG for {ticker} — no OHLCV")

    if not prices:
        state.append_audit("compute_features", "skipping RRG — no ticker prices available")
        return None

    benchmark_df = _records_to_df(bench_ohlcv)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: compute_rrg(prices, benchmark_df))


async def _run_flow_strength(state: AnalysisState) -> FlowStrengthResult | None:
    """Build flow history DataFrame and call compute_flow_strength."""
    fii_data = state.alt_data.get("fii_dii")
    if not fii_data:
        state.append_audit("compute_features", "skipping flow strength — FII/DII data unavailable")
        return None

    flow_df = _build_flow_history(fii_data)
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, lambda: compute_flow_strength(flow_df))
    except ValueError as exc:
        state.append_audit("compute_features", f"flow strength skipped: {exc}")
        return None


async def compute_features(state: AnalysisState) -> AnalysisState:
    """Compute RRG, flow strength, and GMP features from ingested data."""
    node = "compute_features"

    # RRG and flow run concurrently
    rrg_result, flow_result = await asyncio.gather(
        _run_rrg(state),
        _run_flow_strength(state),
    )

    # GMP disagreement (sequential — depends on gmp connector result)
    gmp_result = None
    gmp_connector_dict = state.alt_data.get("gmp_connector")
    if gmp_connector_dict is not None:
        from schemas.connectors import ConnectorResult

        gmp_cr = ConnectorResult.model_validate(gmp_connector_dict)
        loop = asyncio.get_running_loop()
        gmp_result = await loop.run_in_executor(None, lambda: compute_gmp_disagreement(gmp_cr))

    # Write to state
    state.rotation = rrg_result.model_dump() if rrg_result else {}
    state.alt_data["flow"] = flow_result.model_dump() if flow_result else None
    state.alt_data["gmp"] = gmp_result.model_dump() if gmp_result else None

    # Build Plotly price charts from OHLCV data
    from worker.charts import build_price_charts  # noqa: PLC0415

    loop = asyncio.get_running_loop()
    state.charts = await loop.run_in_executor(None, lambda: build_price_charts(state))

    state.append_audit(
        node,
        "feature computation complete",
        rrg_points=len(rrg_result.points) if rrg_result else 0,
        flow_available=flow_result is not None,
        gmp_available=gmp_result is not None,
        charts=len(state.charts),
    )
    return state
