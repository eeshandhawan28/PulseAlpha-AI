# PulseAlpha AI — Frontend UI Design Spec

**Date:** 2026-05-29  
**Status:** Approved

---

## Goal

Build a Next.js dashboard that connects the existing FastAPI backend (`POST /analyze`, `GET /history`) to a browser UI. Users can run analyses against Indian market tickers and browse past runs — without touching the terminal.

---

## Architecture

```
services/frontend/          ← New Next.js 14 app (port 3000)
  app/
    page.tsx                ← Redirects to /analyze
    analyze/page.tsx        ← Main analysis screen
    history/page.tsx        ← Past runs browser
  components/
    Sidebar.tsx             ← Persistent nav + accuracy badge
    StepTracker.tsx         ← Pipeline progress (SSE-driven)
    MetricCards.tsx         ← Stance / Confidence / Divergence / RRG
    ReportViewer.tsx        ← Streaming markdown renderer
    HistoryTable.tsx        ← Searchable + filterable table
  lib/
    api.ts                  ← Typed wrappers for all API calls
    stream.ts               ← SSE EventSource consumer hook

services/api/api/
  routes/analyze.py         ← Adds GET /analyze/stream SSE endpoint
  routes/history.py         ← New: GET /history
  routes/analyze.py         ← POST /analyze now saves run to history
  main.py                   ← CORS middleware for localhost:3000
  history_store.py          ← New: append/read history.json
```

The frontend is a separate process (`npm run dev` on port 3000). It talks to FastAPI on port 8000. No auth — local use only.

---

## Screen 1 — Analyze

**URL:** `/analyze` (also `/analyze?run_id=<id>` to view a past run from History)

**Layout:** Sidebar (left, 148px) + main content (flex-1).

**Main content regions:**
1. **Query bar** — text input (ticker + question) + Run button. Button becomes a pulsing "Analyzing…" state during the SSE stream.
2. **Pipeline steps panel** (left strip, 155px wide) — six steps rendered as icon + label. Icons cycle through: pending (grey circle) → active (blue spinner) → done (green check).
3. **Metric cards** — 4-up grid: Stance, Confidence, Divergence, RRG Quadrant. Populated progressively as the `metrics` SSE event arrives.
4. **Report viewer** — markdown rendered with `react-markdown`. Text streams in character by character as `chunk` SSE events arrive. Displays a blinking cursor while streaming.

**Pipeline steps (in order):**
1. Market data
2. RRG features
3. FII / DII flows
4. Divergence score
5. Council (n / 5)
6. Report

**Run flow:**
1. User types query, clicks Run.
2. Frontend opens `EventSource` to `GET /analyze/stream?ticker=...&query=...`.
3. Backend runs the LangGraph pipeline, emitting SSE events at each node boundary.
4. Frontend updates steps, metrics, and report in real time.
5. On `done` event, Run button resets. Run is already saved to history server-side.

---

## Screen 2 — History

**URL:** `/history`

**Layout:** Same sidebar + main content.

**Main content:**
- Toolbar: search input (filters ticker + query text) + stance filter dropdown (All / Bullish / Bearish).
- Column header row.
- Scrollable list of past runs. Each row: Ticker | Query (truncated) | Stance badge | Confidence | Date.
- Clicking a row navigates to `/analyze?run_id=...` and re-displays that run's report (fetched from history, no re-run).

---

## Sidebar

Persistent across all pages. Contains:
- Logo: ⚡ PULSEALPHA
- Nav items: Analyze, History (active state highlighted)
- Divider
- Footer accuracy badge: "Model accuracy · 68%" pulled from `GET /history/stats` (last backtest hit rate stored in history.json; falls back to "—" if no backtest run yet).

---

## Backend Additions

### `GET /analyze/stream`

New SSE endpoint alongside the existing `POST /analyze`.

**Query params:** `ticker: str`, `query: str`

**Events emitted:**

```
data: {"type": "step", "node": "ingest", "status": "active"}
data: {"type": "step", "node": "ingest", "status": "done"}
data: {"type": "step", "node": "features", "status": "active"}
data: {"type": "step", "node": "features", "status": "done"}
data: {"type": "step", "node": "divergence", "status": "active"}
data: {"type": "step", "node": "divergence", "status": "done"}
data: {"type": "step", "node": "validate", "status": "done"}
data: {"type": "metrics", "stance": "bullish", "confidence": 0.82, "divergence_score": 0.23, "rrg_quadrant": "Leading"}
data: {"type": "step", "node": "council", "status": "active", "progress": "3/5"}
data: {"type": "step", "node": "council", "status": "done"}
data: {"type": "step", "node": "report", "status": "active"}
data: {"type": "chunk", "text": "## Executive Summary\n\nReliance Industries..."}
data: {"type": "chunk", "text": " shows strong momentum..."}
data: {"type": "done", "run_id": "abc123"}
```

Implementation: calls each node function directly (same as `BacktestRunner`), yielding events between steps. Report text is not natively streamed by the LLM call — the full report string is split on word boundaries into ~50-char chunks and yielded sequentially to simulate streaming.

### `GET /history`

Returns list of saved runs from `history.json`, newest first.

```json
[
  {
    "run_id": "abc123",
    "ticker": "RELIANCE.NS",
    "query": "What's the Q3 2025 outlook?",
    "stance": "bullish",
    "confidence": 0.82,
    "divergence_score": 0.23,
    "rrg_quadrant": "Leading",
    "report": "## Executive Summary\n...",
    "created_at": "2026-05-29T10:23:00Z"
  }
]
```

### `GET /history/stats`

Returns `{"hit_rate_30d": 0.68}` from last backtest result file, or `null` if none exists.

### `POST /analyze` (modified)

Existing endpoint unchanged in behaviour. After completing, appends the run to `history.json` via `history_store.append_run()`.

### CORS

`CORSMiddleware` added in `main.py` allowing `http://localhost:3000`.

### `services/api/api/history_store.py`

Thin wrapper: `append_run(run: dict)` and `list_runs() -> list[dict]` operating on a `history.json` file in the project root. File is created on first write.

---

## Tech Stack

| Layer | Choice |
|-------|--------|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript |
| Styling | Tailwind CSS |
| Components | shadcn/ui |
| Markdown | react-markdown + remark-gfm |
| SSE | Native `EventSource` API via custom React hook |
| Package manager | npm |

---

## What Is NOT Included

- Authentication — local use only
- Backtest UI screen — CLI only (`python -m worker.backtest`)
- Candlestick / price charts
- Mobile responsive layout — desktop-first
- Docker containerisation of the frontend (Phase 7+ concern)

---

## File Map (new files)

```
services/frontend/
  package.json
  tsconfig.json
  tailwind.config.ts
  next.config.ts
  app/
    layout.tsx
    page.tsx                    (redirect → /analyze)
    analyze/page.tsx
    history/page.tsx
  components/
    Sidebar.tsx
    StepTracker.tsx
    MetricCards.tsx
    ReportViewer.tsx
    HistoryTable.tsx
  lib/
    api.ts
    stream.ts

services/api/api/
  history_store.py              (new)
  routes/history.py             (new)
  routes/analyze.py             (modified — add /stream + save to history)
  main.py                       (modified — CORS + history router)
```
