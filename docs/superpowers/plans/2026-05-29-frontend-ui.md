# PulseAlpha Frontend UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Next.js 14 dashboard with Analyze (SSE streaming) and History screens, backed by small FastAPI additions (history store, SSE endpoint, CORS).

**Architecture:** Next.js 14 App Router in `services/frontend/` on port 3000, proxying to FastAPI on port 8000. FastAPI gains a `GET /analyze/stream` SSE endpoint that runs nodes directly (like BacktestRunner) and emits step/metrics/chunk/done events. Past runs are saved to `history.json` in the project root. Sidebar shows model accuracy from the last backtest result file.

**Tech Stack:** Next.js 14, TypeScript, Tailwind CSS, shadcn/ui, react-markdown, remark-gfm, FastAPI StreamingResponse (SSE), Python json file store.

---

## File Map

**New backend files:**
- `services/api/api/history_store.py` — append/read `history.json`
- `services/api/api/routes/history.py` — `GET /history`, `GET /history/stats`

**Modified backend files:**
- `services/api/api/routes/analyze.py` — add `GET /analyze/stream` + save run to history after `POST /analyze`
- `services/api/api/main.py` — CORS middleware + history router

**New frontend files:**
- `services/frontend/package.json`
- `services/frontend/tsconfig.json`
- `services/frontend/tailwind.config.ts`
- `services/frontend/next.config.ts`
- `services/frontend/app/layout.tsx`
- `services/frontend/app/page.tsx`
- `services/frontend/app/analyze/page.tsx`
- `services/frontend/app/history/page.tsx`
- `services/frontend/components/Sidebar.tsx`
- `services/frontend/components/StepTracker.tsx`
- `services/frontend/components/MetricCards.tsx`
- `services/frontend/components/ReportViewer.tsx`
- `services/frontend/components/HistoryTable.tsx`
- `services/frontend/lib/api.ts`
- `services/frontend/lib/stream.ts`

---

## Task 1: Backend — history_store + /history routes + CORS

**Files:**
- Create: `services/api/api/history_store.py`
- Create: `services/api/api/routes/history.py`
- Modify: `services/api/api/main.py`
- Test: `tests/unit/api/test_history_store.py`

- [ ] **Step 1: Create test file**

```bash
mkdir -p "/Users/eeshandhawan/Desktop/PulseAlpha AI/tests/unit/api"
touch "/Users/eeshandhawan/Desktop/PulseAlpha AI/tests/unit/api/__init__.py"
```

- [ ] **Step 2: Write failing tests**

`tests/unit/api/test_history_store.py`:
```python
import json
import pytest
from pathlib import Path
from api.history_store import HistoryStore


@pytest.fixture
def store(tmp_path):
    return HistoryStore(history_file=tmp_path / "history.json")


def test_list_runs_empty(store):
    assert store.list_runs() == []


def test_append_and_list(store):
    run = {
        "run_id": "abc123",
        "ticker": "RELIANCE.NS",
        "query": "Q3 outlook?",
        "stance": "bullish",
        "confidence": 0.82,
        "divergence_score": 0.23,
        "rrg_quadrant": "Leading",
        "report": "## Summary\nBullish.",
        "created_at": "2026-05-29T10:00:00Z",
    }
    store.append_run(run)
    runs = store.list_runs()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "abc123"


def test_list_runs_newest_first(store):
    store.append_run({"run_id": "first", "created_at": "2026-05-01T00:00:00Z"})
    store.append_run({"run_id": "second", "created_at": "2026-05-29T00:00:00Z"})
    runs = store.list_runs()
    assert runs[0]["run_id"] == "second"


def test_get_run_by_id(store):
    store.append_run({"run_id": "xyz", "ticker": "TCS.NS"})
    run = store.get_run("xyz")
    assert run is not None
    assert run["ticker"] == "TCS.NS"


def test_get_run_missing_returns_none(store):
    assert store.get_run("nonexistent") is None
```

- [ ] **Step 3: Run to confirm failure**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run pytest tests/unit/api/test_history_store.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError: No module named 'api.history_store'`

- [ ] **Step 4: Implement `services/api/api/history_store.py`**

```python
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path(__file__).parents[3] / "history.json"


