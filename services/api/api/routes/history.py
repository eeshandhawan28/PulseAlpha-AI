from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

import api.history_store as history_store

logger = logging.getLogger(__name__)
router = APIRouter()

_BACKTEST_DIR = Path(__file__).parents[4] / "backtest_results"


@router.get("/history")
async def list_history() -> list[dict[str, Any]]:
    return history_store.list_runs()


# NOTE: /history/stats MUST be defined before /history/{run_id} to prevent
# FastAPI matching "stats" as a run_id path parameter.
@router.get("/history/stats")
async def history_stats() -> dict[str, Any]:
    """Return hit_rate_30d from the most recent backtest result file, or null."""
    if not _BACKTEST_DIR.exists():
        return {"hit_rate_30d": None}
    files = sorted(_BACKTEST_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        return {"hit_rate_30d": None}
    try:
        data = json.loads(files[0].read_text())
        hit_rate = data.get("metrics", {}).get("hit_rate_30d")
        return {"hit_rate_30d": hit_rate}
    except (json.JSONDecodeError, OSError):
        return {"hit_rate_30d": None}


@router.get("/history/{run_id}")
async def get_history_run(run_id: str) -> dict[str, Any]:
    run = history_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
