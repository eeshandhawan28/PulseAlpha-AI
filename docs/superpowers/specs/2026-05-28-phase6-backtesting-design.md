# Phase 6: Backtesting Harness Design

**Date:** 2026-05-28
**Project:** PulseAlpha AI
**Phase:** 6 — Backtesting (builds on Phase 0–5 foundation)

---

## Goal

Add a backtesting harness that replays the full Phase 1–5 analysis pipeline over historical Indian market data, evaluates predicted stances (bullish/bearish/neutral) against actual price outcomes at 30/90/180-day horizons, and produces a structured JSON report with four metric classes: hit rate, confidence calibration, per-persona accuracy, and divergence-score correlation.

---

## Constraints

- `as_of_date: date | None = None` added to `AnalysisState` — `None` means live mode (no change to existing behaviour)
- Existing nodes (`ingest_all_data`, `compute_features`, etc.) are not modified as LangGraph nodes — the backtest runner calls the underlying async functions directly, bypassing the graph
- Sentiment connector returns empty data when `as_of_date` is set (historical RSS feeds unavailable)
- FII/DII connector returns empty when `as_of_date` is set (historical NSE HTML scraping unreliable)
- Neutral stances are excluded from directional hit rate calculations
- No new Python packages required — `yfinance` already in connectors, `scipy` for correlation (or fallback to manual calculation)
- All LLM calls mocked in tests — no real API calls in CI
- Node never raises — graceful degradation on connector or LLM failure

---

## Architecture

Phase 6 adds a `backtest/` sub-package to `services/worker/worker/` and a `POST /backtest` route to the API. It does not modify any existing LangGraph nodes.

```
BacktestRunner (runner.py)
  │
  ├── sampler.py      → generate_sample_dates(start, end, frequency) → list[date]
  │
  ├── [per sample date]
  │     ├── Data phase: ingest_all_data → compute_features → compute_divergence → normalize_and_validate
  │     │   (called directly as async functions, not via graph)
  │     │   (sentiment + FII/DII return empty when as_of_date set)
  │     │
  │     └── Stance phase (pluggable):
  │           default  → run_council()     (full LLM, 5 personas)
  │           fast mode → heuristic_stance()  (RRG quadrant rule, no LLM)
  │
  ├── outcomes.py     → fetch_outcomes(ticker, as_of_date, horizons) → dict[int, float | None]
  │
  ├── metrics.py      → compute all 4 metric classes from list[PredictionRecord]
  │
  └── results.py      → serialize BacktestResult to JSON, save to output_dir
```

---

## Data Model

### New schemas in `libs/schemas/schemas/backtest.py`

```python
from __future__ import annotations
from datetime import date, datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class BacktestConfig(BaseModel):
    tickers: list[str]
    start_date: date
    end_date: date
    horizons_days: list[int] = [30, 90, 180]
    frequency: Literal["monthly", "weekly"] = "monthly"
    fast_mode: bool = False
    user_query: str = "Backtest analysis"
    output_dir: str = "backtest_results"


class PredictionRecord(BaseModel):
    as_of_date: date
    ticker: str
    stance: str                          # "bullish" | "bearish" | "neutral"
    confidence: float
    divergence_score: float
    persona_stances: dict[str, str]      # {"Contrarian": "bullish", ...}
    outcomes: dict[int, float | None]    # {30: 0.04, 90: -0.02, 180: None}
    correct: dict[int, bool | None]      # {30: True, 90: False, 180: None}


class BacktestResult(BaseModel):
    run_id: str
    config: BacktestConfig
    predictions: list[PredictionRecord]
    metrics: dict[str, Any]
    output_file: str
    created_at: datetime
```

### Modified `libs/schemas/schemas/state.py`

Add one field to `AnalysisState`:
```python
as_of_date: date | None = None
```

---

## Key Components

### `sampler.py` — `generate_sample_dates(start, end, frequency) -> list[date]`

- `"monthly"`: first Monday on or after the 1st of each month between start and end (inclusive)
- `"weekly"`: every Monday between start and end
- Returns empty list if start > end
- No external dependencies — pure datetime arithmetic

### `outcomes.py` — `fetch_outcomes(ticker, as_of_date, horizons) -> dict[int, float | None]`

- Downloads OHLCV for `ticker` from `as_of_date` to `as_of_date + max(horizons) + 10` (buffer for holidays) via `yf.download()` — single call per ticker
- For each horizon `h`: finds the closest trading day on or after `as_of_date + timedelta(days=h)`, returns `(close_at_horizon / close_at_as_of_date) - 1.0` as the return
- Returns `None` for a horizon if data is unavailable (future date, delisted ticker, yfinance error)
- `correct[h]`: `True` if stance=="bullish" and outcome>0, or stance=="bearish" and outcome<0; `False` otherwise; `None` if outcome is None or stance=="neutral"