class HistoryStore:
    def __init__(self, history_file: Path = _DEFAULT_PATH) -> None:
        self._path = history_file

    def _load(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        try:
            return json.loads(self._path.read_text())  # type: ignore[no-any-return]
        except (json.JSONDecodeError, OSError):
            logger.warning("history.json corrupt or unreadable, starting fresh")
            return []

    def _save(self, runs: list[dict[str, Any]]) -> None:
        self._path.write_text(json.dumps(runs, indent=2, default=str))

    def append_run(self, run: dict[str, Any]) -> None:
        runs = self._load()
        runs.append(run)
        self._save(runs)

    def list_runs(self) -> list[dict[str, Any]]:
        runs = self._load()
        return sorted(runs, key=lambda r: r.get("created_at", ""), reverse=True)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        for run in self._load():
            if run.get("run_id") == run_id:
                return run
        return None


# Module-level singleton used by FastAPI routes
_store = HistoryStore()


def append_run(run: dict[str, Any]) -> None:
    _store.append_run(run)


def list_runs() -> list[dict[str, Any]]:
    return _store.list_runs()


def get_run(run_id: str) -> dict[str, Any] | None:
    return _store.get_run(run_id)
```

- [ ] **Step 5: Run tests**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run pytest tests/unit/api/test_history_store.py -v
```
Expected: All 5 PASS.

- [ ] **Step 6: Create `services/api/api/routes/history.py`**

```python
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

import api.history_store as history_store

logger = logging.getLogger(__name__)
router = APIRouter()

_BACKTEST_DIR = Path(__file__).parents[4] / "backtest_results"


@router.get("/history")
async def list_history() -> list[dict[str, Any]]:
    return history_store.list_runs()


@router.get("/history/{run_id}")
async def get_history_run(run_id: str) -> dict[str, Any]:
    run = history_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/history/stats")
async def history_stats() -> dict[str, Any]:
    """Return hit_rate_30d from the most recent backtest result file, or null."""
    if not _BACKTEST_DIR.exists():
        return {"hit_rate_30d": None}
    files = sorted(_BACKTEST_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        return {"hit_rate_30d": None}
    try:
        data = json.loads(files[0].read_text())
        hit_rate = data.get("metrics", {}).get("hit_rate_30d")
        return {"hit_rate_30d": hit_rate}
    except (json.JSONDecodeError, OSError):
        return {"hit_rate_30d": None}
```

- [ ] **Step 7: Add CORS and history router to `services/api/api/main.py`**

Read current `main.py` first, then replace:

```python
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env into os.environ so worker LLM code can use os.getenv()
load_dotenv(Path(__file__).parents[3] / ".env", override=False)

from api.config import get_settings
from api.routes.analyze import router as analyze_router
from api.routes.backtest import router as backtest_router
from api.routes.health import router as health_router
from api.routes.history import router as history_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    s = get_settings()
    logging.basicConfig(level=getattr(logging, s.log_level))
    logger.info("PulseAlpha API starting — env=%s", s.app_env)
    yield
    logger.info("PulseAlpha API shutdown")


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="PulseAlpha AI", version=s.version, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(analyze_router)
    app.include_router(backtest_router)
    app.include_router(history_router)
    return app


app = create_app()
```

- [ ] **Step 8: Commit**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && git add services/api/api/history_store.py services/api/api/routes/history.py services/api/api/main.py tests/unit/api/ && git commit -m "feat(api): history store, /history routes, CORS for localhost:3000"
```

---

## Task 2: Backend — SSE streaming endpoint + save runs to history

**Files:**
- Modify: `services/api/api/routes/analyze.py`

- [ ] **Step 1: Replace `services/api/api/routes/analyze.py` with the version below**

This adds `GET /analyze/stream` (SSE) and modifies `POST /analyze` to save runs to history. Read the current file first to note its contents, then write:

```python
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from schemas.state import AnalysisState

import api.history_store as history_store

logger = logging.getLogger(__name__)
router = APIRouter()


class AnalyzeRequest(BaseModel):
    ticker_universe: list[str]
    user_query: str = "Analyze the provided tickers"


def _rrg_quadrant(state: AnalysisState, ticker: str) -> str:
    for pt in state.rotation.get("points", []):
        if pt.get("ticker") == ticker:
            rs = float(pt.get("rs_ratio", 0.0))
            rm = float(pt.get("rs_momentum", 0.0))
            if rs > 100 and rm > 100:
                return "Leading"
            elif rs > 100:
                return "Weakening"
            elif rm > 100:
                return "Improving"
            return "Lagging"
    return "—"


def _majority_stance(state: AnalysisState) -> str:
    if not state.council_outputs:
        return "neutral"
    from worker.council.variance import majority_stance
    return majority_stance(state.council_outputs)


def _split_chunks(text: str, max_chars: int = 50) -> list[str]:
    """Split text on word boundaries into chunks of ~max_chars each."""
    words = text.split()
    chunks: list[str] = []
    current = ""
    for word in words:
        candidate = current + " " + word if current else word
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def _run_stream(ticker: str, query: str) -> AsyncIterator[str]:
    from worker.nodes.council import run_council
    from worker.nodes.divergence import compute_divergence_node
    from worker.nodes.features import compute_features
    from worker.nodes.ingest import ingest_all_data
    from worker.nodes.report import generate_report
    from worker.nodes.validate import normalize_and_validate

    try:
        state = AnalysisState(user_query=query, ticker_universe=[ticker])
    except ValueError as exc:
        yield _sse({"type": "error", "message": str(exc)})
        return

    # ingest
    yield _sse({"type": "step", "node": "ingest", "status": "active"})
    state = await ingest_all_data(state)
    yield _sse({"type": "step", "node": "ingest", "status": "done"})

    # features
    yield _sse({"type": "step", "node": "features", "status": "active"})
    state = await compute_features(state)
    yield _sse({"type": "step", "node": "features", "status": "done"})

    # divergence + validate
    yield _sse({"type": "step", "node": "divergence", "status": "active"})
    state = await compute_divergence_node(state)
    state = await normalize_and_validate(state)
    yield _sse({"type": "step", "node": "divergence", "status": "done"})

    # council
    yield _sse({"type": "step", "node": "council", "status": "active"})
    state = await run_council(state)
    yield _sse({"type": "step", "node": "council", "status": "done"})

    # emit metrics after council
    stance = _majority_stance(state)
    quadrant = _rrg_quadrant(state, ticker)
    yield _sse({
        "type": "metrics",
        "stance": stance,
        "confidence": round(state.confidence, 4),
        "divergence_score": round(state.divergence_score, 4),
        "rrg_quadrant": quadrant,
    })

    # report
    yield _sse({"type": "step", "node": "report", "status": "active"})
    state = await generate_report(state)
    yield _sse({"type": "step", "node": "report", "status": "done"})

    # stream report chunks
    report_text = state.report or ""
    for chunk in _split_chunks(report_text, max_chars=60):
        yield _sse({"type": "chunk", "text": chunk + " "})

    # save to history
    history_store.append_run({
        "run_id": state.run_id,
        "ticker": ticker,
        "query": query,
        "stance": stance,
        "confidence": round(state.confidence, 4),
        "divergence_score": round(state.divergence_score, 4),
        "rrg_quadrant": quadrant,
        "report": report_text,
        "created_at": datetime.now(UTC).isoformat(),
    })

    yield _sse({"type": "done", "run_id": state.run_id})


@router.get("/analyze/stream")
async def analyze_stream(ticker: str, query: str = "Analyze this ticker") -> StreamingResponse:
    """SSE endpoint — emits step/metrics/chunk/done events as pipeline runs."""
    return StreamingResponse(
        _run_stream(ticker, query),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/analyze", response_model=dict[str, object])
async def analyze(request: AnalyzeRequest) -> dict[str, object]:
    """Run the full analysis graph for the given ticker universe."""
    from worker.graph import run_analysis

    try:
        state = AnalysisState(
            user_query=request.user_query,
            ticker_universe=request.ticker_universe,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        final_state = await run_analysis(state)
    except Exception as exc:
        logger.exception("Graph run failed for tickers=%s", request.ticker_universe)
        raise HTTPException(status_code=500, detail="Analysis graph failed") from exc

    # Save to history
    ticker = request.ticker_universe[0]
    stance = _majority_stance(final_state)
    history_store.append_run({
        "run_id": final_state.run_id,
        "ticker": ticker,
        "query": request.user_query,
        "stance": stance,
        "confidence": round(final_state.confidence, 4),
        "divergence_score": round(final_state.divergence_score, 4),
        "rrg_quadrant": _rrg_quadrant(final_state, ticker),
        "report": final_state.report,
        "created_at": datetime.now(UTC).isoformat(),
    })

    return final_state.model_dump(mode="json")  # type: ignore[no-any-return]
```

- [ ] **Step 2: Verify the API starts cleanly**

Kill any running server first, then start fresh:
```bash
lsof -ti:8000 | xargs kill -9 2>/dev/null; true
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run --package api uvicorn api.main:app --host 0.0.0.0 --port 8000 &
sleep 3
curl -s http://localhost:8000/health
```
Expected: `{"status":"ok","version":"0.1.0","environment":"development"}`

- [ ] **Step 3: Smoke-test the /history endpoint**

```bash
curl -s http://localhost:8000/history | python3 -m json.tool
```
Expected: `[]` (empty array, no error)

- [ ] **Step 4: Commit**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && git add services/api/api/routes/analyze.py && git commit -m "feat(api): SSE /analyze/stream endpoint + save runs to history"
```

---

## Task 3: Frontend — Next.js scaffold

**Files:**
- Create: `services/frontend/` — entire Next.js app scaffold

- [ ] **Step 1: Scaffold Next.js app**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI/services"
npx create-next-app@14 frontend --typescript --tailwind --app --no-src-dir --import-alias "@/*" --no-git --yes
```
Expected: `services/frontend/` created with `app/`, `components/`, `public/`, `package.json`, `tsconfig.json`, `tailwind.config.ts`, `next.config.ts`.

- [ ] **Step 2: Install additional dependencies**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI/services/frontend"
npm install react-markdown remark-gfm
```

- [ ] **Step 3: Install shadcn/ui**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI/services/frontend"
npx shadcn@latest init -d
npx shadcn@latest add badge input button
```
Expected: `components/ui/` created with `badge.tsx`, `input.tsx`, `button.tsx`.

- [ ] **Step 4: Replace `services/frontend/next.config.ts` with**

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  },
};

export default nextConfig;
```

- [ ] **Step 5: Create `.env.local`**

```bash
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > "/Users/eeshandhawan/Desktop/PulseAlpha AI/services/frontend/.env.local"
```

- [ ] **Step 6: Replace `services/frontend/app/globals.css` with**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --background: #0a0e1a;
  --foreground: #e2e8f0;
}

body {
  background: var(--background);
  color: var(--foreground);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
```

- [ ] **Step 7: Replace `services/frontend/tailwind.config.ts` with**

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0a0e1a",
        surface: "#0f1629",
        border: "#1e2d4a",
        muted: "#64748b",
        "muted-foreground": "#94a3b8",
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 8: Replace `services/frontend/app/layout.tsx` with**

```typescript
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PulseAlpha AI",
  description: "Indian Market Intelligence Engine",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-background text-foreground">{children}</body>
    </html>
  );
}
```

- [ ] **Step 9: Replace `services/frontend/app/page.tsx` with**

```typescript
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/analyze");
}
```

- [ ] **Step 10: Verify the app compiles**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI/services/frontend" && npm run build 2>&1 | tail -10
```
Expected: `✓ Compiled successfully` (or similar Next.js build success message).

