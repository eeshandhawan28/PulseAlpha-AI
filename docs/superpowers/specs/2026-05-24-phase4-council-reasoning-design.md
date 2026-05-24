# Phase 4: Council Reasoning Layer Design

**Date:** 2026-05-24
**Project:** PulseAlpha AI
**Phase:** 4 — Council Reasoning (builds on Phase 0+1+2+3 foundation)

---

## Goal

Add a council reasoning layer to the Phase 3 LangGraph pipeline. Five LLM-powered analyst personas each receive the Phase 3 analysis state and independently produce a structured stance (`CouncilOutput`). A variance-based loopback reconciles disagreement up to 3 times. The result is written to `state.council_outputs` and used to update `state.confidence`.

---

## Constraints

- All LLM calls use JSON mode — persona responses are parsed into `CouncilOutput` via `model_validate`
- One retry per persona on parse failure; second failure → neutral `CouncilOutput`, node never raises
- All 5 persona calls run concurrently via `asyncio.gather()` — no sequential persona ordering
- Tier is decided once per `run_council` invocation — no mid-run tier switching
- Reconciliation loop capped at `max_iterations=3` — no infinite cycles possible
- No new API routes — `POST /analyze` already calls `run_analysis()` which runs the full graph
- All LLM calls mocked in tests — no real API calls in CI

---

## Architecture

Phase 4 extends the Phase 3 graph with one new node appended after `normalize_and_validate`:

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
run_council              (NEW)
  ↓
END
```

`run_council` is a single async LangGraph node. All council logic — parallel persona calls, variance check, reconciliation loop — lives inside this node as plain Python. No sub-graph, no conditional LangGraph edges.

---

## Council Sub-Package

All council logic lives in `services/worker/worker/council/`:

| File | Responsibility |
|------|---------------|
| `personas.py` | 5 persona system prompts + registry dict |
| `llm.py` | Tier-routing LLM client (HF → Ollama → Paid fallback) |
| `parser.py` | JSON → CouncilOutput parsing with one retry |
| `variance.py` | Disagreement score computation + threshold check |

---

## Persona Contracts

Five personas, each a named system prompt + archetype. All five receive the same compressed Phase 3 context.

| Persona | Archetype | Focus |
|---------|-----------|-------|
| Contrarian | Challenges the consensus view | What is the crowd missing? |
| First Principles | Strips away narrative, focuses on numbers | PE, ROE, debt — does the math check out? |
| Expansionist | Momentum and flow optimist | Sector rotation, FII inflows, RRG leadership |
| Outsider | Treats data as a stranger would | No prior thesis, pure pattern reading |
| Synthesizer | Integrates all signals, flags conflicts | Last to speak in reconciliation |

**Context format** — same for all 5 personas, serialized to a string capped at ~1500 tokens:
- Top 3 sentiment headlines per ticker
- Key fundamentals: PE, ROE, market cap, debt-to-equity
- RRG quadrant per ticker
- FII/DII net flows
- `divergence_score` and `contradictions` list from Phase 3

**Output schema** — each persona call returns JSON parsed into `CouncilOutput`:
```python
class CouncilOutput(BaseModel):
    persona: str
    stance: Literal["bullish", "bearish", "neutral"]
    rationale: str
    confidence: float  # 0.0–1.0
    citations: list[str]