### `metrics.py` — four functions, each takes `list[PredictionRecord]`

**`hit_rate(predictions, horizon) -> dict`**
```
{
  "overall": 0.62,
  "bullish": 0.65,
  "bearish": 0.58,
  "n_evaluated": 42,
  "n_excluded_neutral": 8
}
```
Neutral stances excluded. Returns zeroed dict if no predictions.

**`confidence_calibration(predictions, horizon) -> list[dict]`**
Buckets: `[0.0, 0.4)`, `[0.4, 0.6)`, `[0.6, 0.8)`, `[0.8, 1.0]`
```
[{"bucket": "0.6-0.8", "accuracy": 0.71, "n": 18}, ...]
```

**`persona_accuracy(predictions, horizon) -> dict[str, dict]`**
```
{
  "Contrarian": {"accuracy": 0.68, "n": 42},
  "FirstPrinciples": {"accuracy": 0.60, "n": 42},
  ...
}
```

**`divergence_correlation(predictions, horizon) -> dict`**
```
{
  "correlation": -0.31,   # negative = lower divergence → better accuracy
  "n": 42
}
```
Pearson correlation between `divergence_score` and `correct` (1/0). Uses `statistics.correlation` (Python 3.12+) or manual formula.

### `heuristic.py` — `heuristic_stance(state) -> AnalysisState`

Fast mode stance provider:
- Looks at RRG points in `state.rotation`: if majority of tickers are in "Leading" quadrant → `stance="bullish"`, else `stance="bearish"`
- Sets `confidence=0.5` for all outputs
- Fills `persona_stances` with all 5 personas set to the same stance
- Writes 5 identical `CouncilOutput` objects to `state.council_outputs`
- Appends one audit entry

### `runner.py` — `BacktestRunner`

```python
class BacktestRunner:
    def __init__(self, config: BacktestConfig) -> None: ...

    async def run(self) -> BacktestResult:
        sample_dates = generate_sample_dates(config.start_date, config.end_date, config.frequency)
        predictions: list[PredictionRecord] = []

        for sample_date in sample_dates:
            for ticker in config.tickers:
                state = AnalysisState(
                    user_query=config.user_query,
                    ticker_universe=[ticker],
                    as_of_date=sample_date,
                )
                # Data phase — direct async calls, not via graph
                state = await ingest_all_data(state)
                state = await compute_features(state)
                state = await compute_divergence_node(state)
                state = await normalize_and_validate(state)

                # Stance phase — pluggable
                if config.fast_mode:
                    state = heuristic_stance(state)
                else:
                    state = await run_council(state)

                # Fetch outcomes
                outcomes = await fetch_outcomes(ticker, sample_date, config.horizons_days)
                correct = _compute_correct(state, outcomes)

                predictions.append(PredictionRecord(...))

        metrics = _compute_all_metrics(predictions, config.horizons_days)
        result = BacktestResult(predictions=predictions, metrics=metrics, ...)
        save_results(result, config.output_dir)
        return result
```

Each ticker × date is run sequentially (not concurrently) to avoid yfinance rate limiting.

### `results.py` — `save_results(result, output_dir) -> str`

- Creates `output_dir` if absent
- Filename: `{run_id}_{start_date}_{end_date}.json`
- Writes `result.model_dump(mode="json")` — all dates serialized as ISO strings
- Returns absolute file path

### `__main__.py` — CLI

```bash
uv run python -m worker.backtest \
  --tickers RELIANCE.NS,TCS.NS \
  --start 2022-01-01 \
  --end 2023-12-31 \
  --frequency monthly \
  --fast \
  --output-dir backtest_results
```

Prints summary table to stdout on completion:

```
Backtest complete — 24 dates × 2 tickers = 48 predictions
Output: backtest_results/abc123_2022-01-01_2023-12-31.json

Hit rate (90d):  overall=0.62  bullish=0.65  bearish=0.58
Calibration:     0.4-0.6: 0.51  0.6-0.8: 0.67  0.8-1.0: 0.74
Divergence corr: -0.31 (lower divergence → better accuracy)
```

### `services/api/routes/backtest.py` — `POST /backtest`

Request body: `BacktestConfig` JSON.
Response: `BacktestResult` JSON (same as file contents).
Runs `BacktestRunner(config).run()` and returns result.
File is also saved to `config.output_dir` on the server.

---

## Connector Modifications

### `libs/connectors/sentiment.py`
When `as_of_date` is set on the caller's state, the ingest node passes it. Sentiment connector: if `as_of_date is not None`, return `ConnectorResult(data={"headlines": []}, confidence=0.0)` immediately without fetching RSS.