- [ ] **Step 11: Commit**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && git add services/frontend/ && git commit -m "feat(frontend): Next.js 14 scaffold with Tailwind + shadcn/ui"
```

---

## Task 4: Frontend — lib/api.ts + lib/stream.ts

**Files:**
- Create: `services/frontend/lib/api.ts`
- Create: `services/frontend/lib/stream.ts`

- [ ] **Step 1: Create `services/frontend/lib/api.ts`**

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface HistoryRun {
  run_id: string;
  ticker: string;
  query: string;
  stance: string;
  confidence: number;
  divergence_score: number;
  rrg_quadrant: string;
  report: string;
  created_at: string;
}

export interface HistoryStats {
  hit_rate_30d: number | null;
}

export async function fetchHistory(): Promise<HistoryRun[]> {
  const res = await fetch(`${API_URL}/history`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchHistoryRun(runId: string): Promise<HistoryRun | null> {
  const res = await fetch(`${API_URL}/history/${runId}`, { cache: "no-store" });
  if (!res.ok) return null;
  return res.json();
}

export async function fetchHistoryStats(): Promise<HistoryStats> {
  const res = await fetch(`${API_URL}/history/stats`, { cache: "no-store" });
  if (!res.ok) return { hit_rate_30d: null };
  return res.json();
}

export function getStreamUrl(ticker: string, query: string): string {
  const params = new URLSearchParams({ ticker, query });
  return `${API_URL}/analyze/stream?${params.toString()}`;
}
```

