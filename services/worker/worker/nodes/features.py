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
    """Build a single-row FII/DII DataFrame from today's connector data.

    Note: This produces a single-row DataFrame from today's snapshot.
    compute_flow_strength requires zscore_window (20) rows minimum and will
    raise ValueError, which _run_flow_strength catches — flow_result will be None
    in production until historical FII/DII accumulation is added (future phase).
    """
    from datetime import date
    return pd.DataFrame([{
        "date": date.today(),
        "fii_net": fii_data.get("fii_net", 0.0),
        "fii_buy": fii_data.get("fii_buy", 0.0),
        "fii_sell": fii_data.get("fii_sell", 0.0),
        "dii_net": fii_data.get("dii_net", 0.0),
        "dii_buy": fii_data.get("dii_buy", 0.0),
        "dii_sell": fii_data.get("dii_sell", 0.0),
    }]).set_index("date")


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

    state.append_audit(
        node,
        "feature computation complete",
        rrg_points=len(rrg_result.points) if rrg_result else 0,
        flow_available=flow_result is not None,
        gmp_available=gmp_result is not None,
    )
    return state
