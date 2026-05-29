# Plan: Build a Stateful Multi-Agent Indian Stock Analysis Platform (Free-First LLM Strategy)

## 1) What was analyzed from your source document

Your source design is strong on vision and research depth. It already defines:
- A LangGraph supervisor architecture with cyclical state updates.
- Rich data modules: fundamentals, sentiment, corporate filings, IPO GMP, FII/DII flows, and RRG sector rotation.
- A council-style reasoning layer for debate and synthesis.
- A confidence-driven output structure.

Main gaps to close for real execution:
- No concrete repository structure and service boundaries.
- No strict schema contracts and data quality gates.
- No benchmark/evaluation loop to decide when paid models are worth it.
- No operational plan for rate limits, retries, observability, and CI/CD.
- No hard cost controls and model routing policy.

This plan turns your document into an implementation roadmap that Claude can execute end-to-end.

---

## 2) Project objective

Build a production-ready, stateful multi-agent stock analysis system for Indian markets that:
- Works first with free/local LLMs (Ollama + Hugging Face free/provider credits).
- Uses paid LLMs only when measured quality gains justify the spend.
- Produces explainable portfolio directives with confidence scoring, citations, and risk flags.

Non-goal for Phase 1:
- Full auto-trading execution with broker order placement.

---

## 3) Success criteria (must be measurable)

### Product success
- Generate a complete analysis report for any ticker universe in under 120 seconds for cached paths and under 300 seconds for cold paths.
- Reports include: data provenance, contradictions found, confidence score, and recommended actions.

### Model performance success
- At least 80% pass rate on internal rubric for report usefulness and factual consistency.
- Hallucinated citations under 2%.
- Free/local stack baseline established before paid model trials.

### Cost success
- 80%+ of production requests served by free/local models.
- Paid model usage limited to escalation paths with strict daily cap.

---

## 4) Free-first LLM strategy (core requirement)

## 4.1 Model tiers

Tier A: Local, zero per-call cost (default)
- Ollama models for routing, extraction, first-pass synthesis.
- Suggested starters:
  - qwen3:8b (general reasoning)
  - llama3.1:8b-instruct (stable baseline)
  - mistral:7b-instruct or mixtral variants if hardware permits

Tier B: Low-cost/free API fallback
- Hugging Face Inference Providers (free credits where available).
- Use for heavier summarization or long-context fallback when local quality drops.

Tier C: Paid escalation (only when needed)
- Paid premium model only for final synthesis on high-risk/high-divergence cases.
- Trigger strictly by confidence and contradiction thresholds.

## 4.2 Routing policy

- Default all tasks to Tier A.
- Escalate to Tier B if:
  - parser confidence below threshold,
  - extraction schema fails twice,
  - context length exceeds local model limit.
- Escalate to Tier C only if:
  - divergence score is high after two reconciliation loops,
  - user asks for high-stakes, publication-grade memo,
  - expected value of better output is higher than model cost.

## 4.3 Cost guardrails

- Per-request token budget by node.
- Daily global spend cap and per-user cap.
- Hard fail-safe: if cap reached, continue in free-only degraded mode with explicit warning.

---

## 5) Recommended implementation architecture

## 5.1 Tech stack
- Language: Python 3.11+
- API: FastAPI
- Orchestration: LangGraph + LangChain tool calling
- Storage:
  - PostgreSQL for structured state and run logs
  - Redis for cache and queue speedups
  - Object store/local files for raw ingested artifacts
- Analytics: Pandas, Polars (optional), NumPy
- Visualization: Plotly for RRG and dashboard charts
- Scheduling: APScheduler or Celery + Redis
- Observability: LangSmith tracing + OpenTelemetry + Prometheus/Grafana

## 5.2 Graph nodes (first release)
1. ingest_fundamentals
2. ingest_sentiment
3. ingest_corporate_spy
4. ingest_ipo_gmp
5. ingest_fii_dii
6. compute_rrg
7. normalize_and_validate
8. run_council
9. reconcile_divergence
10. synthesize_report
11. score_confidence
12. finalize_output

## 5.3 State schema
Use a strict typed schema with validation on every node transition.
Required top-level fields:
- run_id
- user_query
- ticker_universe
- market_data
- alt_data
- sentiment
- rotation
- council_outputs
- contradictions
- confidence
- citations
- report
- audit_log

---

## 6) Build phases Claude should execute

## Phase 0: Foundation and repo scaffolding (Day 1-2)
Deliverables:
- Monorepo layout with services/api, services/worker, libs/core, libs/agents, libs/connectors, infra.
- Environment handling, logging, config templates.
- Docker compose for postgres, redis, api, worker.
- CI pipeline with lint, type checks, unit tests.

Exit criteria:
- One command local boot and health check endpoint working.

## Phase 1: Data connector MVPs (Week 1)
Deliverables:
- Connectors for:
  - Yahoo/yfinance fallback chain
  - mftool AMFI
  - news sentiment feed ingestion
  - pnsea corporate data
- Retry/backoff, anti-rate-limit controls, cache TTL rules.