- [ ] **Step 2: Create `services/frontend/lib/stream.ts`**

```typescript
"use client";

import { useCallback, useRef, useState } from "react";
import { getStreamUrl } from "./api";

export type StepStatus = "pending" | "active" | "done";

export interface Step {
  node: string;
  label: string;
  status: StepStatus;
}

export interface Metrics {
  stance: string;
  confidence: number;
  divergence_score: number;
  rrg_quadrant: string;
}

const INITIAL_STEPS: Step[] = [
  { node: "ingest", label: "Market data", status: "pending" },
  { node: "features", label: "RRG features", status: "pending" },
  { node: "divergence", label: "Divergence score", status: "pending" },
  { node: "council", label: "Council", status: "pending" },
  { node: "report", label: "Report", status: "pending" },
];

export function useAnalysisStream() {
  const [steps, setSteps] = useState<Step[]>(INITIAL_STEPS);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [reportText, setReportText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const start = useCallback((ticker: string, query: string) => {
    esRef.current?.close();
    setSteps(INITIAL_STEPS);
    setMetrics(null);
    setReportText("");
    setRunId(null);
    setError(null);
    setIsStreaming(true);

    const url = getStreamUrl(ticker.trim(), query.trim());
    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = (e: MessageEvent) => {
      try {
        const event = JSON.parse(e.data as string);
        if (event.type === "step") {
          setSteps((prev) =>
            prev.map((s) =>
              s.node === event.node ? { ...s, status: event.status as StepStatus } : s
            )
          );
        } else if (event.type === "metrics") {
          setMetrics({
            stance: event.stance,
            confidence: event.confidence,
            divergence_score: event.divergence_score,
            rrg_quadrant: event.rrg_quadrant,
          });
        } else if (event.type === "chunk") {
          setReportText((prev) => prev + (event.text as string));
        } else if (event.type === "error") {
          setError(event.message as string);
          setIsStreaming(false);
          es.close();
        } else if (event.type === "done") {
          setRunId(event.run_id as string);
          setIsStreaming(false);
          es.close();
        }
      } catch {
        // malformed event — skip
      }
    };

    es.onerror = () => {
      setError("Connection to analysis server lost. Is the API running on port 8000?");
      setIsStreaming(false);
      es.close();
    };
  }, []);

  const reset = useCallback(() => {
    esRef.current?.close();
    setSteps(INITIAL_STEPS);
    setMetrics(null);
    setReportText("");
    setRunId(null);
    setError(null);
    setIsStreaming(false);
  }, []);

  return { steps, metrics, reportText, isStreaming, runId, error, start, reset };
}
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && git add services/frontend/lib/ && git commit -m "feat(frontend): api.ts typed wrappers and useAnalysisStream SSE hook"
```

