from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncGenerator
from contextlib import nullcontext
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from schemas.state import AnalysisState

import api.history_store as history_store
import api.trace_store as trace_store

logger = logging.getLogger(__name__)
router = APIRouter()


def _tracer() -> Any:
    """Return the OTEL tracer if opentelemetry is installed, else None."""
    try:
        from opentelemetry import trace  # noqa: PLC0415

        return trace.get_tracer("pulsealpha.api")
    except ImportError:
        return None


def _span(name: str) -> Any:
    """Return a span context manager; falls back to nullcontext when OTEL is absent."""
    t = _tracer()
    if t is None:
        return nullcontext()
    from opentelemetry.trace import SpanKind  # noqa: PLC0415

    return t.start_as_current_span(name, kind=SpanKind.INTERNAL)


def _set_span_attrs(span: Any, **attrs: Any) -> None:
    """Set attributes on a span if it is a real OTEL span (not nullcontext result)."""
    if span is None:
        return
    try:
        for k, v in attrs.items():
            span.set_attribute(k, str(v))
    except Exception:
        pass


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


def _split_chunks(text: str) -> list[str]:
    """Split text into one chunk per line, preserving markdown structure (newlines intact)."""
    return [line + "\n" for line in text.split("\n")]


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def _run_stream(ticker: str, query: str) -> AsyncGenerator[str, None]:
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

    try:
        with _span("pulsealpha.analyze") as root_span:
            _set_span_attrs(root_span, ticker=ticker, query=query, run_id=state.run_id)

            # ingest
            yield _sse({"type": "step", "node": "ingest", "status": "active"})
            with _span("node.ingest") as s:
                _set_span_attrs(s, **{"input.value": ticker, "openinference.span.kind": "CHAIN"})
                state = await ingest_all_data(state)
                _set_span_attrs(s, **{"output.value": f"tickers={state.ticker_universe}, market_data_keys={list(state.market_data.keys())}"})
            yield _sse({"type": "step", "node": "ingest", "status": "done"})

            # features
            yield _sse({"type": "step", "node": "features", "status": "active"})
            with _span("node.features") as s:
                _set_span_attrs(s, **{"openinference.span.kind": "CHAIN"})
                state = await compute_features(state)
                _set_span_attrs(s, **{"output.value": f"divergence={state.divergence_score:.4f}, charts={len(state.charts)}"})
            yield _sse({"type": "step", "node": "features", "status": "done"})

            # divergence + validate
            yield _sse({"type": "step", "node": "divergence", "status": "active"})
            with _span("node.divergence") as s:
                _set_span_attrs(s, **{"openinference.span.kind": "CHAIN"})
                state = await compute_divergence_node(state)
                state = await normalize_and_validate(state)
                _set_span_attrs(s, **{"output.value": f"divergence_score={state.divergence_score:.4f}, contradictions={len(state.contradictions)}"})
            yield _sse({"type": "step", "node": "divergence", "status": "done"})

            # council
            yield _sse({"type": "step", "node": "council", "status": "active"})
            with _span("node.council") as s:
                _set_span_attrs(s, **{"openinference.span.kind": "CHAIN", "input.value": f"divergence={state.divergence_score:.4f}"})
                state = await run_council(state)
                stances = [o.stance for o in (state.council_outputs or [])]
                _set_span_attrs(s, **{"output.value": f"stances={stances}, confidence={state.confidence:.4f}"})
            yield _sse({"type": "step", "node": "council", "status": "done"})

            # emit metrics after council
            stance = _majority_stance(state)
            quadrant = _rrg_quadrant(state, ticker)
            _set_span_attrs(
                root_span,
                stance=stance,
                confidence=round(state.confidence, 4),
                divergence_score=round(state.divergence_score, 4),
                rrg_quadrant=quadrant,
            )
            yield _sse(
                {
                    "type": "metrics",
                    "stance": stance,
                    "confidence": round(state.confidence, 4),
                    "divergence_score": round(state.divergence_score, 4),
                    "rrg_quadrant": quadrant,
                }
            )

            # emit price charts (generated in features node)
            if state.charts:
                yield _sse({"type": "charts", "charts": state.charts})

            # report
            yield _sse({"type": "step", "node": "report", "status": "active"})
            with _span("node.report") as s:
                _set_span_attrs(s, **{"openinference.span.kind": "CHAIN"})
                state = await generate_report(state)
                _set_span_attrs(s, **{"output.value": (state.report or "")[:500]})
            yield _sse({"type": "step", "node": "report", "status": "done"})

        # emit RAG evidence (annual report chunks retrieved for this ticker)
        rag_data = state.alt_data.get(f"{ticker}_rag_chunks", {})
        if rag_data.get("chunks"):
            yield _sse(
                {
                    "type": "rag_evidence",
                    "chunks": rag_data["chunks"],
                    "year": rag_data.get("year", ""),
                    "pdf_url": rag_data.get("pdf_url", ""),
                }
            )

        # save full pipeline trace for local debugging (6h TTL)
        try:
            trace_store.save_trace(state.run_id, state.model_dump(mode="json"))
        except Exception:
            logger.warning("Failed to save trace for run %s", state.run_id, exc_info=True)

        # stream report chunks
        report_text = state.report or ""
        # Strip inline citation tags the LLM generates — they clutter the display
        report_text = re.sub(r"\s*\[SRC:[^\]]+\]", "", report_text).strip()
        for chunk in _split_chunks(report_text):
            yield _sse({"type": "chunk", "text": chunk})

        # emit done BEFORE writing to disk so client always gets confirmation
        yield _sse({"type": "done", "run_id": state.run_id})

        # save to history (after done — failure here must not block the client)
        try:
            history_store.append_run(
                {
                    "run_id": state.run_id,
                    "ticker": ticker,
                    "query": query,
                    "stance": stance,
                    "confidence": round(state.confidence, 4),
                    "divergence_score": round(state.divergence_score, 4),
                    "rrg_quadrant": quadrant,
                    "report": report_text,
                    "created_at": datetime.now(UTC).isoformat(),
                }
            )
        except Exception:
            logger.warning("Failed to save run %s to history", state.run_id, exc_info=True)

    except Exception as exc:
        logger.exception("Stream pipeline failed for ticker=%s", ticker)
        yield _sse({"type": "error", "message": "Pipeline failed", "detail": str(exc)})


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
    history_store.append_run(
        {
            "run_id": final_state.run_id,
            "ticker": ticker,
            "query": request.user_query,
            "stance": stance,
            "confidence": round(final_state.confidence, 4),
            "divergence_score": round(final_state.divergence_score, 4),
            "rrg_quadrant": _rrg_quadrant(final_state, ticker),
            "report": final_state.report,
            "created_at": datetime.now(UTC).isoformat(),
        }
    )

    return final_state.model_dump(mode="json")  # type: ignore[no-any-return]
