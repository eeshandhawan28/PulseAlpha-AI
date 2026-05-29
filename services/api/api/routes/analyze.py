from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from schemas.state import AnalysisState

import api.history_store as history_store

logger = logging.getLogger(__name__)
router = APIRouter()


class AnalyzeRequest(BaseModel):
    ticker_universe: list[str]
    user_query: str = "Analyze the provided tickers"


def _rrg_quadrant(state: AnalysisState, ticker: str) -> str:
    for pt in state.rotation.get("points", []):
        if pt.get("ticker") == ticker:
            rs = float(pt.get("rs_ratio", 0.0))
            rm = float(pt.get("rs_momentum", 0.0))
            if rs > 100 and rm > 100:
                return "Leading"
            elif rs > 100:
                return "Weakening"
            elif rm > 100:
                return "Improving"
            return "Lagging"
    return "—"


def _majority_stance(state: AnalysisState) -> str:
    if not state.council_outputs:
        return "neutral"
    from worker.council.variance import majority_stance
    return majority_stance(state.council_outputs)


def _split_chunks(text: str, max_chars: int = 60) -> list[str]:
    """Split text on word boundaries into chunks of ~max_chars each."""
    words = text.split()
    chunks: list[str] = []
    current = ""
    for word in words:
        candidate = current + " " + word if current else word
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def _run_stream(ticker: str, query: str) -> AsyncIterator[str]:
    from worker.nodes.council import run_council
    from worker.nodes.divergence import compute_divergence_node
    from worker.nodes.features import compute_features
    from worker.nodes.ingest import ingest_all_data
    from worker.nodes.report import generate_report
    from worker.nodes.validate import normalize_and_validate

    try:
        state = AnalysisState(user_query=query, ticker_universe=[ticker])
    except ValueError as exc:
        yield _sse({"type": "error", "message": str(exc)})
        return

    # ingest
    yield _sse({"type": "step", "node": "ingest", "status": "active"})
    state = await ingest_all_data(state)
    yield _sse({"type": "step", "node": "ingest", "status": "done"})

    # features
    yield _sse({"type": "step", "node": "features", "status": "active"})
    state = await compute_features(state)
    yield _sse({"type": "step", "node": "features", "status": "done"})

    # divergence + validate
    yield _sse({"type": "step", "node": "divergence", "status": "active"})
    state = await compute_divergence_node(state)
    state = await normalize_and_validate(state)
    yield _sse({"type": "step", "node": "divergence", "status": "done"})

    # council
    yield _sse({"type": "step", "node": "council", "status": "active"})
    state = await run_council(state)
    yield _sse({"type": "step", "node": "council", "status": "done"})

    # emit metrics after council
    stance = _majority_stance(state)
    quadrant = _rrg_quadrant(state, ticker)
    yield _sse({
        "type": "metrics",
        "stance": stance,
        "confidence": round(state.confidence, 4),
        "divergence_score": round(state.divergence_score, 4),
        "rrg_quadrant": quadrant,
    })

    # report
    yield _sse({"type": "step", "node": "report", "status": "active"})
    state = await generate_report(state)
    yield _sse({"type": "step", "node": "report", "status": "done"})

    # stream report chunks
    report_text = state.report or ""
    for chunk in _split_chunks(report_text, max_chars=60):
        yield _sse({"type": "chunk", "text": chunk + " "})

    # save to history
    history_store.append_run({
        "run_id": state.run_id,
        "ticker": ticker,
        "query": query,
        "stance": stance,
        "confidence": round(state.confidence, 4),
        "divergence_score": round(state.divergence_score, 4),
        "rrg_quadrant": quadrant,
        "report": report_text,
        "created_at": datetime.now(UTC).isoformat(),
    })

    yield _sse({"type": "done", "run_id": state.run_id})


@router.get("/analyze/stream")
async def analyze_stream(ticker: str, query: str = "Analyze this ticker") -> StreamingResponse:
    """SSE endpoint — emits step/metrics/chunk/done events as pipeline runs."""
    return StreamingResponse(
        _run_stream(ticker, query),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/analyze", response_model=dict[str, object])
async def analyze(request: AnalyzeRequest) -> dict[str, object]:
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

    # Save to history
    ticker = request.ticker_universe[0]
    stance = _majority_stance(final_state)
    history_store.append_run({
        "run_id": final_state.run_id,
        "ticker": ticker,
        "query": request.user_query,
        "stance": stance,
        "confidence": round(final_state.confidence, 4),
        "divergence_score": round(final_state.divergence_score, 4),
        "rrg_quadrant": _rrg_quadrant(final_state, ticker),
        "report": final_state.report,
        "created_at": datetime.now(UTC).isoformat(),
    })

    return final_state.model_dump(mode="json")  # type: ignore[no-any-return]
