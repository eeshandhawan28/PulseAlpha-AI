from __future__ import annotations

import logging

from schemas.models import RoutingConfig
from schemas.state import AnalysisState

from worker.council.llm import select_tier
from worker.report.evidence import build_evidence_blocks
from worker.report.flags import apply_confidence_flags
from worker.report.llm import call_report_llm
from worker.report.parser import parse_citations
from worker.report.prompt import build_report_prompt, get_system_prompt

logger = logging.getLogger(__name__)

_NODE = "generate_report"
_MIN_REPORT_LENGTH = 100


def _fallback_report(state: AnalysisState) -> str:
    """Return a minimal fallback report when LLM fails or returns empty response."""
    stances = (
        ", ".join(o.stance for o in state.council_outputs) if state.council_outputs else "none"
    )
    return (
        f"## Report Generation Failed\n"
        f"Confidence: {state.confidence:.2f}\n"
        f"Council stances: {stances}\n"
        f"Run ID: {state.run_id}\n"
    )


async def generate_report(state: AnalysisState) -> AnalysisState:
    """Generate a 7-section markdown report from Phase 1–4 outputs.

    Writes state.report (markdown string) and state.citations (list[Citation]).
    Node never raises — fallback report written on any LLM failure.
    """
    config = RoutingConfig()
    tier = select_tier(state, config)

    state.append_audit(_NODE, "report generation starting", tier=str(tier))

    blocks = build_evidence_blocks(state)
    prompt = build_report_prompt(blocks, state.user_query)
    system_prompt = get_system_prompt()

    try:
        raw_report = await call_report_llm(prompt, system_prompt, tier)
    except Exception:
        logger.exception("LLM call failed for report generation, writing fallback")
        state.report = _fallback_report(state)
        state.append_audit(_NODE, "report generation failed — fallback written")
        return state

    if not raw_report or len(raw_report) < _MIN_REPORT_LENGTH:
        logger.warning(
            "LLM returned short/empty response (%d chars), writing fallback",
            len(raw_report) if raw_report else 0,
        )
        state.report = _fallback_report(state)
        state.append_audit(_NODE, "report generation failed — short response, fallback written")
        return state

    citations = parse_citations(raw_report, blocks)
    citations = apply_confidence_flags(citations, blocks)

    state.report = raw_report
    state.citations = citations

    state.append_audit(
        _NODE,
        "report generation complete",
        citations_count=len(citations),
        report_length=len(raw_report),
    )

    return state