```

**Parse failure handling:**
1. Parse failure → retry once with explicit error: "Your previous response was not valid JSON. Return only a JSON object matching this schema: ..."
2. Second failure → `CouncilOutput(persona=..., stance="neutral", rationale="parse failed", confidence=0.0, citations=[])`
3. Node never raises on LLM or parse errors

---

## LLM Tier Routing

Tier is decided once before the `asyncio.gather()` — all 5 personas use the same tier within a single run.

```
state.divergence_score ≤ 0.7  →  Tier A (HF Inference API)
state.divergence_score > 0.7  →  Tier C (Paid) if daily cap not exceeded, else Tier B (Ollama)
Tier A call failure            →  fall back to Tier B (Ollama)
```

Configuration via existing `RoutingConfig` from `libs/schemas`:
- `divergence_threshold = 0.7`
- `daily_paid_cap_usd = 2.0`
- `default_tier = ModelTier.HF_API`

---

## Variance Check & Reconciliation Loop

**Disagreement metric** (computed after initial 5-persona batch and after each reconciliation round):

```
majority = max(bullish_count, bearish_count, neutral_count)
disagreement = 1 - (majority / 5)
```

- `disagreement = 0.0` → unanimous
- `disagreement = 0.4` → 3/2 split (e.g. 3 bullish, 2 bearish)
- `disagreement = 0.6` → worst-case 2/2/1 split

**Threshold:** `RoutingConfig.divergence_threshold` (default 0.7)

If `disagreement < threshold` → skip reconciliation, write outputs.

**Reconciliation loop** (runs only when `disagreement ≥ threshold`):

1. Identify dissenting personas — those whose stance differs from the majority stance
2. Each dissenting persona gets a revision call: same Phase 3 context + reconciliation prompt showing majority stance + Synthesizer's rationale from current round
3. Re-compute disagreement on revised stances
4. If still ≥ threshold and `iteration < 3` → loop back to step 1
5. After 3 iterations → accept current stances, append audit entry noting unresolved disagreement

**Synthesizer role in reconciliation:** Synthesizer runs in the initial parallel batch only. During reconciliation rounds it does not get a revision call — its rationale is used to inform dissenters, not revised itself.

**Confidence update** after council completes:
```
state.confidence = (1 - final_disagreement) * 0.5 + state.confidence * 0.5
```

---

## File Map

```
services/worker/worker/
├── council/
│   ├── __init__.py
│   ├── personas.py        # 5 persona system prompts + registry dict
│   ├── llm.py             # tier-routing LLM client, HF→Ollama→Paid fallback
│   ├── parser.py          # JSON→CouncilOutput with one retry on parse failure
│   └── variance.py        # disagreement score + threshold check
└── nodes/
    └── council.py         # run_council node — orchestrates council sub-package

tests/unit/worker/
├── council/
│   ├── __init__.py
│   ├── test_personas.py   # prompt rendering, all 5 personas produce valid strings
│   ├── test_parser.py     # valid JSON→CouncilOutput; bad JSON→retry; double fail→neutral
│   └── test_variance.py   # unanimous→0.0; 3/2 split→0.4; threshold logic
└── test_council_node.py   # run_council end-to-end with mocked LLM calls

tests/integration/
└── test_council_endpoint.py  # POST /analyze with mocked LLM returns council_outputs
```

**Modified files:**
- `services/worker/worker/graph.py` — add `run_council` node after `normalize_and_validate`
- `services/worker/pyproject.toml` — add `langchain-openai` or equivalent for Paid tier if not present

---

## Testing Strategy

All LLM calls mocked — no real API calls in CI.

| Test file | What it verifies |
|-----------|-----------------|
| `test_personas.py` | All 5 personas render non-empty system prompts; persona registry contains all 5 keys |
| `test_parser.py` | Valid JSON → CouncilOutput; invalid JSON → retry; second failure → neutral output, no raise |
| `test_variance.py` | Unanimous 5/0/0 → 0.0; 3/2/0 split → 0.4; threshold check logic |
| `test_council_node.py` | All personas succeed → 5 outputs in state; reconciliation loop terminates at max_iterations; parse failure → neutral entry, no crash; confidence updated correctly |
| `test_council_endpoint.py` | POST /analyze returns 200 with `council_outputs` list of 5; `state.confidence` updated |

---

## Phase Exit Criteria

- `POST /analyze` returns `council_outputs` with 5 `CouncilOutput` entries
- `state.confidence` reflects council reconciliation result
- Reconciliation loop always terminates — max 3 iterations enforced
- All unit + integration tests pass
- `state.audit_log` contains at least one entry from `run_council`

---

## Dependencies

No new Python packages required if `langchain-huggingface` and `langchain-ollama` are already installed (they are, from Phase 3 `pyproject.toml`). Paid tier (Tier C) will require `langchain-openai` — add to `services/worker/pyproject.toml` as optional, guarded by `ModelTier.PAID` code path.
