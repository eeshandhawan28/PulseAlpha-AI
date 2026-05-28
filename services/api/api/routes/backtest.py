from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from schemas.backtest import BacktestConfig, BacktestResult
from worker.backtest.runner import BacktestRunner

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/backtest", response_model=BacktestResult)
async def run_backtest(config: BacktestConfig) -> BacktestResult:
    """Run a backtesting session over historical data.

    Returns predictions, metrics, and the path to the saved JSON results file.
    """
    try:
        result = await BacktestRunner(config).run()
    except Exception as exc:
        logger.exception("Backtest runner failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result
