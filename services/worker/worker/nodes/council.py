from __future__ import annotations

import asyncio
import logging

from schemas.models import ModelTier, RoutingConfig
from schemas.state import AnalysisState, CouncilOutput

from worker.council.llm import call_llm, select_tier
from worker.council.parser import neutral_output, parse_with_retry
from worker.council.personas import PERSONA_NAMES, PERSONAS, build_reconciliation_prompt
from worker.council.variance import compute_disagreement, majority_stance

logger = logging.getLogger(__name__)

_NODE = "run_council"
_MAX_ITERATIONS = 3
_MAX_HEADLINES_PER_TICKER = 3

# Council-specific disagreement threshold.
# RoutingConfig.divergence_threshold (0.7) is used for tier escalation.
# With 5 personas and 3 stances, max possible disagreement is 0.6 (2/2/1 split),
# so the council uses a lower practical threshold: 0.35 triggers on any 3/2 split.
_COUNCIL_DISAGREEMENT_THRESHOLD = 0.35


def _build_context(state: AnalysisState) -> str:
    """Serialize Phase 3 state into a token-budgeted context string (~1500 tokens)."""
    lines: list[str] = [
        f"User query: {state.user_query}",
        f"Tickers: {', '.join(state.ticker_universe)}",
        f"Divergence score: {state.divergence_score:.2f}",
    ]
    if state.contradictions:
        lines.append(f"Contradictions: {'; '.join(state.contradictions[:5])}")

    for ticker in state.ticker_universe:
        lines.append(f"\n--- {ticker} ---")

        fund = (state.market_data.get(ticker) or {}).get("fundamentals") or {}
        if fund:
            lines.append(
                f"Fundamentals: PE={fund.get('pe_ratio')}, ROE={fund.get('roe')}, "
                f"MarketCap={fund.get('market_cap')}, D/E={fund.get('debt_to_equity')}"
            )

        rotation = state.rotation or {}
        for pt in rotation.get("points", []):
            if pt.get("ticker") == ticker:
                rs = float(pt.get("rs_ratio", 0.0))
                rm = float(pt.get("rs_momentum", 0.0))
                quadrant = "Leading" if rs > 100 and rm > 100 else "Lagging/Other"
                lines.append(f"RRG: rs_ratio={rs:.2f}, rs_momentum={rm:.2f} ({quadrant})")
                break

        headlines = (state.sentiment.get(ticker) or {}).get("headlines", [])
        for h in headlines[:_MAX_HEADLINES_PER_TICKER]:
            lines.append(f"Headline: {h.get('title', '')}")

    fii_dii = state.alt_data.get("fii_dii") or {}
    if fii_dii:
        lines.append(f"\nFII net: {fii_dii.get('fii_net')}, DII net: {fii_dii.get('dii_net')}")

    return "\n".join(lines)


async def _call_persona(
    persona_name: str,
    context: str,
    tier: ModelTier,
    extra_user_content: str = "",
) -> CouncilOutput:
    system_prompt = PERSONAS[persona_name]
    user_message = context
    if extra_user_content:
        user_message = f"{context}\n\n{extra_user_content}"

    retry_message = (
        "Your previous response was not valid JSON. Return ONLY a JSON object: "
        '{"persona": "...", "stance": "bullish"|"bearish"|"neutral", '
        '"rationale": "...", "confidence": 0.0-1.0, "citations": [...]}'
    )

    async def do_retry() -> str:
        return await call_llm(system_prompt, retry_message, tier)

    try:
        first = await call_llm(system_prompt, user_message, tier)
    except Exception:
        logger.exception("LLM call failed for persona %s, returning neutral", persona_name)
        return neutral_output(persona_name)

    return await parse_with_retry(first, persona_name, do_retry)


async def run_council(state: AnalysisState) -> AnalysisState:
    """Run all 5 council personas, then reconcile disagreement up to 3 times.

    Disagreement threshold: _COUNCIL_DISAGREEMENT_THRESHOLD (0.35).
    All LLM calls run concurrently via asyncio.gather(). Node never raises.
    """
    config = RoutingConfig()
    tier = select_tier(state, config)
    context = _build_context(state)

    state.append_audit(_NODE, "council starting", tier=str(tier), personas=PERSONA_NAMES)

    outputs: list[CouncilOutput] = list(
        await asyncio.gather(*[_call_persona(p, context, tier) for p in PERSONA_NAMES])
    )

    disagreement = compute_disagreement(outputs)
    iteration = 0

    while disagreement >= _COUNCIL_DISAGREEMENT_THRESHOLD and iteration < _MAX_ITERATIONS:
        iteration += 1
        majority = majority_stance(outputs)
        synthesizer_out = next((o for o in outputs if o.persona == "Synthesizer"), None)
        synthesizer_rationale = (
            synthesizer_out.rationale if synthesizer_out else "No synthesis available."
        )

        state.append_audit(
            _NODE,
            "reconciliation round",
            iteration=iteration,
            disagreement=round(disagreement, 3),
            majority=majority,
        )

        # Identify dissenters: non-majority stance, excluding Synthesizer
        dissenter_indices: list[int] = []
        revision_tasks = []
        for i, o in enumerate(outputs):
            # Use the canonical persona name from PERSONA_NAMES (not parsed output)
            canonical_name = PERSONA_NAMES[i]
            if canonical_name != "Synthesizer" and o.stance != majority:
                extra = build_reconciliation_prompt(canonical_name, majority, synthesizer_rationale)
                revision_tasks.append(_call_persona(canonical_name, context, tier, extra))
                dissenter_indices.append(i)

        if revision_tasks:
            revision_results: list[CouncilOutput] = list(await asyncio.gather(*revision_tasks))
            for idx, revised in zip(dissenter_indices, revision_results):
                outputs[idx] = revised

        disagreement = compute_disagreement(outputs)

    if iteration > 0 and disagreement >= _COUNCIL_DISAGREEMENT_THRESHOLD:
        state.append_audit(
            _NODE,
            "unresolved disagreement after max iterations",
            iterations=iteration,
            final_disagreement=round(disagreement, 3),
        )

    state.council_outputs = outputs
    prior_confidence = state.confidence
    state.confidence = round(
        min(max((1.0 - disagreement) * 0.5 + prior_confidence * 0.5, 0.0), 1.0), 4
    )

    state.append_audit(
        _NODE,
        "council complete",
        final_disagreement=round(disagreement, 3),
        confidence=state.confidence,
        iterations=iteration,
    )

    return state
