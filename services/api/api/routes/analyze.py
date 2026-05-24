from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from schemas.state import AnalysisState

logger = logging.getLogger(__name__)

router = APIRouter()


class AnalyzeRequest(BaseModel):
    ticker_universe: list[str]
    user_query: str = "Analyze the provided tickers"


@router.post("/analyze", response_model=dict)
async def analyze(request: AnalyzeRequest) -> dict:
    """Run the full analysis graph for the given ticker universe."""
    from worker.graph import run_analysis

    try:
        state = AnalysisState(
            user_query=request.user_query,
            ticker_universe=request.ticker_universe,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        final_state = await run_analysis(state)
    except Exception as exc:
        logger.exception("Graph run failed for tickers=%s", request.ticker_universe)
        raise HTTPException(status_code=500, detail="Analysis graph failed") from exc

    return final_state.model_dump(mode="json")
