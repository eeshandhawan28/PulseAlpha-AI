from __future__ import annotations

from schemas.report import EvidenceBlock
from schemas.state import AnalysisState

_MAX_HEADLINES = 3


def build_evidence_blocks(state: AnalysisState) -> dict[str, EvidenceBlock]:
    """Build named evidence blocks from AnalysisState for report generation.

    Block naming: {TICKER}_{DOMAIN} for per-ticker, flat names for cross-ticker.
    Missing data → content="No data available", confidence=0.0. Never raises.
    """
    blocks: dict[str, EvidenceBlock] = {}

    for ticker in state.ticker_universe:
        ticker_data = state.market_data.get(ticker) or {}
        confidences = ticker_data.get("_connector_confidence") or {}

        # Fundamentals block
        fund = ticker_data.get("fundamentals") or {}
        if fund:
            content = (
                f"PE={fund.get('pe_ratio')}, ROE={fund.get('roe')}, "
                f"MarketCap={fund.get('market_cap')}, D/E={fund.get('debt_to_equity')}"
            )
            confidence = float(confidences.get("fundamentals", 0.5))
        else:
            content = "No data available"
            confidence = 0.0
        blocks[f"{ticker}_FUNDAMENTALS"] = EvidenceBlock(
            name=f"{ticker}_FUNDAMENTALS",
            content=content,
            confidence=confidence,
            source="fundamentals connector",
        )

        # OHLCV block
        ohlcv = ticker_data.get("ohlcv") or []
        if ohlcv:
            last_close = ohlcv[-1].get("close", "N/A") if ohlcv else "N/A"
            trend = "uptrend" if len(ohlcv) >= 2 and ohlcv[-1].get("close", 0) > ohlcv[0].get("close", 0) else "downtrend"
            content = f"Last close: {last_close}, 30d trend: {trend}, {len(ohlcv)} data points"
            confidence = float(confidences.get("ohlcv", 0.5))
        else:
            content = "No data available"
            confidence = 0.0
        blocks[f"{ticker}_OHLCV"] = EvidenceBlock(
            name=f"{ticker}_OHLCV",
            content=content,
            confidence=confidence,
            source="market data connector",
        )

        # Sentiment block
        sent_data = state.sentiment.get(ticker) or {}
        headlines = sent_data.get("headlines") or []
        if headlines:
            top = headlines[:_MAX_HEADLINES]
            content = "; ".join(h.get("title", "") for h in top if h.get("title"))
            confidence = float(sent_data.get("_connector_confidence", 0.5))
        else:
            content = "No data available"
            confidence = 0.0
        blocks[f"{ticker}_SENTIMENT"] = EvidenceBlock(
            name=f"{ticker}_SENTIMENT",
            content=content,
            confidence=confidence,
            source="sentiment connector",
        )

        # RRG block
        rrg_content = "No data available"
        rrg_confidence = 0.0
        for pt in (state.rotation or {}).get("points", []):
            if pt.get("ticker") == ticker:
                rs = float(pt.get("rs_ratio", 0.0))
                rm = float(pt.get("rs_momentum", 0.0))
                quadrant = "Leading" if rs > 100 and rm > 100 else "Lagging/Other"
                rrg_content = f"Quadrant: {quadrant}, rs_ratio={rs:.2f}, rs_momentum={rm:.2f}"
                rrg_confidence = float(state.confidence)
                break
        blocks[f"{ticker}_RRG"] = EvidenceBlock(
            name=f"{ticker}_RRG",
            content=rrg_content,
            confidence=rrg_confidence,
            source="RRG feature engine",
        )

    # FII/DII flows block
    fii_dii = state.alt_data.get("fii_dii") or {}
    if fii_dii:
        content = f"FII net: {fii_dii.get('fii_net')}, DII net: {fii_dii.get('dii_net')}"
        confidence = float(state.alt_data.get("_fii_confidence", 0.5))
    else:
        content = "No data available"
        confidence = 0.0
    blocks["FII_DII_FLOWS"] = EvidenceBlock(
        name="FII_DII_FLOWS",
        content=content,
        confidence=confidence,
        source="FII/DII connector",
    )

    # Council stances block
    if state.council_outputs:
        stance_lines = [
            f"{o.persona}: {o.stance} (confidence={o.confidence:.2f}) — {o.rationale}"
            for o in state.council_outputs
        ]
        content = "\n".join(stance_lines)
        confidence = sum(o.confidence for o in state.council_outputs) / len(state.council_outputs)
    else:
        content = "No council outputs available"
        confidence = 0.0
    blocks["COUNCIL_STANCES"] = EvidenceBlock(
        name="COUNCIL_STANCES",
        content=content,
        confidence=round(confidence, 4),
        source="council reasoning layer",
    )

    # Divergence summary block
    contradictions = state.contradictions or []
    content_parts = [f"Divergence score: {state.divergence_score:.2f}"]
    if contradictions:
        content_parts.append(f"Contradictions: {'; '.join(contradictions[:5])}")
    else:
        content_parts.append("No contradictions detected")
    blocks["DIVERGENCE_SUMMARY"] = EvidenceBlock(
        name="DIVERGENCE_SUMMARY",
        content="\n".join(content_parts),
        confidence=round(1.0 - state.divergence_score, 4),
        source="divergence computation",
    )

    return blocks
