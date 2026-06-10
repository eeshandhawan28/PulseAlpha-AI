from __future__ import annotations

from schemas.report import EvidenceBlock

_SYSTEM_PROMPT = """\
You are a senior equity research analyst at an institutional fund covering Indian markets.
Write a comprehensive, professional investment analysis report in clean, well-structured markdown.

FORMATTING RULES (follow strictly):
- Use Title Case for all section headings (e.g. "## Executive Summary", NOT "## EXECUTIVE SUMMARY")
- Write in clear, flowing prose paragraphs — no walls of capital letters
- Use **bold** for key terms and numbers on first mention
- Use bullet points sparingly, only for lists of 3+ discrete items
- Do NOT include citation tags like [SRC:...] anywhere in the report
- Do NOT use ALL CAPS in the report body text
- Write at the level of a Goldman Sachs or Motilal Oswal equity research note
- Each section should be substantive (3-5 sentences minimum)
"""

_REPORT_TEMPLATE = """\
## Analysis Query
{query}

---

## Available Evidence

{evidence_section}

---

## Report Requirements

Write a professional equity research report with the 7 sections below.
Use the evidence provided. Be specific with numbers. Write in analytical prose.
Do NOT include [SRC:...] citation tags. Do NOT use ALL CAPS. Use standard Title Case headings.

### Section 1 — Executive Summary
A 3-4 sentence summary of the overall investment stance, key conviction drivers, and confidence level.
State the recommendation clearly (Bullish / Bearish / Neutral Hold).

### Section 2 — Market Context
Analyse the macro backdrop: FII/DII institutional flows, their directional implication, and how
the current flow environment affects the thesis. Reference specific flow numbers from the evidence.

### Section 3 — Per-Ticker Analysis
For each ticker, cover five sub-topics:
- **RRG Momentum**: Which quadrant and what it implies for near-term price behaviour
- **Price Momentum**: 30-day trend, key support/resistance levels relative to the 30d range
- **Fundamental Health**: PE, ROE, debt levels, growth rates — and whether they are attractive at current price
- **Recent News & Sentiment**: What recent headlines suggest about near-term catalysts or risks
- **Management Commentary & Annual Report Insights**: Draw directly from the {{TICKER}}_ANNUAL_REPORT_RAG evidence block. Quote specific figures from the retrieved passages (revenue, EBITDA, segment performance, guidance language). If the block shows "No annual report text available", explicitly state this data gap and note that qualitative assessment is limited to ratios and headlines. Do NOT fabricate management commentary.

### Section 4 — Council Debate Summary
Summarise how the 5 analyst personas reached their conclusions. Note the majority stance,
the dissenting view (if any), and what specific evidence drove the divergence.

### Section 5 — Contradictions & Risk Flags
List the key risks: data gaps, contradictory signals, macro risks to the thesis.
Flag any missing data that limits conviction.

### Section 6 — Recommended Actions
Give a clear recommendation per ticker: Buy / Sell / Hold with a suggested time horizon
(short-term 1-3 months, medium-term 6-12 months). Include a brief stop-loss or risk management note.

### Section 7 — Confidence & Data Quality
Use the PIPELINE_METRICS block to state the exact overall confidence score (e.g. "67% — medium").
List each LOW and MEDIUM confidence source by name and explain specifically how the gap limits conviction.
State the divergence score and what it means for the reliability of the recommendation.
Do NOT use a generic confidence number — use the exact percentage from PIPELINE_METRICS.
"""


SECTION_HEADERS = [
    "Section 1 — Executive Summary",
    "Section 2 — Market Context",
    "Section 3 — Per-Ticker Analysis",
    "Section 4 — Council Debate Summary",
    "Section 5 — Contradictions & Risk Flags",
    "Section 6 — Recommended Actions",
    "Section 7 — Confidence & Data Quality",
]


def build_report_prompt(blocks: dict[str, EvidenceBlock], user_query: str) -> str:
    evidence_lines: list[str] = []
    for name, block in blocks.items():
        confidence_label = "HIGH" if block.confidence >= 0.7 else "MEDIUM" if block.confidence >= 0.4 else "LOW"
        evidence_lines.append(f"### {name}  [confidence: {confidence_label} ({block.confidence:.0%}), source: {block.source}]")
        evidence_lines.append(block.content)
        evidence_lines.append("")

    evidence_section = "\n".join(evidence_lines)
    return _REPORT_TEMPLATE.format(
        query=user_query,
        evidence_section=evidence_section,
    )


def get_system_prompt() -> str:
    return _SYSTEM_PROMPT
