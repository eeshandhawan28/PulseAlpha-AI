# Phase 3: LangGraph Orchestration Design

**Date:** 2026-05-24
**Project:** PulseAlpha AI
**Phase:** 3 — LangGraph Orchestration (builds on Phase 0+1+2 foundation)

---

## Goal

Build a LangGraph-based orchestration layer (`services/worker/`) that wires Phase 1 connectors and Phase 2 feature functions into a stateful analysis pipeline. Expose the graph via a `POST /analyze` FastAPI endpoint that accepts a ticker universe and returns a fully-populated `AnalysisState` as JSON.

---

## Constraints

- All LangGraph and graph node code must be Python 3.11+
- No LLM calls in Phase 3 — pure data ingestion and feature computation only
- Optional connectors (GMP, sentiment) must never hard-block the graph — graceful None handling required
- Graph uses in-memory checkpointing (MemorySaver) — no persistence across process restarts
- The HTTP endpoint blocks until the graph completes — no background jobs or queues

---

## Architecture

### Design Decision: Fixed Sequential Graph

The graph uses a fixed sequential topology with `asyncio.gather()` inside each node (Option C from topology brainstorm). This is the correct choice for Phase 3 because:

- Ingestion and feature computation nodes don't make decisions — they always run the same operations
- Hard data dependencies (RRG needs prices, divergence needs flow) mean the ordering IS the dependency graph
- Dynamic routing belongs in Phase 4 (council layer), where the agent genuinely chooses: escalate model tier, loop for reconciliation, or finalize

Dynamic LangGraph conditional edges will be introduced in Phase 4 when there is real branching logic driven by state.

### Graph Flow

```
START
  ↓
ingest_all_data
  asyncio.gather(fundamentals, market_data, fii_dii, sentiment, ipo_gmp)
  writes: state.market_data, state.alt_data, state.sentiment
  ↓
compute_features
  asyncio.gather(compute_rrg, compute_flow_strength) + sequential compute_gmp_disagreement
  writes: state.rotation, state.alt_data["flow"], state.alt_data["gmp"]
  ↓
compute_divergence
  calls divergence.compute_divergence() from Phase 2
  writes: state.divergence_score, state.contradictions
  ↓
normalize_and_validate
  validates required fields, sets state.confidence
  ↓
END
```

### Checkpointing

LangGraph `MemorySaver` — checkpoints after each node completes, keyed by `thread_id` derived from `state.run_id`. Survives node-level failures within a process but not process crashes. Sufficient for Phase 3.

---

## Node Contracts

Each node is a plain async function:
```python
async def node_name(state: AnalysisState) -> AnalysisState
```

No LLM calls. No side effects beyond writing to `AnalysisState`.

### `ingest_all_data`

- Runs all 5 connectors concurrently via `asyncio.gather()`
- Connectors: `FundamentalsConnector`, `MarketDataConnector` (yfinance OHLCV), `FIIDIIConnector`, `SentimentConnector`, `IPOGMPConnector`
- Writes raw connector outputs:
  - `state.market_data`: prices dict (ticker → DataFrame), quotes
  - `state.alt_data`: fii_dii raw result, gmp raw result
  - `state.sentiment`: headlines dict
- Failed connectors write `None` to their field — node never raises
- Appends one `AuditEntry` per connector failure

### `compute_features`

- Reads from `state.market_data` and `state.alt_data`
- `asyncio.gather(compute_rrg(...), compute_flow_strength(...))` runs RRG and flow in parallel
- `compute_gmp_disagreement(...)` runs sequentially after (depends on GMP connector result)
- Writes:
  - `RRGResult` → `state.rotation`
  - `FlowStrengthResult` → `state.alt_data["flow"]`
  - `IPOGMPResult | None` → `state.alt_data["gmp"]`
- Missing prices for a ticker → RRG skips that ticker and logs via `state.append_audit`
- Missing FII/DII data → `state.alt_data["flow"]` is None, node doesn't raise

### `compute_divergence`

