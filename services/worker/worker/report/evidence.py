from __future__ import annotations

from schemas.report import EvidenceBlock
from schemas.state import AnalysisState

_MAX_HEADLINES = 5


def _fmt(v: object, fmt: str = "") -> str:
    if v is None:
        return "N/A"
    if fmt == "pct" and isinstance(v, (int, float)):
        return f"{v * 100:.1f}%"
    if fmt == "cr" and isinstance(v, (int, float)):
        return f"₹{v / 1e7:.0f} Cr"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def build_evidence_blocks(state: AnalysisState) -> dict[str, EvidenceBlock]:
    blocks: dict[str, EvidenceBlock] = {}

    for ticker in state.ticker_universe:
        ticker_data = state.market_data.get(ticker) or {}
        confidences = ticker_data.get("_connector_confidence") or {}

        # ── Fundamentals block (enriched) ──────────────────────────────
        fund = ticker_data.get("fundamentals") or {}
        if fund:
            lines = [
                f"Company: {_fmt(fund.get('name'))} | Sector: {_fmt(fund.get('sector'))} | Industry: {_fmt(fund.get('industry'))}",
                f"Current Price: {_fmt(fund.get('current_price'))} | Market Cap: {_fmt(fund.get('market_cap'), 'cr')}",
                f"52-Week Range: {_fmt(fund.get('week_52_low'))} – {_fmt(fund.get('week_52_high'))}",
                f"P/E Ratio: {_fmt(fund.get('pe_ratio'))} | P/B Ratio: {_fmt(fund.get('pb_ratio'))} | Dividend Yield: {_fmt(fund.get('dividend_yield'), 'pct')}",
                f"ROE: {_fmt(fund.get('roe'), 'pct')} | Debt/Equity: {_fmt(fund.get('debt_to_equity'))}",
                f"Revenue Growth (YoY): {_fmt(fund.get('revenue_growth'), 'pct')} | Earnings Growth (YoY): {_fmt(fund.get('earnings_growth'), 'pct')}",
            ]
            content = "\n".join(lines)
            confidence = float(confidences.get("fundamentals", 0.5))
        else:
            content = "No fundamental data available"
            confidence = 0.0
        blocks[f"{ticker}_FUNDAMENTALS"] = EvidenceBlock(
            name=f"{ticker}_FUNDAMENTALS",
            content=content,
            confidence=confidence,
            source="yfinance fundamentals",
        )

        # ── OHLCV / Price momentum block ───────────────────────────────
        ohlcv = ticker_data.get("ohlcv") or []
        if ohlcv and len(ohlcv) >= 2:
            first_close = ohlcv[0].get("close", 0) or 0
            last_close = ohlcv[-1].get("close", 0) or 0
            high_30d = max((r.get("high", 0) or 0 for r in ohlcv), default=0)
            low_30d = min((r.get("low", float("inf")) or float("inf") for r in ohlcv), default=0)
            avg_vol = sum(r.get("volume", 0) or 0 for r in ohlcv) / len(ohlcv)
            pct_chg = ((last_close - first_close) / first_close * 100) if first_close else 0
            trend = "uptrend" if pct_chg > 0 else "downtrend"
            content = (
                f"30-day performance: {pct_chg:+.1f}% ({trend})\n"
                f"Last close: ₹{last_close:.1f} | 30d High: ₹{high_30d:.1f} | 30d Low: ₹{low_30d:.1f}\n"
                f"Average daily volume: {avg_vol:,.0f} shares | Data points: {len(ohlcv)}"
            )
            confidence = float(confidences.get("ohlcv", 0.5))
        elif ohlcv:
            last_close = ohlcv[-1].get("close", "N/A")
            content = f"Last close: {last_close}"
            confidence = 0.3
        else:
            content = "No price data available"
            confidence = 0.0
        blocks[f"{ticker}_OHLCV"] = EvidenceBlock(
            name=f"{ticker}_OHLCV",
            content=content,
            confidence=confidence,
            source="yfinance market data",
        )

        # ── News headlines block ────────────────────────────────────────
        # Try Yahoo Finance news first (from alt_data), then RSS sentiment
        yf_news = (state.alt_data or {}).get(f"{ticker}_news") or []
        sent_data = state.sentiment.get(ticker) or {}
        rss_headlines = sent_data.get("headlines") or []

        all_headlines = []
        for item in yf_news[:_MAX_HEADLINES]:
            title = item.get("title", "")
            publisher = item.get("publisher", "")
            if title:
                all_headlines.append(f"• [{publisher}] {title}" if publisher else f"• {title}")
        for item in rss_headlines[:max(0, _MAX_HEADLINES - len(all_headlines))]:
            title = item.get("title", "")
            if title:
                all_headlines.append(f"• {title}")

        if all_headlines:
            content = "\n".join(all_headlines)
            confidence = 0.7
        else:
            content = "No recent news available"
            confidence = 0.0
        blocks[f"{ticker}_NEWS"] = EvidenceBlock(
            name=f"{ticker}_NEWS",
            content=content,
            confidence=confidence,
            source="Yahoo Finance / RSS news",
        )

        # ── RRG momentum block ─────────────────────────────────────────
        rrg_content = "No RRG data available"
        rrg_confidence = 0.0
        for pt in (state.rotation or {}).get("points", []):
            if pt.get("ticker") == ticker:
                rs = float(pt.get("rs_ratio", 0.0))
                rm = float(pt.get("rs_momentum", 0.0))
                if rs > 100 and rm > 100:
                    quadrant = "Leading (strong relative strength, positive momentum)"
                elif rs > 100:
                    quadrant = "Weakening (strong relative strength but losing momentum)"
                elif rm > 100:
                    quadrant = "Improving (below benchmark but gaining momentum)"
                else:
                    quadrant = "Lagging (below benchmark, negative momentum)"
                rrg_content = (
                    f"RRG Quadrant: {quadrant}\n"
                    f"RS Ratio: {rs:.2f} (benchmark=100) | RS Momentum: {rm:.2f} (benchmark=100)"
                )
                rrg_confidence = float(state.confidence)
                break
        blocks[f"{ticker}_RRG"] = EvidenceBlock(
            name=f"{ticker}_RRG",
            content=rrg_content,
            confidence=rrg_confidence,
            source="RRG feature engine",
        )

    # ── FII/DII flows block ────────────────────────────────────────────
    fii_dii = (state.alt_data or {}).get("fii_dii") or {}
    if fii_dii:
        fii_net = fii_dii.get("fii_net", 0) or 0
        dii_net = fii_dii.get("dii_net", 0) or 0
        fii_dir = "net BUYING" if fii_net > 0 else "net SELLING"
        dii_dir = "net BUYING" if dii_net > 0 else "net SELLING"
        content = (
            f"FII/FPI: ₹{fii_net:.0f} Cr ({fii_dir})\n"
            f"DII: ₹{dii_net:.0f} Cr ({dii_dir})\n"
            f"Combined institutional flow: ₹{(fii_net + dii_net):.0f} Cr"
        )
        confidence = 0.8
    else:
        content = "No FII/DII flow data available"
        confidence = 0.0
    blocks["FII_DII_FLOWS"] = EvidenceBlock(
        name="FII_DII_FLOWS",
        content=content,
        confidence=confidence,
        source="NSE FII/DII feed",
    )

    # ── Council stances block ─────────────────────────────────────────
    if state.council_outputs:
        stance_lines = [
            f"- **{o.persona}**: {o.stance.upper()} (confidence={o.confidence:.0%})\n  {o.rationale}"
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

    # ── Divergence summary block ───────────────────────────────────────
    contradictions = state.contradictions or []
    content_parts = [f"Divergence score: {state.divergence_score:.3f} (0=consensus, 1=maximum disagreement)"]
    if contradictions:
        content_parts.append("Detected contradictions:\n" + "\n".join(f"  - {c}" for c in contradictions[:5]))
    else:
        content_parts.append("No analyst contradictions detected — strong consensus")
    blocks["DIVERGENCE_SUMMARY"] = EvidenceBlock(
        name="DIVERGENCE_SUMMARY",
        content="\n".join(content_parts),
        confidence=round(1.0 - state.divergence_score, 4),
        source="divergence computation",
    )

    return blocks
