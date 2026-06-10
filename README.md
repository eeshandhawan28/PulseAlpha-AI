# PulseAlpha AI

Private-desk equity research powered by a multi-agent LLM council. Enter a ticker and a research mandate; receive a structured analyst report with conviction score, divergence metrics, and RRG quadrant in seconds.

Built for Indian equities (NSE/BSE). Streams live as the pipeline runs.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Browser (Next.js 14)                           │
│                                                                         │
│   Hero / Commission Panel  ──►  Analyze Page (SSE stream)               │
│   The Ledger (history)          ├─ StepTracker  (live node progress)    │
│                                 ├─ MetricCards  (verdict / conviction)  │
│                                 └─ ReportViewer (streamed markdown)     │
└────────────────────────────┬────────────────────────────────────────────┘
                             │  HTTP + Server-Sent Events
┌────────────────────────────▼────────────────────────────────────────────┐
│                        API  (FastAPI)                                   │
│                                                                         │
│   POST /analyze  ──► streams SSE back to browser                        │
│   GET  /history  ──► list past runs (history.json store)                │
│   GET  /history/{run_id}                                                │
│   GET  /health                                                          │
└────────────────────────────┬────────────────────────────────────────────┘
                             │  Python function call (same process)
┌────────────────────────────▼────────────────────────────────────────────┐
│                      Worker  (LangGraph pipeline)                       │
│                                                                         │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌────────────┐           │
│  │  ingest  │──►│ features │──►│ council  │──►│ divergence │           │
│  └──────────┘   └──────────┘   └──────────┘   └─────┬──────┘           │
│                                                      │                  │
│                              ┌───────────┐   ┌──────▼──────┐           │
│                              │ validate  │◄──│   report    │           │
│                              └───────────┘   └─────────────┘           │
│                                                                         │
│  Council personas: Contrarian · FirstPrinciples · Expansionist          │
│                    Outsider · Synthesizer                               │
└─────────────┬───────────────────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────────────────┐
│                    Connectors  (libs/connectors)                        │
│                                                                         │
│  market_data      ── yfinance OHLCV + info                              │
│  nse_quotes       ── NSE live quotes                                    │
│  nse_announcements── NSE corporate filings feed                         │
│  nse_document_fetcher─ PDF filings downloader                           │
│  document_rag     ── PDF → chunks → embeddings → ChromaDB retrieval     │
│  screener         ── screener.in fundamentals scraper                   │
│  news_aggregator  ── multi-source news scraper                          │
│  fii_dii          ── FII / DII flow data                                │
│  fundamentals     ── financial ratios                                   │
│  sentiment        ── text sentiment scoring                             │
│  ipo_gmp          ── IPO grey-market premium                            │
│  nav               ── mutual fund NAV                                   │
└─────────────────────────────────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────────────────┐
│                      Feature Libs  (libs/features)                      │
│                                                                         │
│  rrg          ── Relative Rotation Graph quadrant classification        │
│  divergence   ── cross-agent opinion divergence score                   │
│  fii_dii      ── institutional flow feature engineering                 │
│  ipo_gmp      ── GMP trend features                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

### Pipeline Node Details

| Node | What it does |
|------|-------------|
| **ingest** | Fetches raw data: OHLCV, NSE quotes, news, NSE announcements, fundamentals, FII/DII flows |
| **features** | Computes derived signals: RRG quadrant, institutional flow deltas, GMP trends |
| **council** | Runs 5 LLM personas in parallel; each returns `{stance, confidence, rationale, citations}` |
| **divergence** | Aggregates council votes → consensus stance, confidence score, divergence score |
| **report** | Builds evidence block from all data; calls LLM to write the full markdown research note |
| **validate** | Sanity-checks report structure; emits final `{stance, confidence, report_text}` |

### Document RAG

NSE PDF filings are processed through a local RAG pipeline:

```
PDF URL  ──►  pdfplumber extraction  ──►  sliding-window chunks (800 chars, 150 overlap)
         ──►  sentence-transformers embeddings  ──►  ChromaDB vector store
         ──►  cosine similarity retrieval at report generation time
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS v3 |
| API | FastAPI, Python 3.11, SSE streaming |
| Worker | LangGraph, LangChain, Anthropic Claude |
| Connectors | httpx, yfinance, pdfplumber, BeautifulSoup |
| RAG | sentence-transformers, ChromaDB |
| Tooling | uv (workspace), ruff, mypy, pytest |
| Fonts | Cormorant Garamond · Jost · Spline Sans Mono |

---

## Project Structure

```
pulsealpha-ai/
├── services/
│   ├── api/            # FastAPI service
│   ├── worker/         # LangGraph pipeline + council + report
│   └── frontend/       # Next.js app
├── libs/
│   ├── connectors/     # All external data connectors
│   ├── features/       # Signal computation libraries
│   └── schemas/        # Shared Pydantic models
├── tests/
│   ├── unit/           # Per-connector and per-lib unit tests
│   └── integration/    # End-to-end API tests
├── infra/docker/       # Dockerfiles + docker-compose
└── pyproject.toml      # uv workspace root
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) (`pip install uv`)
- Anthropic API key

### Install

```bash
# Python workspace (API + worker + all libs)
uv sync --all-extras

# Frontend
cd services/frontend
npm install
```

### Environment

Create `services/api/.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

### Run

```bash
# Terminal 1 — API + worker
uv run uvicorn api.main:app --reload --port 8000

# Terminal 2 — Frontend
cd services/frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### Docker

```bash
make docker-up    # starts api + worker containers
make docker-down
```

### Dev Commands

```bash
make lint         # ruff check + format check
make typecheck    # mypy
make test-unit    # pytest tests/unit/
make test         # pytest tests/ (requires running API)
make health       # curl /health
```
