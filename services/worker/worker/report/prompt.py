from __future__ import annotations

from schemas.report import EvidenceBlock

SECTION_HEADERS: list[str] = [
    "## Executive Summary",
    "## Market Context",
    "## Per-Ticker Analysis",
    "## Council Debate Summary",
    "## Contradictions & Risk Flags",
    "## Recommended Actions",
    "## Confidence & Data Provenance",
]

_CITATION_INSTRUCTION = """
For every factual claim, append a citation tag immediately after the claim:
[SRC:BLOCK_NAME:field_name]
Use only block names from the evidence provided. Do not invent block names.
Respond with the full markdown report only. No preamble, no trailing text.
"""

_SYSTEM_PROMPT = (
    "You are a senior Indian equity analyst. Write a structured investment analysis report "
    "using only the evidence provided. Every factual claim must be immediately followed by "
    "a citation tag in the format [SRC:BLOCK_NAME:field_name]."
)

_REPORT_TEMPLATE = """\
You are writing an investment analysis report for the following query:
{query}

## Available Evidence Blocks

{evidence_section}

## Report Structure

Write the following 7 sections in order. Use markdown headers exactly as shown.

## Executive Summary
2-3 sentences summarising the overall stance and confidence level across all tickers.

## Market Context
Describe the macro flow backdrop using FII/DII data.

## Per-Ticker Analysis
One sub-section per ticker covering: RRG quadrant position, price momentum, and fundamental health.

## Council Debate Summary
Summarise how the 5 analyst personas agreed or disagreed, and what the reconciliation outcome was.

## Contradictions & Risk Flags
List each detected contradiction and associated risk level.

## Recommended Actions
Bullish/bearish/hold recommendation per ticker with concise reasoning.

## Confidence & Data Provenance
Overall confidence score, which data sources had low confidence, and data quality notes.

{citation_instruction}
"""


def build_report_prompt(blocks: dict[str, EvidenceBlock], user_query: str) -> str:
    """Render the full 7-section report prompt with evidence blocks injected."""
    evidence_lines: list[str] = []
    for name, block in blocks.items():
        evidence_lines.append(
            f"### {name} (confidence={block.confidence:.2f}, source={block.source})"
        )
        evidence_lines.append(block.content)
        evidence_lines.append("")

    evidence_section = "\n".join(evidence_lines)

    return _REPORT_TEMPLATE.format(
        query=user_query,
        evidence_section=evidence_section,
        citation_instruction=_CITATION_INSTRUCTION,
    )


def get_system_prompt() -> str:
    """Return the system prompt for the report LLM call."""
    return _SYSTEM_PROMPT