### `libs/connectors/fii_dii.py`
Same pattern: if `as_of_date is not None`, return empty result (historical NSE HTML is unreliable).

### `libs/connectors/market_data.py` and `libs/connectors/fundamentals.py`
Add optional `as_of_date` parameter to `_fetch()`. Pass as `end` date to `yf.download()` / `yf.Ticker().history()`. When `None`, behaves exactly as today.

### `services/worker/worker/nodes/ingest.py`
Pass `state.as_of_date` to connector fetch calls. No change to connector interface contract — `as_of_date` is passed as a keyword argument.

---

## Error Handling

| Scenario | Handling |
|---|---|
| `yfinance` returns no data at a horizon | `outcomes[h] = None`, `correct[h] = None`, excluded from metrics |
| Connector failure during backtest | Same graceful degradation as live mode — missing data, run continues |
| LLM failure in full mode | Council's neutral fallback applies; neutral excluded from hit rate |
| Empty date range (start > end) | `sampler` returns `[]`, `BacktestResult` has empty predictions, zeroed metrics |
| `output_dir` does not exist | Created automatically by `save_results` |
| `as_of_date` is `None` (live mode) | All connectors behave as today — no change to existing behaviour |

---

## File Map

```
libs/schemas/schemas/
└── backtest.py                       NEW — BacktestConfig, PredictionRecord, BacktestResult

services/worker/worker/
├── backtest/
│   ├── __init__.py                   NEW
│   ├── sampler.py                    NEW — generate_sample_dates()
│   ├── outcomes.py                   NEW — fetch_outcomes()
│   ├── metrics.py                    NEW — hit_rate, confidence_calibration, persona_accuracy, divergence_correlation
│   ├── results.py                    NEW — save_results()
│   ├── heuristic.py                  NEW — heuristic_stance()
│   └── runner.py                     NEW — BacktestRunner
└── __main__.py                       NEW — CLI entry point

services/api/routes/
└── backtest.py                       NEW — POST /backtest

tests/unit/
├── schemas/
│   └── test_backtest_schema.py       NEW
└── worker/
    └── backtest/
        ├── __init__.py               NEW
        ├── test_sampler.py           NEW
        ├── test_outcomes.py          NEW
        ├── test_metrics.py           NEW
        ├── test_heuristic.py         NEW
        └── test_runner.py            NEW

tests/integration/
└── test_backtest_endpoint.py         NEW

Modified:
- libs/schemas/schemas/state.py           — add as_of_date: date | None = None
- libs/schemas/schemas/__init__.py        — export BacktestConfig, PredictionRecord, BacktestResult
- libs/connectors/market_data.py          — pass as_of_date to yfinance
- libs/connectors/fundamentals.py         — pass as_of_date to yfinance
- libs/connectors/fii_dii.py              — return empty when as_of_date set
- libs/connectors/sentiment.py            — return empty when as_of_date set
- services/worker/worker/nodes/ingest.py  — pass state.as_of_date to connectors
- services/api/main.py                    — register backtest router
- libs/schemas/schemas/__init__.py        — export new backtest schemas
```

---

## Testing Strategy

| Test file | What it verifies |
|---|---|
| `test_backtest_schema.py` | Config validation; PredictionRecord with None outcomes; BacktestResult serializes to JSON cleanly |
| `test_sampler.py` | Monthly sampling; weekly sampling; start==end returns one date; start>end returns empty |
| `test_outcomes.py` | yfinance mocked; correct return at each horizon; None when data missing; single download call per ticker |
| `test_metrics.py` | Hit rate with known correct/incorrect predictions; calibration bucketing; persona accuracy per persona; divergence correlation sign and value |
| `test_heuristic.py` | Leading majority → bullish; non-Leading → bearish; all 5 CouncilOutputs written; confidence=0.5 |
| `test_runner.py` | Full run with 2 dates × 1 ticker, mocked connectors + council LLM; fast_mode=True uses heuristic; neutral excluded from metrics; JSON file written |
| `test_backtest_endpoint.py` | POST /backtest returns 200, predictions list, metrics dict, output_file path |

---

## Phase Exit Criteria

- `POST /backtest` returns 200 with `predictions`, `metrics`, `output_file`
- CLI `python -m worker.backtest` prints summary and writes JSON
- Hit rate, calibration, persona accuracy, divergence correlation all present in `metrics`
- `as_of_date=None` on live `POST /analyze` — no behaviour change
- All unit + integration tests pass
- `ruff check .` clean, `mypy` clean

---

## Dependencies

No new Python packages required. `yfinance` already in `libs/connectors`. `statistics.correlation` (stdlib, Python 3.10+) for Pearson correlation. If unavailable, manual formula used.
