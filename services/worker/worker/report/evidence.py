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
            name_ = _fmt(fund.get("name"))
            sector_ = _fmt(fund.get("sector"))
            industry_ = _fmt(fund.get("industry"))
            price_ = _fmt(fund.get("current_price"))
            mcap_ = _fmt(fund.get("market_cap"), "cr")
            lo_ = _fmt(fund.get("week_52_low"))
            hi_ = _fmt(fund.get("week_52_high"))
            pe_ = _fmt(fund.get("pe_ratio"))
            pb_ = _fmt(fund.get("pb_ratio"))
            dy_ = _fmt(fund.get("dividend_yield"), "pct")
            roe_ = _fmt(fund.get("roe"), "pct")
            de_ = _fmt(fund.get("debt_to_equity"))
            rev_ = _fmt(fund.get("revenue_growth"), "pct")
            earn_ = _fmt(fund.get("earnings_growth"), "pct")
            lines = [
                f"Company: {name_} | Sector: {sector_} | Industry: {industry_}",
                f"Current Price: {price_} | Market Cap: {mcap_}",
                f"52-Week Range: {lo_} – {hi_}",
                f"P/E Ratio: {pe_} | P/B Ratio: {pb_} | Dividend Yield: {dy_}",
                f"ROE: {roe_} | Debt/Equity: {de_}",
                f"Revenue Growth (YoY): {rev_} | Earnings Growth (YoY): {earn_}",
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
                f"Last close: ₹{last_close:.1f} | "
                f"30d High: ₹{high_30d:.1f} | 30d Low: ₹{low_30d:.1f}\n"
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

        # ── News Articles block (scraped summaries + YF fallback) ──────
        sent_data = state.sentiment.get(ticker) or {}
        articles = sent_data.get("articles", [])
        rss_headlines = sent_data.get("headlines", [])
        yf_news = (state.alt_data or {}).get(f"{ticker}_news") or []

        news_lines: list[str] = []
        for art in articles[:4]:
            title = art.get("title", "")
            summary = art.get("summary", "")
            source = art.get("source", "")
            published = art.get("published", "")
            if title:
                header = f"**{source}** ({published}): {title}" if source else title
                news_lines.append(header)
                if summary:
                    news_lines.append(summary[:300])
                news_lines.append("")
        # Fallback: RSS headlines
        if not news_lines and rss_headlines:
            for h in rss_headlines[:3]:
                news_lines.append(f"• {h.get('title', '')}")
        # Fallback: Yahoo Finance news
        if not news_lines:
            for item in yf_news[:_MAX_HEADLINES]:
                title = item.get("title", "")
                publisher = item.get("publisher", "")
                if title:
                    news_lines.append(f"• [{publisher}] {title}" if publisher else f"• {title}")

        if news_lines:
            news_content = "\n".join(news_lines).strip()
            news_confidence = 0.7 if articles else 0.4
        else:
            news_content = "No recent news available"
            news_confidence = 0.0
        blocks[f"{ticker}_NEWS"] = EvidenceBlock(
            name=f"{ticker}_NEWS",
            content=news_content,
            confidence=news_confidence,
            source="Google News / article scraper",
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

        # ── Annual Report RAG block ────────────────────────────────────
        rag_data = (state.alt_data or {}).get(f"{ticker}_rag_chunks") or {}
        rag_chunks: list[str] = rag_data.get("chunks", [])
        rag_year: str = rag_data.get("year", "")

        if rag_chunks:
            rag_lines: list[str] = []
            cache_note = " (cached)" if rag_data.get("cache_hit") else ""
            header = (
                f"Annual Report {rag_year}{cache_note} — Retrieved Passages:"
                if rag_year
                else "Annual Report — Retrieved Passages:"
            )
            rag_lines.append(header)
            rag_lines.append("")
            for idx, chunk in enumerate(rag_chunks[:5], start=1):
                # Chunks are prefixed "[Section: <name>]\n<text>" — render the
                # section label separately so the LLM knows the provenance.
                if chunk.startswith("[Section:"):
                    section_end = chunk.find("]\n")
                    if section_end != -1:
                        section_label = chunk[: section_end + 1]   # e.g. "[Section: MD&A]"
                        passage_text = chunk[section_end + 2 :]    # rest of text
                    else:
                        section_label = ""
                        passage_text = chunk
                else:
                    section_label = ""
                    passage_text = chunk

                trimmed = passage_text[:700].strip()
                if trimmed:
                    label_line = f"[Passage {idx}{' — ' + section_label if section_label else ''}]"
                    rag_lines.append(label_line)
                    rag_lines.append(trimmed)
                    rag_lines.append("")
            rag_content = "\n".join(rag_lines).strip()
            rag_confidence = 0.85
        else:
            rag_content = "No annual report text available"
            rag_confidence = 0.0

        blocks[f"{ticker}_ANNUAL_REPORT_RAG"] = EvidenceBlock(
            name=f"{ticker}_ANNUAL_REPORT_RAG",
            content=rag_content,
            confidence=rag_confidence,
            source="NSE annual report (RAG)",
        )

        # ── NSE Announcements block ────────────────────────────────────
        ann_data = (state.alt_data or {}).get(f"{ticker}_announcements") or {}
        announcements = ann_data.get("announcements", [])
        if announcements:
            ann_lines = [
                f"- {a['date']} [{a['category']}]: {a['subject']}"
                for a in announcements[:5]
            ]
            ann_content = "Latest NSE corporate announcements:\n" + "\n".join(ann_lines)
            ann_confidence = min(0.9, 0.2 * len(announcements))
        else:
            ann_content = "No recent NSE announcements available"
            ann_confidence = 0.0
        blocks[f"{ticker}_ANNOUNCEMENTS"] = EvidenceBlock(
            name=f"{ticker}_ANNOUNCEMENTS",
            content=ann_content,
            confidence=ann_confidence,
            source="NSE announcements API",
        )

        # ── Screener.in block ──────────────────────────────────────────
        scr_data = (state.alt_data or {}).get(f"{ticker}_screener") or {}
        pros = scr_data.get("pros", [])
        cons = scr_data.get("cons", [])
        ratios = scr_data.get("ratios", {})
        cagr = scr_data.get("cagr", {})

        if pros or cons or ratios:
            scr_lines: list[str] = []
            if pros:
                scr_lines.append("Analyst view — Pros (screener.in):")
                scr_lines.extend(f"• {p}" for p in pros)
            if cons:
                scr_lines.append("\nAnalyst view — Cons:")
                scr_lines.extend(f"• {c}" for c in cons)
            if ratios:
                ratio_str = " | ".join(
                    f"{k.replace('_', ' ').title()}: {v}"
                    for k, v in list(ratios.items())[:6]
                )
                scr_lines.append(f"\nKey metrics: {ratio_str}")
            if cagr:
                cagr_str = " | ".join(f"{k.replace('_', ' ')}: {v}" for k, v in cagr.items())
                scr_lines.append(f"CAGR: {cagr_str}")
            scr_content = "\n".join(scr_lines)
            scr_confidence = 0.85 if (pros or cons) and ratios else 0.4
        else:
            scr_content = "No screener.in data available"
            scr_confidence = 0.0
        blocks[f"{ticker}_SCREENER"] = EvidenceBlock(
            name=f"{ticker}_SCREENER",
            content=scr_content,
            confidence=scr_confidence,
            source="screener.in",
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

    # ── Pipeline metrics block (overall confidence + divergence) ─────
    conf_pct = round(state.confidence * 100)
    conf_label = (
        "high" if state.confidence >= 0.7
        else "medium" if state.confidence >= 0.4
        else "low"
    )
    div_score = getattr(state, "divergence_score", 0.0)
    div_label = (
        "strong consensus" if div_score < 0.2
        else "moderate disagreement" if div_score < 0.5
        else "high disagreement"
    )

    # Per-block confidence summary
    block_summary_lines: list[str] = []
    for name, block in blocks.items():
        lvl = "HIGH" if block.confidence >= 0.7 else "MEDIUM" if block.confidence >= 0.4 else "LOW"
        block_summary_lines.append(f"  {name}: {lvl} ({block.confidence:.0%})")

    pipeline_content = (
        f"OVERALL PIPELINE CONFIDENCE: {conf_pct}% ({conf_label})\n"
        f"DIVERGENCE SCORE: {div_score:.3f} ({div_label})\n\n"
        f"Per-source confidence breakdown:\n" + "\n".join(block_summary_lines)
    )
    blocks["PIPELINE_METRICS"] = EvidenceBlock(
        name="PIPELINE_METRICS",
        content=pipeline_content,
        confidence=state.confidence,
        source="pipeline computation",
    )

    # ── Council stances block ─────────────────────────────────────────
    if state.council_outputs:
        stance_lines = [
            f"- **{o.persona}**: {o.stance.upper()} "
            f"(confidence={o.confidence:.0%})\n  {o.rationale}"
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
    content_parts = [
        f"Divergence score: {state.divergence_score:.3f} "
        "(0=consensus, 1=maximum disagreement)"
    ]
    if contradictions:
        lines = "\n".join(f"  - {c}" for c in contradictions[:5])
        content_parts.append(f"Detected contradictions:\n{lines}")
    else:
        content_parts.append("No analyst contradictions detected — strong consensus")
    blocks["DIVERGENCE_SUMMARY"] = EvidenceBlock(
        name="DIVERGENCE_SUMMARY",
        content="\n".join(content_parts),
        confidence=round(1.0 - state.divergence_score, 4),
        source="divergence computation",
    )

    return blocks
