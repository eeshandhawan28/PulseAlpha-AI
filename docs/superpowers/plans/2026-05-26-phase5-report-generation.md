
# Phase 5: Report Generation & Auditability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `generate_report` LangGraph node that synthesizes all Phase 1–4 outputs into a 7-section markdown report with inline `[SRC:block:field]` citation tags, parsed into typed `Citation` objects and confidence-flagged.

**Architecture:** A new `services/worker/worker/report/` sub-package (mirroring Phase 4's `council/`) backs a single `generate_report` node appended after `run_council`. Evidence blocks are built from `AnalysisState`, injected into a prompt, the LLM produces tagged markdown, citations are regex-extracted, and low-confidence sources are flagged. Node never raises — fallback report written on any LLM failure.

**Tech Stack:** Python 3.11, Pydantic v2, re (stdlib), langchain-huggingface, langchain-ollama, pytest-asyncio, unittest.mock.

---

## File Map

```
libs/schemas/schemas/
└── report.py                        NEW — EvidenceBlock schema

services/worker/worker/
├── report/
│   ├── __init__.py                  NEW — empty package marker
│   ├── evidence.py                  NEW — build_evidence_blocks(state) → dict[str, EvidenceBlock]
│   ├── prompt.py                    NEW — build_report_prompt(blocks, query) → str
│   ├── parser.py                    NEW — parse_citations(report_text, blocks) → list[Citation]
│   ├── flags.py                     NEW — apply_confidence_flags(citations, blocks, threshold) → list[Citation]
│   └── llm.py                       NEW — call_report_llm(prompt, tier) → str
└── nodes/
    └── report.py                    NEW — generate_report() LangGraph node

tests/unit/
├── schemas/
│   └── test_report_schema.py        NEW — EvidenceBlock validation
└── worker/
    ├── report/
    │   ├── __init__.py              NEW
    │   ├── test_evidence.py         NEW
    │   ├── test_prompt.py           NEW
    │   ├── test_parser.py           NEW
    │   └── test_flags.py            NEW
    └── test_report_node.py          NEW

tests/integration/
└── test_report_endpoint.py          NEW

Modified:
- libs/schemas/schemas/__init__.py   — export EvidenceBlock
- services/worker/worker/graph.py    — add generate_report node after run_council
```

---

### Task 1: EvidenceBlock Schema

**Files:**
- Create: `libs/schemas/schemas/report.py`
- Modify: `libs/schemas/schemas/__init__.py`
- Create: `tests/unit/schemas/test_report_schema.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/schemas/test_report_schema.py`:
```python
import pytest
from pydantic import ValidationError
from schemas.report import EvidenceBlock


def test_evidence_block_valid():
    block = EvidenceBlock(
        name="RELIANCE_FUNDAMENTALS",
        content="PE=28.0, ROE=0.12",
        confidence=0.9,
        source="YFinance fundamentals",
    )
    assert block.name == "RELIANCE_FUNDAMENTALS"
    assert block.confidence == 0.9


def test_evidence_block_confidence_too_high_raises():
    with pytest.raises(ValidationError):
        EvidenceBlock(name="X", content="y", confidence=1.5, source="z")


def test_evidence_block_confidence_negative_raises():
    with pytest.raises(ValidationError):
        EvidenceBlock(name="X", content="y", confidence=-0.1, source="z")


def test_evidence_block_zero_confidence_valid():
    block = EvidenceBlock(name="X", content="No data available", confidence=0.0, source="missing")
    assert block.confidence == 0.0
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI"
uv run pytest tests/unit/schemas/test_report_schema.py -v
```
Expected: `ModuleNotFoundError: No module named 'schemas.report'`

- [ ] **Step 3: Implement `libs/schemas/schemas/report.py`**

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class EvidenceBlock(BaseModel):
    name: str
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: str
```

- [ ] **Step 4: Export from `libs/schemas/schemas/__init__.py`**

Add `from .report import EvidenceBlock` and `"EvidenceBlock"` to `__all__`:

```python
from .connectors import ConnectorError, ConnectorResult
from .features import (
    DivergenceResult,
    FlowStrengthResult,
    IPOGMPResult,
    RRGPoint,
    RRGResult,
)
from .models import ModelTier, RoutingConfig
from .report import EvidenceBlock
from .state import AnalysisState, AuditEntry, Citation, CouncilOutput

__all__ = [
    "AnalysisState",
    "AuditEntry",
    "CouncilOutput",
    "Citation",
    "ConnectorResult",
    "ConnectorError",
    "EvidenceBlock",
    "ModelTier",
    "RoutingConfig",
    "RRGPoint",
    "RRGResult",
    "FlowStrengthResult",
    "IPOGMPResult",
    "DivergenceResult",
]
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/unit/schemas/test_report_schema.py -v
```
Expected: All 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI"
git add libs/schemas/schemas/report.py libs/schemas/schemas/__init__.py \
        tests/unit/schemas/test_report_schema.py
git commit -m "feat(schemas): add EvidenceBlock schema for Phase 5 report generation"
```

---

### Task 2: evidence.py — Build Evidence Blocks from AnalysisState

**Files:**
- Create: `services/worker/worker/report/__init__.py`
- Create: `services/worker/worker/report/evidence.py`
- Create: `tests/unit/worker/report/__init__.py`
- Create: `tests/unit/worker/report/test_evidence.py`

- [ ] **Step 1: Create package markers**

```bash
touch "/Users/eeshandhawan/Desktop/PulseAlpha AI/services/worker/worker/report/__init__.py"
touch "/Users/eeshandhawan/Desktop/PulseAlpha AI/tests/unit/worker/report/__init__.py"
```

- [ ] **Step 2: Write failing tests**

`tests/unit/worker/report/test_evidence.py`:
```python
from schemas.report import EvidenceBlock
from schemas.state import AnalysisState, CouncilOutput
from worker.report.evidence import build_evidence_blocks


def _full_state() -> AnalysisState:
    state = AnalysisState(user_query="Analyze", ticker_universe=["RELIANCE.NS"])
    state.market_data = {
        "RELIANCE.NS": {
            "fundamentals": {"pe_ratio": 28.0, "roe": 0.12, "market_cap": 1e12, "debt_to_equity": 0.3},
            "ohlcv": [{"date": f"2026-01-{i+1:02d}", "close": 100.0 + i} for i in range(30)],
            "_connector_confidence": {"fundamentals": 0.9, "ohlcv": 0.85},
        }
    }
    state.sentiment = {
        "RELIANCE.NS": {
            "headlines": [{"title": "Reliance posts strong Q4"}, {"title": "FII buying Reliance"}],
            "_connector_confidence": 0.7,
        }
    }
    state.rotation = {
        "points": [{"ticker": "RELIANCE.NS", "rs_ratio": 105.0, "rs_momentum": 102.0}]
    }
    state.alt_data = {
        "fii_dii": {"fii_net": 500.0, "dii_net": -100.0},
        "_fii_confidence": 0.8,
    }
    state.council_outputs = [
        CouncilOutput(persona="Contrarian", stance="bullish", rationale="r", confidence=0.8),
        CouncilOutput(persona="FirstPrinciples", stance="bullish", rationale="r", confidence=0.9),
        CouncilOutput(persona="Expansionist", stance="bullish", rationale="r", confidence=0.85),
        CouncilOutput(persona="Outsider", stance="neutral", rationale="r", confidence=0.6),
        CouncilOutput(persona="Synthesizer", stance="bullish", rationale="r", confidence=0.75),
    ]
    state.divergence_score = 0.2
    state.confidence = 0.75
    return state


def test_all_expected_blocks_present():
    state = _full_state()
    blocks = build_evidence_blocks(state)
    assert "RELIANCE.NS_FUNDAMENTALS" in blocks
    assert "RELIANCE.NS_OHLCV" in blocks
    assert "RELIANCE.NS_SENTIMENT" in blocks
    assert "RELIANCE.NS_RRG" in blocks
    assert "FII_DII_FLOWS" in blocks
    assert "COUNCIL_STANCES" in blocks
    assert "DIVERGENCE_SUMMARY" in blocks


def test_blocks_are_evidence_block_instances():
    state = _full_state()
    blocks = build_evidence_blocks(state)
    for block in blocks.values():
        assert isinstance(block, EvidenceBlock)


def test_missing_fundamentals_gives_zero_confidence():
    state = AnalysisState(user_query="q", ticker_universe=["TCS.NS"])
    blocks = build_evidence_blocks(state)
    assert "TCS.NS_FUNDAMENTALS" in blocks
    assert blocks["TCS.NS_FUNDAMENTALS"].confidence == 0.0
    assert blocks["TCS.NS_FUNDAMENTALS"].content == "No data available"


def test_council_stances_confidence_is_average():
    state = _full_state()
    blocks = build_evidence_blocks(state)
    # avg of 0.8, 0.9, 0.85, 0.6, 0.75 = 0.78
    assert abs(blocks["COUNCIL_STANCES"].confidence - 0.78) < 0.01


def test_divergence_summary_confidence_is_one_minus_score():
    state = _full_state()
    blocks = build_evidence_blocks(state)
    assert abs(blocks["DIVERGENCE_SUMMARY"].confidence - 0.8) < 0.01


def test_divergence_summary_content_has_contradictions():
    state = _full_state()
    state.contradictions = ["Bullish momentum vs bearish fundamentals"]
    blocks = build_evidence_blocks(state)
    assert "Bullish momentum" in blocks["DIVERGENCE_SUMMARY"].content


def test_rrg_block_shows_quadrant():
    state = _full_state()
    blocks = build_evidence_blocks(state)
    assert "Leading" in blocks["RELIANCE.NS_RRG"].content


def test_sentiment_block_has_headlines():
    state = _full_state()
    blocks = build_evidence_blocks(state)
    assert "Reliance posts strong Q4" in blocks["RELIANCE.NS_SENTIMENT"].content
```

- [ ] **Step 3: Run to confirm failure**

```bash
uv run pytest tests/unit/worker/report/test_evidence.py -v
```
Expected: `ModuleNotFoundError: No module named 'worker.report'`

- [ ] **Step 4: Implement `services/worker/worker/report/evidence.py`**

```python
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
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/unit/worker/report/test_evidence.py -v
```
Expected: All 8 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add services/worker/worker/report/__init__.py services/worker/worker/report/evidence.py \
        tests/unit/worker/report/__init__.py tests/unit/worker/report/test_evidence.py
git commit -m "feat(report): evidence block builder from AnalysisState"
```

---

### Task 3: prompt.py — 7-Section Report Prompt

**Files:**
- Create: `services/worker/worker/report/prompt.py`
- Create: `tests/unit/worker/report/test_prompt.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/worker/report/test_prompt.py`:
```python
from schemas.report import EvidenceBlock
from worker.report.prompt import SECTION_HEADERS, build_report_prompt


def _blocks() -> dict[str, EvidenceBlock]:
    return {
        "RELIANCE.NS_FUNDAMENTALS": EvidenceBlock(
            name="RELIANCE.NS_FUNDAMENTALS", content="PE=28.0", confidence=0.9, source="s"
        ),
        "FII_DII_FLOWS": EvidenceBlock(
            name="FII_DII_FLOWS", content="FII net: 500", confidence=0.8, source="s"
        ),
        "COUNCIL_STANCES": EvidenceBlock(
            name="COUNCIL_STANCES", content="Contrarian: bullish", confidence=0.8, source="s"
        ),
        "DIVERGENCE_SUMMARY": EvidenceBlock(
            name="DIVERGENCE_SUMMARY", content="Score: 0.2", confidence=0.8, source="s"
        ),
    }


def test_prompt_contains_all_seven_section_headers():
    prompt = build_report_prompt(_blocks(), "Analyze Reliance")
    for header in SECTION_HEADERS:
        assert header in prompt, f"Missing section header: {header}"


def test_prompt_contains_user_query():
    prompt = build_report_prompt(_blocks(), "Analyze Reliance Industries")
    assert "Analyze Reliance Industries" in prompt


def test_prompt_contains_evidence_content():
    prompt = build_report_prompt(_blocks(), "test query")
    assert "PE=28.0" in prompt
    assert "FII net: 500" in prompt


def test_prompt_contains_citation_instruction():
    prompt = build_report_prompt(_blocks(), "test")
    assert "[SRC:" in prompt
    assert "BLOCK_NAME" in prompt


def test_prompt_contains_block_names():
    prompt = build_report_prompt(_blocks(), "test")
    assert "RELIANCE.NS_FUNDAMENTALS" in prompt
    assert "FII_DII_FLOWS" in prompt


def test_section_headers_has_seven_items():
    assert len(SECTION_HEADERS) == 7
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/unit/worker/report/test_prompt.py -v
```
Expected: `ModuleNotFoundError: No module named 'worker.report.prompt'`

- [ ] **Step 3: Implement `services/worker/worker/report/prompt.py`**

```python
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
        evidence_lines.append(f"### {name} (confidence={block.confidence:.2f}, source={block.source})")
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
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/worker/report/test_prompt.py -v
```
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/worker/worker/report/prompt.py tests/unit/worker/report/test_prompt.py
git commit -m "feat(report): 7-section report prompt builder"
```

---

### Task 4: parser.py — Citation Tag Extraction

**Files:**
- Create: `services/worker/worker/report/parser.py`
- Create: `tests/unit/worker/report/test_parser.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/worker/report/test_parser.py`:
```python
from schemas.report import EvidenceBlock
from schemas.state import Citation
from worker.report.parser import parse_citations


def _blocks() -> dict[str, EvidenceBlock]:
    return {
        "RELIANCE_FUNDAMENTALS": EvidenceBlock(
            name="RELIANCE_FUNDAMENTALS", content="PE=28", confidence=0.9, source="s"
        ),
        "COUNCIL_STANCES": EvidenceBlock(
            name="COUNCIL_STANCES", content="bullish", confidence=0.8, source="s"
        ),
    }


def test_valid_tag_returns_citation():
    text = "Reliance has a PE of 28 [SRC:RELIANCE_FUNDAMENTALS:pe_ratio] which is below average."
    citations = parse_citations(text, _blocks())
    assert len(citations) == 1
    assert citations[0].source == "RELIANCE_FUNDAMENTALS"
    assert "Reliance has a PE of 28" in citations[0].claim


def test_unknown_block_is_dropped():
    text = "Some claim [SRC:UNKNOWN_BLOCK:field] about markets."
    citations = parse_citations(text, _blocks())
    assert len(citations) == 0


def test_no_tags_returns_empty_list():
    text = "This report has no citation tags at all."
    citations = parse_citations(text, _blocks())
    assert citations == []


def test_multiple_tags_in_one_line_returns_multiple_citations():
    text = "Bullish stance [SRC:COUNCIL_STANCES:Contrarian] with strong PE [SRC:RELIANCE_FUNDAMENTALS:pe_ratio]."
    citations = parse_citations(text, _blocks())
    assert len(citations) == 2
    sources = {c.source for c in citations}
    assert "COUNCIL_STANCES" in sources
    assert "RELIANCE_FUNDAMENTALS" in sources


def test_citation_claim_is_the_full_line():
    text = "Line one.\nReliance PE is strong [SRC:RELIANCE_FUNDAMENTALS:pe_ratio].\nLine three."
    citations = parse_citations(text, _blocks())
    assert len(citations) == 1
    assert "Reliance PE is strong" in citations[0].claim


def test_citations_are_citation_instances():
    text = "A claim [SRC:RELIANCE_FUNDAMENTALS:pe_ratio] here."
    citations = parse_citations(text, _blocks())
    assert all(isinstance(c, Citation) for c in citations)


def test_url_and_timestamp_are_none():
    text = "A claim [SRC:COUNCIL_STANCES:Contrarian] here."
    citations = parse_citations(text, _blocks())
    assert citations[0].url is None
    assert citations[0].timestamp is None
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/unit/worker/report/test_parser.py -v
```
Expected: `ModuleNotFoundError: No module named 'worker.report.parser'`

- [ ] **Step 3: Implement `services/worker/worker/report/parser.py`**

```python
from __future__ import annotations

import re

from schemas.report import EvidenceBlock
from schemas.state import Citation

_TAG_PATTERN = re.compile(r"\[SRC:([A-Z0-9_.]+):([a-zA-Z0-9_]+)\]")


def parse_citations(
    report_text: str, blocks: dict[str, EvidenceBlock]
) -> list[Citation]:
    """Extract [SRC:BLOCK:field] tags from report_text into Citation objects.

    Tags referencing unknown block names are silently dropped.
    Citation.claim is the full line containing the tag (with the tag removed).
    url and timestamp are always None in Phase 5.
    """
    citations: list[Citation] = []

    for line in report_text.splitlines():
        matches = _TAG_PATTERN.findall(line)
        if not matches:
            continue

        # Strip all tags from the line to get the clean claim text
        clean_line = _TAG_PATTERN.sub("", line).strip()

        for block_name, _field in matches:
            if block_name not in blocks:
                continue
            citations.append(
                Citation(
                    claim=clean_line,
                    source=block_name,
                    url=None,
                    timestamp=None,
                )
            )

    return citations
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/worker/report/test_parser.py -v
```
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/worker/worker/report/parser.py tests/unit/worker/report/test_parser.py
git commit -m "feat(report): citation tag parser with unknown block drop"
```

---

### Task 5: flags.py — Confidence Flag Post-Processor

**Files:**
- Create: `services/worker/worker/report/flags.py`
- Create: `tests/unit/worker/report/test_flags.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/worker/report/test_flags.py`:
```python
from schemas.report import EvidenceBlock
from schemas.state import Citation
from worker.report.flags import apply_confidence_flags

_LOW = EvidenceBlock(name="LOW_BLOCK", content="x", confidence=0.3, source="s")
_HIGH = EvidenceBlock(name="HIGH_BLOCK", content="x", confidence=0.8, source="s")
_BLOCKS = {"LOW_BLOCK": _LOW, "HIGH_BLOCK": _HIGH}


def _citation(source: str, claim: str = "Some claim") -> Citation:
    return Citation(claim=claim, source=source, url=None, timestamp=None)


def test_low_confidence_appends_warning():
    citations = [_citation("LOW_BLOCK", "Claim about low source")]
    result = apply_confidence_flags(citations, _BLOCKS)
    assert "⚠ low-confidence source" in result[0].claim


def test_high_confidence_unchanged():
    citations = [_citation("HIGH_BLOCK", "Claim about high source")]
    result = apply_confidence_flags(citations, _BLOCKS)
    assert "⚠" not in result[0].claim
    assert result[0].claim == "Claim about high source"


def test_empty_citations_returns_empty():
    result = apply_confidence_flags([], _BLOCKS)
    assert result == []


def test_exactly_at_threshold_is_not_flagged():
    blocks = {"EDGE_BLOCK": EvidenceBlock(name="EDGE_BLOCK", content="x", confidence=0.5, source="s")}
    citations = [_citation("EDGE_BLOCK", "Edge case claim")]
    result = apply_confidence_flags(citations, blocks)
    assert "⚠" not in result[0].claim


def test_custom_threshold():
    citations = [_citation("HIGH_BLOCK", "High confidence claim")]
    # threshold=0.9 means confidence=0.8 should be flagged
    result = apply_confidence_flags(citations, _BLOCKS, threshold=0.9)
    assert "⚠ low-confidence source" in result[0].claim


def test_original_citations_not_mutated():
    original_claim = "Original claim"
    citations = [_citation("LOW_BLOCK", original_claim)]
    apply_confidence_flags(citations, _BLOCKS)
    # original list item should not be mutated — function returns new list
    assert citations[0].claim == original_claim


def test_multiple_citations_flagged_correctly():
    citations = [
        _citation("LOW_BLOCK", "Low claim"),
        _citation("HIGH_BLOCK", "High claim"),
    ]
    result = apply_confidence_flags(citations, _BLOCKS)
    assert "⚠" in result[0].claim
    assert "⚠" not in result[1].claim
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/unit/worker/report/test_flags.py -v
```
Expected: `ModuleNotFoundError: No module named 'worker.report.flags'`

- [ ] **Step 3: Implement `services/worker/worker/report/flags.py`**

```python
from __future__ import annotations

from schemas.report import EvidenceBlock
from schemas.state import Citation

_DEFAULT_THRESHOLD = 0.5
_LOW_CONFIDENCE_SUFFIX = " ⚠ low-confidence source"


def apply_confidence_flags(
    citations: list[Citation],
    blocks: dict[str, EvidenceBlock],
    threshold: float = _DEFAULT_THRESHOLD,
) -> list[Citation]:
    """Return a new list of Citations with low-confidence sources flagged.

    For each citation where blocks[source].confidence < threshold,
    appends ' ⚠ low-confidence source' to citation.claim.
    Citations referencing unknown blocks are left unchanged.
    Original citations are not mutated.
    """
    result: list[Citation] = []
    for citation in citations:
        block = blocks.get(citation.source)
        if block is not None and block.confidence < threshold:
            flagged = citation.model_copy(
                update={"claim": citation.claim + _LOW_CONFIDENCE_SUFFIX}
            )
            result.append(flagged)
        else:
            result.append(citation)
    return result
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/worker/report/test_flags.py -v
```
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/worker/worker/report/flags.py tests/unit/worker/report/test_flags.py
git commit -m "feat(report): confidence flag post-processor for citations"
```

---

### Task 6: report/llm.py — LLM Call for Report Generation

**Files:**
- Create: `services/worker/worker/report/llm.py`

No unit tests — covered via mocks in the report node tests (Task 7).

- [ ] **Step 1: Implement `services/worker/worker/report/llm.py`**

```python
from __future__ import annotations

import logging
import os

from schemas.models import ModelTier

logger = logging.getLogger(__name__)


async def call_report_llm(prompt: str, system_prompt: str, tier: ModelTier) -> str:
    """Route report generation LLM call to HF/Ollama/PAID backend.

    HF_API failure falls back to Ollama. PAID falls back to Ollama (Phase 6).
    """
    if tier == ModelTier.HF_API:
        try:
            return await _call_hf(system_prompt, prompt)
        except Exception:
            logger.warning("HF API call failed for report, falling back to Ollama")
            return await _call_ollama(system_prompt, prompt)
    elif tier == ModelTier.OLLAMA:
        return await _call_ollama(system_prompt, prompt)
    else:  # ModelTier.PAID — deferred to Phase 6
        logger.warning("PAID tier not implemented in Phase 5, falling back to Ollama")
        return await _call_ollama(system_prompt, prompt)


async def _call_hf(system_prompt: str, user_message: str) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_huggingface import HuggingFaceEndpoint

    token = os.getenv("HF_API_TOKEN", "")
    model_name = os.getenv("HF_DEFAULT_MODEL", "HuggingFaceH4/zephyr-7b-beta")

    llm = HuggingFaceEndpoint(  # type: ignore[call-arg]
        repo_id=model_name,
        huggingfacehub_api_token=token,
        task="text-generation",
        model_kwargs={"max_new_tokens": 2048},
    )
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]
    response = await llm.ainvoke(messages)
    content = getattr(response, "content", None)
    return str(content) if content is not None else str(response)


async def _call_ollama(system_prompt: str, user_message: str) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_ollama import ChatOllama

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model_name = os.getenv("OLLAMA_DEFAULT_MODEL", "phi3:mini")

    llm = ChatOllama(base_url=base_url, model=model_name)
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]
    response = await llm.ainvoke(messages)
    return str(response.content)
```

- [ ] **Step 2: Verify importable**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI"
uv run python -c "from worker.report.llm import call_report_llm; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add services/worker/worker/report/llm.py
git commit -m "feat(report): tier-routing LLM client for report generation"
```

---

### Task 7: nodes/report.py — generate_report Node

**Files:**
- Create: `services/worker/worker/nodes/report.py`
- Create: `tests/unit/worker/test_report_node.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/worker/test_report_node.py`:
```python
from unittest.mock import AsyncMock, patch

import pytest
from schemas.state import AnalysisState, CouncilOutput
from worker.nodes.report import generate_report

_VALID_REPORT = """\
## Executive Summary
Reliance shows bullish momentum [SRC:COUNCIL_STANCES:Contrarian] with strong FII flows.

## Market Context
FII net inflows of 500Cr [SRC:FII_DII_FLOWS:fii_net] indicate institutional buying.

## Per-Ticker Analysis
### RELIANCE.NS
PE ratio of 28 [SRC:RELIANCE.NS_FUNDAMENTALS:pe_ratio] is below sector average.

## Council Debate Summary
Four of five personas [SRC:COUNCIL_STANCES:Synthesizer] were bullish after reconciliation.

## Contradictions & Risk Flags
No major contradictions [SRC:DIVERGENCE_SUMMARY:score] detected.

## Recommended Actions
Buy RELIANCE.NS [SRC:COUNCIL_STANCES:Expansionist] on dips.

## Confidence & Data Provenance
Overall confidence: 0.75 [SRC:DIVERGENCE_SUMMARY:confidence].
"""


def _make_state() -> AnalysisState:
    state = AnalysisState(user_query="Analyze Reliance", ticker_universe=["RELIANCE.NS"])
    state.confidence = 0.75
    state.divergence_score = 0.2
    state.market_data = {
        "RELIANCE.NS": {
            "fundamentals": {"pe_ratio": 28.0, "roe": 0.12},
            "ohlcv": [{"date": "2026-01-01", "close": 100.0}],
        }
    }
    state.alt_data = {"fii_dii": {"fii_net": 500.0, "dii_net": -100.0}}
    state.council_outputs = [
        CouncilOutput(persona="Contrarian", stance="bullish", rationale="r", confidence=0.8),
        CouncilOutput(persona="FirstPrinciples", stance="bullish", rationale="r", confidence=0.9),
        CouncilOutput(persona="Expansionist", stance="bullish", rationale="r", confidence=0.85),
        CouncilOutput(persona="Outsider", stance="neutral", rationale="r", confidence=0.6),
        CouncilOutput(persona="Synthesizer", stance="bullish", rationale="r", confidence=0.75),
    ]
    return state


@pytest.mark.asyncio
async def test_valid_llm_response_sets_report():
    with patch("worker.nodes.report.call_report_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _VALID_REPORT
        state = await generate_report(_make_state())
    assert state.report is not None
    assert len(state.report) >= 100
    assert "## Executive Summary" in state.report


@pytest.mark.asyncio
async def test_valid_llm_response_populates_citations():
    with patch("worker.nodes.report.call_report_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _VALID_REPORT
        state = await generate_report(_make_state())
    assert isinstance(state.citations, list)
    assert len(state.citations) > 0


@pytest.mark.asyncio
async def test_empty_llm_response_writes_fallback_report():
    with patch("worker.nodes.report.call_report_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = ""
        state = await generate_report(_make_state())
    assert state.report is not None
    assert "Report Generation Failed" in state.report
    assert "0.75" in state.report  # confidence injected


@pytest.mark.asyncio
async def test_short_llm_response_writes_fallback_report():
    with patch("worker.nodes.report.call_report_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "Too short"
        state = await generate_report(_make_state())
    assert "Report Generation Failed" in state.report


@pytest.mark.asyncio
async def test_llm_raises_writes_fallback_does_not_crash():
    with patch("worker.nodes.report.call_report_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = ConnectionError("LLM unavailable")
        state = await generate_report(_make_state())
    assert state.report is not None
    assert "Report Generation Failed" in state.report


@pytest.mark.asyncio
async def test_low_confidence_citation_is_flagged():
    # COUNCIL_STANCES will have low avg confidence if all outputs have confidence=0.1
    s = _make_state()
    s.council_outputs = [
        CouncilOutput(persona="Contrarian", stance="bullish", rationale="r", confidence=0.1),
        CouncilOutput(persona="FirstPrinciples", stance="bullish", rationale="r", confidence=0.1),
        CouncilOutput(persona="Expansionist", stance="bullish", rationale="r", confidence=0.1),
        CouncilOutput(persona="Outsider", stance="bullish", rationale="r", confidence=0.1),
        CouncilOutput(persona="Synthesizer", stance="bullish", rationale="r", confidence=0.1),
    ]
    report_text = "Bullish [SRC:COUNCIL_STANCES:Contrarian] overall."
    with patch("worker.nodes.report.call_report_llm", new_callable=AsyncMock) as mock_llm:
        # Pad to > 100 chars
        mock_llm.return_value = report_text + " " * 200
        state = await generate_report(s)
    assert any("⚠" in c.claim for c in state.citations)


@pytest.mark.asyncio
async def test_audit_log_has_generate_report_entries():
    with patch("worker.nodes.report.call_report_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = _VALID_REPORT
        state = await generate_report(_make_state())
    entries = [e for e in state.audit_log if e.node == "generate_report"]
    assert len(entries) >= 1
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/unit/worker/test_report_node.py -v
```
Expected: `ModuleNotFoundError: No module named 'worker.nodes.report'`

- [ ] **Step 3: Implement `services/worker/worker/nodes/report.py`**

```python
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
    stances = ", ".join(o.stance for o in state.council_outputs) if state.council_outputs else "none"
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
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/worker/test_report_node.py -v
```
Expected: All 7 tests PASS.

- [ ] **Step 5: Run all unit tests for regressions**

```bash
uv run pytest tests/unit/ -v --tb=short
```
Expected: All green.

- [ ] **Step 6: Commit**

```bash
git add services/worker/worker/nodes/report.py tests/unit/worker/test_report_node.py
git commit -m "feat(report): generate_report LangGraph node with fallback and citation flagging"
```

---

### Task 8: Wire generate_report into graph.py

**Files:**
- Modify: `services/worker/worker/graph.py`

- [ ] **Step 1: Read current graph.py**

Read `/Users/eeshandhawan/Desktop/PulseAlpha AI/services/worker/worker/graph.py` to confirm the current last edge is `run_council → END`.

- [ ] **Step 2: Add import and node**

Add `from worker.nodes.report import generate_report` after the `run_council` import. Add the node and update edges so the full `_build_graph()` reads:

```python
from worker.nodes.council import run_council
from worker.nodes.divergence import compute_divergence_node
from worker.nodes.features import compute_features
from worker.nodes.ingest import ingest_all_data
from worker.nodes.report import generate_report
from worker.nodes.validate import normalize_and_validate
```

```python
def _build_graph() -> Any:
    builder: StateGraph[AnalysisState] = StateGraph(AnalysisState)

    builder.add_node("ingest_all_data", _wrap(ingest_all_data))
    builder.add_node("compute_features", _wrap(compute_features))
    builder.add_node("compute_divergence", _wrap(compute_divergence_node))
    builder.add_node("normalize_and_validate", _wrap(normalize_and_validate))
    builder.add_node("run_council", _wrap(run_council))
    builder.add_node("generate_report", _wrap(generate_report))

    builder.set_entry_point("ingest_all_data")
    builder.add_edge("ingest_all_data", "compute_features")
    builder.add_edge("compute_features", "compute_divergence")
    builder.add_edge("compute_divergence", "normalize_and_validate")
    builder.add_edge("normalize_and_validate", "run_council")
    builder.add_edge("run_council", "generate_report")
    builder.add_edge("generate_report", END)

    return builder.compile(checkpointer=MemorySaver())
```

- [ ] **Step 3: Verify import**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI"
uv run python -c "from worker.graph import run_analysis; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Run unit tests**

```bash
uv run pytest tests/unit/ -v --tb=short
```
Expected: All green.

- [ ] **Step 5: Commit**

```bash
git add services/worker/worker/graph.py
git commit -m "feat(graph): wire generate_report node after run_council"
```

---

### Task 9: Integration Test — POST /analyze Returns Report

**Files:**
- Create: `tests/integration/test_report_endpoint.py`

- [ ] **Step 1: Write failing tests**

`tests/integration/test_report_endpoint.py`:
```python
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from schemas.connectors import ConnectorError, ConnectorResult

_MOCK_REPORT = """\
## Executive Summary
Reliance shows bullish momentum [SRC:COUNCIL_STANCES:Contrarian] overall.

## Market Context
FII net inflows [SRC:FII_DII_FLOWS:fii_net] support the bullish case.

## Per-Ticker Analysis
RELIANCE.NS PE of 28 [SRC:RELIANCE.NS_FUNDAMENTALS:pe_ratio] is fair value.

## Council Debate Summary
All personas [SRC:COUNCIL_STANCES:Synthesizer] agreed after round one.

## Contradictions & Risk Flags
No major contradictions [SRC:DIVERGENCE_SUMMARY:score] found.

## Recommended Actions
Buy RELIANCE.NS [SRC:COUNCIL_STANCES:Expansionist] on momentum.

## Confidence & Data Provenance
Confidence 0.75 [SRC:DIVERGENCE_SUMMARY:confidence]. All sources high quality.
"""

import json


def _ok(source: str, ticker: str, data: dict) -> ConnectorResult:
    return ConnectorResult(source=source, ticker=ticker, data=data, confidence=0.9)


def _err(source: str, ticker: str) -> ConnectorResult:
    return ConnectorResult(
        source=source, ticker=ticker, data={}, confidence=0.0,
        error=ConnectorError(code="FETCH_ERROR", message="mocked"),
    )


def _bullish_json(persona: str = "TestPersona") -> str:
    return json.dumps({
        "persona": persona,
        "stance": "bullish",
        "rationale": f"{persona} analysis complete.",
        "confidence": 0.8,
        "citations": ["test data point"],
    })


@pytest.fixture()
def mock_all():
    ohlcv = [{"date": f"2026-01-{i + 1:02d}", "close": 100.0 + i} for i in range(30)]
    bench = [{"date": f"2026-01-{i + 1:02d}", "close": 200.0 + i} for i in range(30)]

    async def md_side_effect(ticker: str) -> ConnectorResult:
        if ticker == "^NSEI":
            return _ok("md", "^NSEI", {"ohlcv": bench})
        return _ok("md", ticker, {"ohlcv": ohlcv})

    with (
        patch("worker.nodes.ingest.FundamentalsConnector") as MockFund,
        patch("worker.nodes.ingest.MarketDataConnector") as MockMD,
        patch("worker.nodes.ingest.FIIDIIConnector") as MockFII,
        patch("worker.nodes.ingest.SentimentConnector") as MockSent,
        patch("worker.nodes.ingest.IPOGMPConnector") as MockGMP,
        patch("worker.nodes.council.call_llm", new_callable=AsyncMock) as MockCouncilLLM,
        patch("worker.nodes.report.call_report_llm", new_callable=AsyncMock) as MockReportLLM,
    ):
        MockFund.return_value.fetch = AsyncMock(
            return_value=_ok("fund", "RELIANCE.NS", {"pe_ratio": 28.0, "sector": "Energy"})
        )
        MockMD.return_value.fetch = AsyncMock(side_effect=md_side_effect)
        MockFII.return_value.fetch = AsyncMock(
            return_value=_ok("fii", "MARKET", {
                "fii_net": 500.0, "fii_buy": 1000.0, "fii_sell": 500.0,
                "dii_net": -100.0, "dii_buy": 200.0, "dii_sell": 300.0,
            })
        )
        MockSent.return_value.fetch = AsyncMock(
            return_value=_ok("sent", "RELIANCE.NS", {"headlines": []})
        )
        MockGMP.return_value.fetch = AsyncMock(return_value=_err("gmp", "RELIANCE"))
        MockCouncilLLM.side_effect = lambda sys, usr, tier: _bullish_json()
        MockReportLLM.return_value = _MOCK_REPORT
        yield


@pytest.mark.asyncio
async def test_analyze_returns_report_field(mock_all):
    from api.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/analyze",
            json={"ticker_universe": ["RELIANCE.NS"], "user_query": "Analyze Reliance"},
        )
    assert r.status_code == 200
    body = r.json()
    assert "report" in body
    assert isinstance(body["report"], str)
    assert len(body["report"]) > 0


@pytest.mark.asyncio
async def test_analyze_returns_citations_list(mock_all):
    from api.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/analyze",
            json={"ticker_universe": ["RELIANCE.NS"], "user_query": "Analyze Reliance"},
        )
    body = r.json()
    assert "citations" in body
    assert isinstance(body["citations"], list)


@pytest.mark.asyncio
async def test_citations_have_required_fields(mock_all):
    from api.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/analyze",
            json={"ticker_universe": ["RELIANCE.NS"], "user_query": "Analyze Reliance"},
        )
    body = r.json()
    for citation in body["citations"]:
        assert "claim" in citation
        assert "source" in citation


@pytest.mark.asyncio
async def test_audit_log_contains_report_entry(mock_all):
    from api.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/analyze",
            json={"ticker_universe": ["RELIANCE.NS"], "user_query": "Analyze Reliance"},
        )
    body = r.json()
    report_entries = [e for e in body["audit_log"] if e["node"] == "generate_report"]
    assert len(report_entries) >= 1
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/integration/test_report_endpoint.py -v
```
Expected: Tests fail (node not in graph yet — but graph is wired from Task 8, so likely fails on import or LLM mock not matching).

- [ ] **Step 3: Run to confirm tests pass**

```bash
uv run pytest tests/integration/test_report_endpoint.py -v
```
Expected: All 4 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_report_endpoint.py
git commit -m "test(integration): POST /analyze returns report and citations fields"
```

---

### Task 10: Full Suite Verification

- [ ] **Step 1: Run all unit tests**

```bash
uv run pytest tests/unit/ -v --tb=short
```
Expected: All green.

- [ ] **Step 2: Run all integration tests**

```bash
uv run pytest tests/integration/test_report_endpoint.py tests/integration/test_council_endpoint.py -v --tb=short
```
Expected: All green.

- [ ] **Step 3: Lint**

```bash
uv run ruff check .
```
Expected: No errors.

- [ ] **Step 4: Type check**

```bash
uv run mypy libs/ services/ --ignore-missing-imports
```
Expected: No errors.

- [ ] **Step 5: Final commit if any lint/mypy fixes needed**

```bash
git add -A
git commit -m "chore: Phase 5 complete — report generation with citation map and confidence flagging"
```

---

## Phase Exit Criteria

| Check | Command | Expected |
|---|---|---|
| Unit tests | `uv run pytest tests/unit/ -v` | All green |
| Integration tests | `uv run pytest tests/integration/test_report_endpoint.py -v` | All 4 green |
| report field | `body["report"]` non-empty string | True |
| citations field | `body["citations"]` is a list | True |
| Audit log | `generate_report` entries in `audit_log` | ≥ 1 |
| Low-confidence flag | `⚠ low-confidence source` in flagged citations | True |
| Lint | `uv run ruff check .` | No errors |
| Types | `uv run mypy libs/ services/ --ignore-missing-imports` | No errors |

## Implementation Notes

- **Patch target for report LLM in tests:** `worker.nodes.report.call_report_llm` (imported into report node's namespace via `from worker.report.llm import call_report_llm`)
- **Patch target for council LLM in integration tests:** `worker.nodes.council.call_llm` (unchanged from Phase 4)
- **`_connector_confidence` key:** `evidence.py` reads `market_data[ticker]["_connector_confidence"]` for per-field confidence values. If absent (most test states won't have it), it defaults to `0.5`. This is a Phase 5 convention — connector results don't currently write this key, so most blocks will have `confidence=0.5` in production until Phase 6 wires it properly.
- **Note for Phase 6 (backtesting):** To enable historical replay, add a `as_of_date: date | None` field to `AnalysisState` and pass it to connectors as a cutoff. OHLCV and FII/DII are historically available via yfinance and SEBI data; fundamentals will be approximate (nearest quarterly filing). Sentiment is not available historically and should be disabled in backtest mode.