- Reads `state.rotation`, `state.alt_data["flow"]`, `state.sentiment`, `state.alt_data["gmp"]`
- Calls `divergence.compute_divergence()` from `libs/features`
- Writes:
  - `DivergenceResult.divergence_score` → `state.divergence_score`
  - `DivergenceResult.contradictions` → `state.contradictions`
- If flow data is missing → writes `divergence_score=0.0`, appends audit entry

### `normalize_and_validate`

- Checks required fields are populated, logs gaps via `state.append_audit`
- Sets `state.confidence` using heuristic:
  ```
  confidence = (connectors_ok / total_connectors) * 0.5 + (1 - divergence_score) * 0.5
  ```
- Appends final audit summary entry with connector success count and divergence score

---

## API Layer

### Endpoint

```
POST /analyze
Content-Type: application/json

Request body:
{
  "ticker_universe": ["RELIANCE.NS", "TCS.NS"],
  "user_query": "Analyze these stocks"
}

Response: AnalysisState (full populated state as JSON)
```

The endpoint:
1. Validates the request body (Pydantic model)
2. Constructs `AnalysisState` from request fields
3. Builds the LangGraph graph with `MemorySaver` checkpointer
4. Invokes the graph with `thread_id = state.run_id`
5. Returns the final `AnalysisState` as JSON

Response includes: market_data, rotation (RRG), alt_data (flow, gmp), sentiment, divergence_score, contradictions, confidence, audit_log.

### Separation of Concerns

- `services/api/routes/analyze.py` — HTTP route handler only
- `services/worker/graph.py` — graph construction and invocation (imported by the route)
- `services/worker/nodes/` — individual node implementations

---

## File Map

```
services/
├── api/
│   ├── main.py                      # MODIFIED: include analyze router
│   └── routes/
│       └── analyze.py               # NEW: POST /analyze route
└── worker/
    ├── graph.py                     # NEW: LangGraph graph construction + MemorySaver
    └── nodes/
        ├── __init__.py              # NEW
        ├── ingest.py                # NEW: ingest_all_data node
        ├── features.py              # NEW: compute_features node
        ├── divergence.py            # NEW: compute_divergence node
        └── validate.py              # NEW: normalize_and_validate node

tests/
├── unit/
│   └── worker/
│       ├── __init__.py              # NEW
│       ├── test_ingest_node.py      # NEW
│       ├── test_feature_node.py     # NEW
│       ├── test_divergence_node.py  # NEW
│       └── test_validate_node.py   # NEW
└── integration/
    └── test_analyze_endpoint.py     # NEW
```

---

## Testing Strategy

All tests use mocked connectors — no real network calls.

| Test file | What it verifies |
|-----------|-----------------|
| `test_ingest_node.py` | All connectors succeed → correct state fields populated; one connector fails → state still valid, audit log has failure entry; all connectors fail → empty data, no exception |
| `test_feature_node.py` | RRG result → `state.rotation`; flow → `state.alt_data["flow"]`; None GMP → `state.alt_data["gmp"]` is None, no raise |
| `test_divergence_node.py` | `divergence_score` and `contradictions` written correctly; missing flow → score=0.0, no crash |
| `test_validate_node.py` | Confidence heuristic math; all ok + zero divergence → confidence near 1.0; all failed → near 0.0 |
| `test_analyze_endpoint.py` | `POST /analyze` returns 200 with valid `AnalysisState` JSON; missing `ticker_universe` returns 422; full graph run completes without raising |

---

## Phase Exit Criteria

- `POST /analyze` with mocked connectors returns HTTP 200 with a valid `AnalysisState` JSON body
- Response includes `divergence_score`, `confidence`, and at least one `RRGPoint` in `state.rotation`
- All unit and integration tests pass
- `AnalysisState.audit_log` contains entries from all four nodes on a successful run

---

## Dependencies

`services/worker/pyproject.toml` — already listed from Phase 0 plan:
```toml
"langgraph>=0.2",
"langchain>=0.2",
"features",   # add: Phase 2 feature library
```

No new dependencies for `services/api`.
