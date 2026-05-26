# Phase 5: Report Generation & Auditability Design

**Date:** 2026-05-26
**Project:** PulseAlpha AI
**Phase:** 5 — Report Generation (builds on Phase 0+1+2+3+4 foundation)

---

## Goal

Add a report generation layer that synthesizes all Phase 1–4 outputs into a structured 7-section markdown report. Every factual claim carries an inline citation tag tied to a named evidence block. A post-processing step converts citation tags into typed `Citation` objects and flags claims backed by low-confidence sources.

---

## Constraints

- `state.report` stays as `str | None` — no schema changes to `AnalysisState`
- `state.citations: list[Citation]` already defined — populated by this phase
- Single LLM call per report (not per section) — latency and cost controlled
- Node never raises — fallback report written on LLM failure or empty response
- All LLM calls mocked in tests — no real API calls in CI
- Reuses tier-routing logic from Phase 4 (`select_tier` / `ModelTier`)
- Citation parsing is regex-based — if tag references unknown block, silently dropped

---

## Architecture

Phase 5 extends the graph with one new node appended after `run_council`:

```
START
  ↓
ingest_all_data          (Phase 3 — unchanged)
  ↓
compute_features         (Phase 3 — unchanged)
  ↓
compute_divergence       (Phase 3 — unchanged)
  ↓
normalize_and_validate   (Phase 3 — unchanged)
  ↓
run_council              (Phase 4 — unchanged)
  ↓
generate_report          (NEW)
  ↓
END
```

`generate_report` is a single async LangGraph node backed by a new `services/worker/worker/report/` sub-package. Internally it runs five sequential steps:

1. **Evidence building** — serialize `AnalysisState` into named evidence blocks
2. **Prompt rendering** — inject evidence blocks into the 7-section report prompt
3. **LLM call** — route to HF/Ollama/PAID via existing tier logic
4. **Citation parsing** — extract `[SRC:block:field]` tags → `Citation` objects
5. **Confidence flagging** — append `⚠ low-confidence source` where block confidence < 0.5

---

## Evidence Blocks

`evidence.py` builds a `dict[str, EvidenceBlock]` from `AnalysisState`. Block naming convention: `{TICKER}_{DOMAIN}` for per-ticker data, flat names for cross-ticker data.

### EvidenceBlock Schema (new in `libs/schemas/schemas/report.py`)

```python
class EvidenceBlock(BaseModel):
    name: str
    content: str        # serialized text injected into prompt
    confidence: float   # drives speculative flagging (0.0–1.0)
    source: str         # human-readable source name e.g. "YFinance fundamentals"
```

### Block Registry

| Block name | Content | Confidence source |
|---|---|---|
| `{TICKER}_FUNDAMENTALS` | PE, ROE, market cap, D/E | `ConnectorResult.confidence` from fundamentals connector |
| `{TICKER}_OHLCV` | Last close, 30d trend direction | `ConnectorResult.confidence` from market data connector |
| `{TICKER}_SENTIMENT` | Top 3 headlines + polarity | `ConnectorResult.confidence` from sentiment connector |
| `{TICKER}_RRG` | Quadrant, rs_ratio, rs_momentum | Derived from rotation state; confidence = `state.confidence` |
| `FII_DII_FLOWS` | FII net, DII net | `ConnectorResult.confidence` from FII connector |
| `COUNCIL_STANCES` | All 5 persona stances + rationales | Average `CouncilOutput.confidence` across 5 personas |
| `DIVERGENCE_SUMMARY` | Score, contradictions list | `1 - state.divergence_score` |

**Missing data handling** — if a connector result is absent for a ticker, the block is still created with `content="No data available"` and `confidence=0.0`. The node never skips a block or raises.

---

## Citation Tag Format

Inline tags embedded by the LLM in the markdown report:

```
[SRC:RELIANCE_FUNDAMENTALS:pe_ratio]
[SRC:COUNCIL_STANCES:Contrarian]
[SRC:FII_DII_FLOWS:fii_net]
```

**Regex pattern:** `\[SRC:([A-Z0-9_]+):([a-zA-Z0-9_]+)\]`

Tags referencing unknown block names are silently dropped. The report string is never modified during citation parsing — only `state.citations` is populated.

**`Citation` schema** (already in `libs/schemas/schemas/state.py`):
```python
class Citation(BaseModel):
    claim: str       # the sentence containing the tag (extracted by parser)
    source: str      # block name e.g. "RELIANCE_FUNDAMENTALS"
    url: str | None  # None for all Phase 5 citations
    timestamp: datetime | None
```

---

## Confidence Flagging

`flags.py` post-processes the parsed citations:

```
For each Citation where blocks[citation.source].confidence < 0.5:
    citation.claim += " ⚠ low-confidence source"
```

Threshold is `0.5` (hardcoded in Phase 5, configurable in Phase 6). Citations referencing unknown blocks are already dropped before this step runs.