---

## Task 5: Frontend — Sidebar component

**Files:**
- Create: `services/frontend/components/Sidebar.tsx`

- [ ] **Step 1: Create `services/frontend/components/Sidebar.tsx`**

```typescript
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchHistoryStats } from "@/lib/api";

const NAV = [
  { href: "/analyze", label: "Analyze", icon: "📊" },
  { href: "/history", label: "History", icon: "📋" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [hitRate, setHitRate] = useState<number | null>(null);

  useEffect(() => {
    fetchHistoryStats().then((s) => setHitRate(s.hit_rate_30d));
  }, []);

  return (
    <aside className="w-36 min-w-36 flex flex-col gap-1 border-r border-border bg-[#080d1c] px-2 py-3">
      <div className="px-1 pb-3 border-b border-border mb-1">
        <span className="text-xs font-extrabold tracking-wider text-indigo-400">
          ⚡ PULSEALPHA
        </span>
      </div>

      {NAV.map((item) => {
        const active = pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-xs transition-colors ${
              active
                ? "bg-blue-900 text-blue-300 font-semibold"
                : "text-muted hover:text-muted-foreground hover:bg-surface"
            }`}
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </Link>
        );
      })}

      <div className="mt-auto pt-3 border-t border-border">
        <div className="flex justify-between text-[10px] text-muted">
          <span>Model accuracy</span>
          <span className="text-green-400 font-bold">
            {hitRate !== null ? `${Math.round(hitRate * 100)}%` : "—"}
          </span>
        </div>
        <div className="flex justify-between text-[10px] text-muted mt-0.5">
          <span>30-day hit rate</span>
          <span className="text-[10px] text-muted">last backtest</span>
        </div>
      </div>
    </aside>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && git add services/frontend/components/Sidebar.tsx && git commit -m "feat(frontend): Sidebar with nav links and model accuracy footer"
```

---

## Task 6: Frontend — StepTracker + MetricCards + ReportViewer

**Files:**
- Create: `services/frontend/components/StepTracker.tsx`
- Create: `services/frontend/components/MetricCards.tsx`
- Create: `services/frontend/components/ReportViewer.tsx`

- [ ] **Step 1: Create `services/frontend/components/StepTracker.tsx`**

```typescript
import { Step, StepStatus } from "@/lib/stream";

function StepIcon({ status }: { status: StepStatus }) {
  if (status === "done")
    return (
      <span className="inline-flex w-4 h-4 rounded-full items-center justify-center bg-green-900 text-green-400 text-[9px]">
        ✓
      </span>
    );
  if (status === "active")
    return (
      <span className="inline-flex w-4 h-4 rounded-full items-center justify-center bg-blue-900 text-blue-400 text-[9px] animate-pulse">
        ●
      </span>
    );
  return (
    <span className="inline-flex w-4 h-4 rounded-full items-center justify-center bg-border text-muted text-[9px]">
      ○
    </span>
  );
}