Exit criteria:
- Connectors return normalized payloads and pass schema validation tests.

## Phase 2: Feature engineering and indicators (Week 2)
Deliverables:
- RRG engine with corrected momentum math (shifted rs ratio roc).
- FII/DII flow strength index and streak metrics.
- IPO disagreement score.
- Divergence detector for conflicting signals.

Exit criteria:
- Reproducible feature tables for at least 50 tickers.

## Phase 3: LangGraph orchestration and shared state machine (Week 3)
Deliverables:
- Supervisor graph with deterministic edge logic.
- Node-level contracts and guardrails.
- Resume/retry from partial state.

Exit criteria:
- End-to-end graph run succeeds on sample portfolios without manual intervention.

## Phase 4: Council reasoning layer (Week 4)
Deliverables:
- Five role prompts (Contrarian, First Principles, Expansionist, Outsider, Synthesizer).
- Structured output parser for stance vectors and rationale.
- Consensus variance and loopback reconciliation.

Exit criteria:
- Stable consensus loop with max iteration cap and no infinite cycles.

## Phase 5: Report generation and auditability (Week 5)
Deliverables:
- Final report with sections from your source design.
- Citation map tied to raw evidence objects.
- Confidence labeling and speculative flag rules.

Exit criteria:
- Human reviewer can trace each major claim to source data.

## Phase 6: Free vs paid model evaluation harness (Week 6)
Deliverables:
- Benchmark set of 100 realistic analysis prompts.
- Side-by-side runs: local-only vs local+HF vs paid escalation.
- Scoring rubric:
  - factual grounding
  - contradiction handling
  - actionability
  - latency
  - cost per report

Exit criteria:
- Quantified decision document on whether paid models add enough value.

## Phase 7: Dashboard and operations (Week 7)
Deliverables:
- Web dashboard for run traces, confidence trends, and allocation outputs.
- Alerting for connector failures, schema drift, and budget cap breaches.

Exit criteria:
- Operator can monitor and debug runs without reading raw logs.

## Phase 8: Hardening and release (Week 8)
Deliverables:
- Load tests, chaos tests, fallback validation.
- Security checks, secrets management, role-based access.
- Release candidate and runbook.

Exit criteria:
- Production-ready with rollback plan.

---

## 7) Repository structure to implement

- services/api
- services/worker
- services/dashboard
- libs/agents
- libs/connectors
- libs/features
- libs/schemas
- libs/reporting
- libs/eval
- infra/docker
- infra/k8s (optional later)
- tests/unit
- tests/integration
- tests/e2e
- docs

---

## 8) Data quality and reliability rules

- Every connector must expose:
  - freshness timestamp
  - source name
  - confidence field
  - error class
- Reject downstream computation when critical fields are stale or missing.
- Implement source fallback chain by module.
- Cache policy examples:
  - NAV and slow-changing metadata: 24h to 7d
  - intraday market data: 1m to 15m
  - sentiment snapshots: 5m to 30m

---

## 9) Evaluation framework to justify model spending

## 9.1 Offline benchmark
- Curate scenarios:
  - bullish trend continuation
  - bear reversal traps
  - conflicting insider vs flow signals
  - hype IPO with weak institutional demand
- Blind-grade outputs with a fixed rubric.

## 9.2 Online shadow mode
- Run local/free and paid synthesis in parallel for a subset.
- Compare deltas in confidence calibration and recommendation stability.

## 9.3 Spend decision rule
Move to paid model only if all are true:
- Quality lift >= 15% on rubric.
- False claim rate reduced materially.
- Incremental cost per useful report within budget target.

---

## 10) Risks and mitigations

- Data source outage:
  - Mitigation: multi-source fallback + cached stale-while-revalidate mode.
- Hallucinated synthesis:
  - Mitigation: citation-required templates and claim checker node.
- Infinite consensus loops:
  - Mitigation: strict max iterations + forced synthesis fallback.
- Budget overrun:
  - Mitigation: hard spend caps and automatic downgrade to free tier.

---

## 11) Compliance and ethics notes

- This is research and decision-support software, not guaranteed financial advice.
- Maintain clear disclaimer in UI/report output.
- Keep audit logs for each recommendation path.

---

## 12) Immediate next actions for Claude (copy this into Claude)

1. Scaffold the repository and baseline services exactly as in Section 7.
2. Implement typed schemas and validation middleware first.
3. Build connectors with retries, caching, and fallback before any LLM logic.
4. Implement feature pipeline (RRG corrected formula, FII/DII metrics, GMP disagreement).
5. Build LangGraph supervisor and state transitions.
6. Add council personas with structured JSON outputs only.
7. Add report generator with evidence-linked citations.
8. Add free-first model router (Ollama default, HF fallback, paid escalation).
9. Build benchmark harness and run local/free baseline first.
10. Produce a go/no-go report for paid model adoption.

---

## 13) Definition of done

Project is done when:
- End-to-end runs are stable,
- Outputs are evidence-linked and measurable,
- Free/local baseline is strong,
- Paid model decision is based on benchmark evidence, not intuition.