---

## Report Sections & Prompt Contract

Single LLM call producing all 7 sections in fixed order:

| # | Section header | Primary evidence blocks |
|---|---|---|
| 1 | `## Executive Summary` | `COUNCIL_STANCES`, `DIVERGENCE_SUMMARY` |
| 2 | `## Market Context` | `FII_DII_FLOWS` |
| 3 | `## Per-Ticker Analysis` | `{TICKER}_RRG`, `{TICKER}_FUNDAMENTALS`, `{TICKER}_OHLCV` |
| 4 | `## Council Debate Summary` | `COUNCIL_STANCES`, `DIVERGENCE_SUMMARY` |
| 5 | `## Contradictions & Risk Flags` | `DIVERGENCE_SUMMARY`, `{TICKER}_SENTIMENT` |
| 6 | `## Recommended Actions` | All blocks |
| 7 | `## Confidence & Data Provenance` | All blocks |

**Prompt citation instruction (appended to every prompt):**
```
For every factual claim, append a citation tag immediately after the claim:
[SRC:BLOCK_NAME:field_name]
Use only block names from the evidence provided. Do not invent block names.
Respond with the full markdown report only. No preamble, no trailing text.
```

**Fallback report** — written to `state.report` when LLM returns empty string or response < 100 characters:
```markdown
## Report Generation Failed
Confidence: {state.confidence:.2f}
Council stances: {comma-joined stances}
Run ID: {state.run_id}
```

---

## File Map

```
libs/schemas/schemas/
└── report.py                      NEW — EvidenceBlock schema

services/worker/worker/
├── report/
│   ├── __init__.py                NEW — empty package marker
│   ├── evidence.py                NEW — build_evidence_blocks(state) → dict[str, EvidenceBlock]
│   ├── prompt.py                  NEW — build_report_prompt(blocks, query) → str
│   ├── parser.py                  NEW — parse_citations(report_text, blocks) → list[Citation]
│   ├── flags.py                   NEW — apply_confidence_flags(citations, blocks, threshold=0.5) → list[Citation]
│   └── llm.py                     NEW — call_report_llm(prompt, tier) → str
└── nodes/
    └── report.py                  NEW — generate_report() LangGraph node

tests/unit/
├── schemas/
│   └── test_report_schema.py      NEW — EvidenceBlock validation
└── worker/
    ├── report/
    │   ├── __init__.py            NEW
    │   ├── test_evidence.py       NEW — block building from state
    │   ├── test_prompt.py         NEW — prompt renders all 7 section headers
    │   ├── test_parser.py         NEW — [SRC:...] extraction, unknown block drop
    │   └── test_flags.py          NEW — confidence < 0.5 → ⚠ flag appended
    └── test_report_node.py        NEW — generate_report end-to-end with mocked LLM

tests/integration/
└── test_report_endpoint.py        NEW — POST /analyze returns report non-empty, citations list

Modified files:
- libs/schemas/schemas/__init__.py       — export EvidenceBlock
- libs/schemas/schemas/state.py          — no changes needed (report/citations already defined)
- services/worker/worker/graph.py        — add generate_report node after run_council
```

---

## Testing Strategy

| Test file | What it verifies |
|---|---|
| `test_report_schema.py` | EvidenceBlock validates correctly; confidence clamped [0,1] |
| `test_evidence.py` | All expected blocks present for full state; missing data → confidence=0.0, not crash; block names follow naming convention |
| `test_prompt.py` | Rendered prompt contains all 7 section headers; evidence content injected; citation instruction present |
| `test_parser.py` | Valid `[SRC:X:y]` → Citation with correct source/claim; unknown block → dropped; no tags → empty list; multiple tags in one sentence → multiple Citations |
| `test_flags.py` | confidence < 0.5 → `⚠ low-confidence source` appended to claim; confidence ≥ 0.5 → claim unchanged; empty citations list → no-op |
| `test_report_node.py` | LLM returns valid markdown → `state.report` set, `state.citations` populated; LLM returns empty → fallback report written; LLM raises → fallback report written, node never raises; audit log has `generate_report` entries |
| `test_report_endpoint.py` | `POST /analyze` returns 200, `report` field non-empty string, `citations` is a list |

---

## Phase Exit Criteria

- `POST /analyze` returns `state.report` as a non-empty markdown string
- `state.citations` is a list of `Citation` objects (may be empty if LLM omits tags)
- Low-confidence citations carry `⚠ low-confidence source` in `claim`
- `generate_report` node never raises under any LLM failure mode
- All unit + integration tests pass
- `ruff check .` clean, `mypy` clean
- `state.audit_log` contains at least one entry from `generate_report`

---

## Dependencies

No new Python packages required. `re` (stdlib) handles citation tag parsing. Reuses `langchain-huggingface` and `langchain-ollama` already in `services/worker/pyproject.toml`. `EvidenceBlock` added to `libs/schemas` — no new lib needed.