export default function StepTracker({ steps }: { steps: Step[] }) {
  return (
    <div className="w-40 min-w-40 border-r border-border px-3 py-3 flex flex-col gap-1">
      <p className="text-[10px] uppercase tracking-widest text-muted mb-2">Pipeline</p>
      {steps.map((step) => (
        <div key={step.node} className="flex items-center gap-2">
          <StepIcon status={step.status} />
          <span
            className={`text-[11px] ${
              step.status === "active"
                ? "text-blue-300 font-semibold"
                : step.status === "done"
                ? "text-muted-foreground"
                : "text-muted"
            }`}
          >
            {step.label}
          </span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create `services/frontend/components/MetricCards.tsx`**

```typescript
import { Metrics } from "@/lib/stream";

interface Card {
  label: string;
  value: string;
  color: string;
}

function stanceColor(stance: string): string {
  if (stance === "bullish") return "text-green-400";
  if (stance === "bearish") return "text-red-400";
  return "text-yellow-400";
}

function toCards(metrics: Metrics): Card[] {
  return [
    {
      label: "Stance",
      value: metrics.stance.toUpperCase(),
      color: stanceColor(metrics.stance),
    },
    {
      label: "Confidence",
      value: `${Math.round(metrics.confidence * 100)}%`,
      color: "text-blue-400",
    },
    {
      label: "Divergence",
      value: metrics.divergence_score.toFixed(2),
      color: "text-purple-400",
    },
    {
      label: "RRG Quad",
      value: metrics.rrg_quadrant,
      color: "text-yellow-400",
    },
  ];
}

function EmptyCard({ label }: { label: string }) {
  return (
    <div className="bg-surface border border-border rounded-lg px-3 py-2">
      <p className="text-[10px] uppercase tracking-wide text-muted">{label}</p>
      <div className="mt-1 h-5 w-12 bg-border rounded animate-pulse" />
    </div>
  );
}

const EMPTY_LABELS = ["Stance", "Confidence", "Divergence", "RRG Quad"];

export default function MetricCards({ metrics }: { metrics: Metrics | null }) {
  if (!metrics) {
    return (
      <div className="grid grid-cols-4 gap-2">
        {EMPTY_LABELS.map((l) => (
          <EmptyCard key={l} label={l} />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-4 gap-2">
      {toCards(metrics).map((card) => (
        <div key={card.label} className="bg-surface border border-border rounded-lg px-3 py-2">
          <p className="text-[10px] uppercase tracking-wide text-muted">{card.label}</p>
          <p className={`text-lg font-bold mt-0.5 ${card.color}`}>{card.value}</p>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Create `services/frontend/components/ReportViewer.tsx`**

```typescript
"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  ticker: string;
  stance: string | null;
  reportText: string;
  isStreaming: boolean;
}

function stanceBadgeClass(stance: string | null): string {
  if (stance === "bullish") return "bg-green-900 text-green-400";
  if (stance === "bearish") return "bg-red-900 text-red-400";
  return "bg-yellow-900 text-yellow-400";
}

export default function ReportViewer({ ticker, stance, reportText, isStreaming }: Props) {
  return (
    <div className="flex-1 bg-surface border border-border rounded-lg p-4 overflow-auto min-h-0">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-bold text-foreground">
          {ticker ? `${ticker} — Analysis Report` : "Analysis Report"}
        </span>
        {stance && (
          <span
            className={`text-[10px] font-bold px-2 py-0.5 rounded ${stanceBadgeClass(stance)}`}
          >
            {stance.toUpperCase()}
          </span>
        )}
      </div>

      {!reportText && !isStreaming && (
        <p className="text-xs text-muted">Enter a ticker and question above, then click Run.</p>
      )}

      {!reportText && isStreaming && (
        <div className="space-y-2">
          {[95, 80, 88, 65, 75].map((w, i) => (
            <div
              key={i}
              className="h-3 bg-border rounded animate-pulse"
              style={{ width: `${w}%` }}
            />
          ))}
        </div>
      )}

      {reportText && (
        <div className="prose prose-sm prose-invert max-w-none text-muted-foreground">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{reportText}</ReactMarkdown>
          {isStreaming && (
            <span className="inline-block w-1.5 h-4 bg-blue-400 align-middle animate-pulse ml-0.5" />
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && git add services/frontend/components/ && git commit -m "feat(frontend): StepTracker, MetricCards, ReportViewer components"
```

---

## Task 7: Frontend — Analyze page

**Files:**
- Create: `services/frontend/app/analyze/page.tsx`

- [ ] **Step 1: Create `services/frontend/app/analyze/` directory and page**

```bash
mkdir -p "/Users/eeshandhawan/Desktop/PulseAlpha AI/services/frontend/app/analyze"
```

- [ ] **Step 2: Create `services/frontend/app/analyze/page.tsx`**

```typescript
"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import MetricCards from "@/components/MetricCards";
import ReportViewer from "@/components/ReportViewer";
import Sidebar from "@/components/Sidebar";
import StepTracker from "@/components/StepTracker";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fetchHistoryRun } from "@/lib/api";
import { useAnalysisStream } from "@/lib/stream";

function AnalyzeContent() {
  const searchParams = useSearchParams();
  const runId = searchParams.get("run_id");

  const [ticker, setTicker] = useState("");
  const [query, setQuery] = useState("");
  const { steps, metrics, reportText, isStreaming, error, start, reset } = useAnalysisStream();
  const [loadedReport, setLoadedReport] = useState<string | null>(null);
  const [loadedTicker, setLoadedTicker] = useState<string | null>(null);
  const [loadedStance, setLoadedStance] = useState<string | null>(null);

  // Load a past run when ?run_id= is present
  useEffect(() => {
    if (!runId) return;
    fetchHistoryRun(runId).then((run) => {
      if (!run) return;
      setLoadedTicker(run.ticker);
      setLoadedStance(run.stance);
      setLoadedReport(run.report);
      setTicker(run.ticker);
      setQuery(run.query);
    });
  }, [runId]);

  const handleRun = () => {
    if (!ticker.trim() || isStreaming) return;
    setLoadedReport(null);
    setLoadedTicker(null);
    setLoadedStance(null);
    start(ticker, query || "Analyze this ticker");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleRun();
  };

  const displayTicker = loadedTicker ?? ticker;
  const displayStance = loadedStance ?? metrics?.stance ?? null;
  const displayReport = loadedReport ?? reportText;

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0">
        {/* Query bar */}
        <div className="flex gap-2 px-4 py-3 border-b border-border">
          <Input
            className="w-40 bg-surface border-border text-foreground placeholder:text-muted"
            placeholder="RELIANCE.NS"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
          />
          <Input
            className="flex-1 bg-surface border-border text-foreground placeholder:text-muted"
            placeholder="What's the Q3 outlook?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
          />
          <Button
            onClick={isStreaming ? reset : handleRun}
            disabled={!ticker.trim() && !isStreaming}
            className={
              isStreaming
                ? "bg-blue-900 text-blue-300 hover:bg-blue-800"
                : "bg-blue-800 text-blue-100 hover:bg-blue-700"
            }
          >
            {isStreaming ? "⏹ Stop" : "▶ Run"}
          </Button>
        </div>

        {error && (
          <div className="mx-4 mt-2 p-2 rounded bg-red-950 border border-red-800 text-red-400 text-xs">
            {error}
          </div>
        )}

        {/* Main content */}
        <div className="flex flex-1 min-h-0">
          <StepTracker steps={steps} />
          <div className="flex flex-col flex-1 gap-3 p-4 min-h-0 min-w-0">
            <MetricCards metrics={metrics} />
            <ReportViewer
              ticker={displayTicker}
              stance={displayStance}
              reportText={displayReport}
              isStreaming={isStreaming}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AnalyzePage() {
  return (
    <Suspense>
      <AnalyzeContent />
    </Suspense>
  );
}
```

- [ ] **Step 3: Verify build still passes**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI/services/frontend" && npm run build 2>&1 | tail -15
```
Expected: Compiled successfully with no errors.

- [ ] **Step 4: Commit**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && git add services/frontend/app/analyze/ && git commit -m "feat(frontend): Analyze page with SSE streaming, step tracker, metrics, report"
```

---

## Task 8: Frontend — HistoryTable + History page

**Files:**
- Create: `services/frontend/components/HistoryTable.tsx`
- Create: `services/frontend/app/history/page.tsx`

- [ ] **Step 1: Create `services/frontend/components/HistoryTable.tsx`**

```typescript
"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import type { HistoryRun } from "@/lib/api";

function stanceBadgeClass(stance: string) {
  if (stance === "bullish") return "bg-green-900 text-green-400 border-0";
  if (stance === "bearish") return "bg-red-900 text-red-400 border-0";
  return "bg-yellow-900 text-yellow-400 border-0";
}

function confColor(conf: number) {
  if (conf >= 0.75) return "text-blue-400";
  if (conf >= 0.5) return "text-yellow-400";
  return "text-red-400";
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", { month: "short", day: "numeric" });
}

export default function HistoryTable({ runs }: { runs: HistoryRun[] }) {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [stanceFilter, setStanceFilter] = useState("all");

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return runs.filter((r) => {
      const matchSearch =
        !q || r.ticker.toLowerCase().includes(q) || r.query.toLowerCase().includes(q);
      const matchStance = stanceFilter === "all" || r.stance === stanceFilter;
      return matchSearch && matchStance;
    });
  }, [runs, search, stanceFilter]);

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Toolbar */}
      <div className="flex gap-2 px-4 py-3 border-b border-border">
        <Input
          className="flex-1 bg-surface border-border text-foreground placeholder:text-muted"
          placeholder="🔍  Search ticker or query…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="bg-surface border border-border text-muted-foreground text-xs rounded-md px-3 py-1.5"
          value={stanceFilter}
          onChange={(e) => setStanceFilter(e.target.value)}
        >
          <option value="all">All stances</option>
          <option value="bullish">Bullish</option>
          <option value="bearish">Bearish</option>
          <option value="neutral">Neutral</option>
        </select>
      </div>

      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border text-[10px] uppercase tracking-widest text-muted">
        <span className="w-28">Ticker</span>
        <span className="flex-1">Query</span>
        <span className="w-16">Stance</span>
        <span className="w-10 text-right">Conf</span>
        <span className="w-14 text-right">Date</span>
      </div>

      {/* Rows */}
      <div className="flex-1 overflow-auto">
        {filtered.length === 0 && (
          <p className="text-center text-muted text-sm py-12">
            No runs yet — go to Analyze to run your first analysis.
          </p>
        )}
        {filtered.map((run) => (
          <div
            key={run.run_id}
            className="flex items-center gap-3 px-4 py-2.5 border-b border-[#0f1629] cursor-pointer hover:bg-surface transition-colors"
            onClick={() => router.push(`/analyze?run_id=${run.run_id}`)}
          >
            <span className="w-28 text-sm font-bold text-foreground truncate">{run.ticker}</span>
            <span className="flex-1 text-xs text-muted truncate">{run.query}</span>
            <span className="w-16">
              <Badge className={`text-[10px] font-bold ${stanceBadgeClass(run.stance)}`}>
                {run.stance.toUpperCase().slice(0, 4)}
              </Badge>
            </span>
            <span className={`w-10 text-right text-xs font-semibold ${confColor(run.confidence)}`}>
              {Math.round(run.confidence * 100)}%
            </span>
            <span className="w-14 text-right text-[11px] text-muted">
              {formatDate(run.created_at)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `services/frontend/app/history/` directory**

```bash
mkdir -p "/Users/eeshandhawan/Desktop/PulseAlpha AI/services/frontend/app/history"
```

- [ ] **Step 3: Create `services/frontend/app/history/page.tsx`**

```typescript
import HistoryTable from "@/components/HistoryTable";
import Sidebar from "@/components/Sidebar";
import { fetchHistory } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HistoryPage() {
  const runs = await fetchHistory();

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-col flex-1 min-h-0">
        <div className="px-4 py-3 border-b border-border">
          <h1 className="text-sm font-bold text-foreground">Analysis History</h1>
          <p className="text-xs text-muted mt-0.5">{runs.length} past runs</p>
        </div>
        <HistoryTable runs={runs} />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verify build**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI/services/frontend" && npm run build 2>&1 | tail -15
```
Expected: Compiled successfully.

- [ ] **Step 5: Commit**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && git add services/frontend/components/HistoryTable.tsx services/frontend/app/history/ && git commit -m "feat(frontend): HistoryTable with search/filter + History page"
```

---

## Task 9: End-to-end smoke test

- [ ] **Step 1: Start the API server**

```bash
lsof -ti:8000 | xargs kill -9 2>/dev/null; true
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run --package api uvicorn api.main:app --host 0.0.0.0 --port 8000 &
sleep 3
curl -s http://localhost:8000/health
```
Expected: `{"status":"ok",...}`

- [ ] **Step 2: Test the SSE endpoint manually**

```bash
curl -N "http://localhost:8000/analyze/stream?ticker=RELIANCE.NS&query=Quick+test" 2>&1 | head -20
```
Expected: Lines starting with `data: {"type": "step", "node": "ingest", ...}` streaming in.

- [ ] **Step 3: Start the frontend**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI/services/frontend" && npm run dev &
sleep 5
curl -s http://localhost:3000 -L -I | head -5
```
Expected: `HTTP/1.1 200 OK` (after redirect to /analyze).

- [ ] **Step 4: Open the UI and run an analysis**

Open `http://localhost:3000` in your browser. Type `RELIANCE.NS` in the ticker field, type any question, click Run. Verify:
- Steps check off one by one on the left panel
- Metric cards populate after the council step
- Report text streams in on the right
- After "done", the History page at `http://localhost:3000/history` shows the run

- [ ] **Step 5: Final commit**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && git add -A && git commit -m "chore: frontend UI complete — Next.js dashboard with SSE streaming"
```
