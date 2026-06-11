from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import api.watchlist_store as watchlist_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class AddRequest(BaseModel):
    ticker: str


@router.get("", response_model=list[dict[str, Any]])
async def get_watchlist() -> list[dict[str, Any]]:
    """Return all watchlist items with their latest cached analysis results."""
    return watchlist_store.list_items()


@router.post("", response_model=dict[str, Any], status_code=201)
async def add_to_watchlist(body: AddRequest) -> dict[str, Any]:
    """Add a ticker to the watchlist."""
    ticker = body.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=422, detail="ticker is required")
    return watchlist_store.add(ticker)


@router.delete("/{ticker}", status_code=204)
async def remove_from_watchlist(ticker: str) -> None:
    """Remove a ticker from the watchlist."""
    removed = watchlist_store.remove(ticker.upper())
    if not removed:
        raise HTTPException(status_code=404, detail=f"{ticker} not in watchlist")


@router.get("/{ticker}/status", response_model=dict[str, Any])
async def ticker_status(ticker: str) -> dict[str, Any]:
    """Check if a ticker is in the watchlist."""
    return {"ticker": ticker.upper(), "in_watchlist": watchlist_store.has(ticker.upper())}


@router.post("/analyze-all", response_model=dict[str, Any])
async def analyze_all() -> dict[str, Any]:
    """Re-run analysis for every ticker in the watchlist (non-streaming, sequential).

    Updates each watchlist item's cached stance/confidence/rrg_quadrant.
    Returns a summary of results.
    """
    from datetime import UTC, datetime  # noqa: PLC0415

    from schemas.state import AnalysisState  # noqa: PLC0415
    from worker.council.variance import majority_stance  # noqa: PLC0415
    from worker.nodes.council import run_council  # noqa: PLC0415
    from worker.nodes.divergence import compute_divergence_node  # noqa: PLC0415
    from worker.nodes.features import compute_features  # noqa: PLC0415
    from worker.nodes.ingest import ingest_all_data  # noqa: PLC0415
    from worker.nodes.report import generate_report  # noqa: PLC0415
    from worker.nodes.validate import normalize_and_validate  # noqa: PLC0415

    import api.history_store as history_store  # noqa: PLC0415

    items = watchlist_store.list_items()
    if not items:
        return {"analyzed": 0, "results": []}

    results = []
    for item in items:
        ticker = item["ticker"]
        try:
            state = AnalysisState(
                user_query="Analyze the investment case and near-term outlook",
                ticker_universe=[ticker],
            )
            state = await ingest_all_data(state)
            state = await compute_features(state)
            state = await compute_divergence_node(state)
            state = await normalize_and_validate(state)
            state = await run_council(state)
            state = await generate_report(state)

            stance = majority_stance(state.council_outputs) if state.council_outputs else "neutral"
            confidence = round(state.confidence, 4)

            # Derive RRG quadrant
            rrg_quadrant = "—"
            for pt in (state.rotation or {}).get("points", []):
                if pt.get("ticker") == ticker:
                    rs = float(pt.get("rs_ratio", 0.0))
                    rm = float(pt.get("rs_momentum", 0.0))
                    if rs > 100 and rm > 100:
                        rrg_quadrant = "Leading"
                    elif rs > 100:
                        rrg_quadrant = "Weakening"
                    elif rm > 100:
                        rrg_quadrant = "Improving"
                    else:
                        rrg_quadrant = "Lagging"
                    break

            watchlist_store.update_from_run(ticker, stance, confidence, rrg_quadrant)

            import re  # noqa: PLC0415

            report_text = re.sub(r"\s*\[SRC:[^\]]+\]", "", state.report or "").strip()
            history_store.append_run(
                {
                    "run_id": state.run_id,
                    "ticker": ticker,
                    "query": "Analyze the investment case and near-term outlook",
                    "stance": stance,
                    "confidence": confidence,
                    "divergence_score": round(state.divergence_score, 4),
                    "rrg_quadrant": rrg_quadrant,
                    "report": report_text,
                    "created_at": datetime.now(UTC).isoformat(),
                }
            )

            results.append(
                {
                    "ticker": ticker,
                    "stance": stance,
                    "confidence": confidence,
                    "rrg_quadrant": rrg_quadrant,
                    "status": "ok",
                }
            )
        except Exception as exc:
            logger.exception("Watchlist analysis failed for %s", ticker)
            results.append({"ticker": ticker, "status": "error", "detail": str(exc)})

    return {"analyzed": len(results), "results": results}
