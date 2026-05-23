# Phase 2: Feature Engineering Design

**Date:** 2026-05-23
**Project:** PulseAlpha AI
**Phase:** 2 — Feature Engineering (builds on Phase 0+1 foundation)

---

## Goal

Build a pure Python feature engineering layer (`libs/features/`) that transforms raw connector outputs into typed analytical signals: RRG quadrant positions, FII/DII flow strength metrics, IPO GMP disagreement scores, and a multi-signal divergence detector. All feature modules are stateless pure functions — no I/O, no LLM calls.

---

## Constraints

- All code is Python 3.11+ (LangGraph and agent-side code must remain Python)
- Feature modules have zero I/O — connectors fetch, features transform
- Every module must be independently testable with synthetic fixture data
- Graph must never hard-block on optional data (GMP, sentiment) — graceful None returns required

---

## Architecture

### Data Flow

```
ConnectorResult objects (prices, fii_dii history, ipo_gmp, sentiment)
        |
        v
libs/features/* (pure pandas/numpy transforms)
        |
        v
Typed feature results (RRGResult, FlowStrengthResult, IPOGMPResult, DivergenceResult)
        |
        v
AnalysisState.rotation / alt_data / divergence_score
        |
        v
LangGraph nodes (Phase 3) — read from state, never call feature functions directly
```

### Design Principle

Option A (selected): Pure stateless transforms. Each feature module exports plain functions accepting DataFrames and typed dicts, returning typed Pydantic models. No classes, no internal state. LangGraph nodes in Phase 3 become thin wrappers that call these functions with connector output.

---

## File Map

```
libs/features/
├── pyproject.toml
└── features/
    ├── __init__.py
    ├── rrg.py              # RRG engine — RS ratio, momentum, quadrant classification
    ├── fii_dii.py          # Flow z-score, ratio, streak metrics
    ├── ipo_gmp.py          # GMP disagreement score (pure math, no scraping)
    └── divergence.py       # Binary conflict flags + aggregate divergence score

libs/schemas/schemas/
├── state.py                # MODIFIED: add divergence_score: float field
└── features.py             # NEW: RRGPoint, RRGResult, FlowStrengthResult, IPOGMPResult, DivergenceResult

libs/connectors/connectors/
└── ipo_gmp.py              # NEW: httpx + BeautifulSoup scraper for ipowatch.in

tests/unit/features/
├── __init__.py
├── test_rrg.py
├── test_fii_dii_features.py
├── test_ipo_gmp_features.py
└── test_divergence.py

tests/unit/connectors/
└── test_ipo_gmp_connector.py
```

---

## Module 1: RRG Engine (`libs/features/features/rrg.py`)

### Inputs

- `prices: dict[str, pd.DataFrame]` — keyed by ticker, each DataFrame has a `close` column (daily)
- `benchmark_df: pd.DataFrame` — close prices for benchmark index
- `smoothing: int = 10` — EMA span for both RS ratio and RS momentum
- `momentum_lag: int = 1` — shift period for ROC calculation
- `benchmark_ticker: str = "^NSEI"` — label stored in output

### Benchmark Modes

- **Default:** Nifty 50 (`^NSEI`) — caller fetches via yfinance and passes as `benchmark_df`
- **Sector-relative:** same formula, benchmark = sector index resolved from `fundamentals.data["sector"]` via a hardcoded mapping dict in `rrg.py`

Sector index mapping (non-exhaustive, extendable):
```python
SECTOR_INDEX_MAP = {
    "Financial Services": "^NSEBANK",
    "Information Technology": "^CNXIT",
    "Pharmaceuticals": "^CNXPHARMA",
    "Energy": "^CNXENERGY",
    "Consumer Cyclical": "^CNXFMCG",
    # fallback: "^NSEI" if sector not in map
}
```

### Corrected Formula

The common bug is applying ROC before EMA smoothing. Correct order:

```
raw_rs       = ticker_close / benchmark_close * 100
rs_ratio     = EMA(raw_rs, span=smoothing)                          # smooth first
raw_momentum = (rs_ratio / rs_ratio.shift(momentum_lag) - 1) * 100
rs_momentum  = EMA(raw_momentum, span=smoothing)                    # then smooth momentum
```

### Quadrant Classification

Applied to the latest (most recent) row's values:

| Condition | Quadrant |
|-----------|----------|
| rs_ratio > 100 AND rs_momentum > 0 | Leading |
| rs_ratio > 100 AND rs_momentum ≤ 0 | Weakening |
| rs_ratio ≤ 100 AND rs_momentum ≤ 0 | Lagging |
| rs_ratio ≤ 100 AND rs_momentum > 0 | Improving |

### Output Types

```python
class RRGPoint(BaseModel):
    ticker: str
    rs_ratio: float
    rs_momentum: float
    quadrant: Literal["Leading", "Weakening", "Lagging", "Improving"]
    benchmark: str        # "^NSEI" or sector index ticker
    as_of: date

class RRGResult(BaseModel):
    points: list[RRGPoint]
    smoothing: int
    momentum_lag: int
```

### Function Signature

```python
def compute_rrg(
    prices: dict[str, pd.DataFrame],
    benchmark_df: pd.DataFrame,
    smoothing: int = 10,
    momentum_lag: int = 1,
    benchmark_ticker: str = "^NSEI",
) -> RRGResult: ...
```

Tickers with insufficient history (fewer than `smoothing + momentum_lag + 5` rows) are skipped — not included in `RRGResult.points`. Caller is responsible for logging skipped tickers via `AnalysisState.append_audit`.

---

## Module 2: FII/DII Flow Strength (`libs/features/features/fii_dii.py`)

### Input

```python
flow_history: pd.DataFrame
# Required columns: date, fii_net, fii_buy, fii_sell, dii_net, dii_buy, dii_sell
# Sorted ascending by date; latest row = today's data
zscore_window: int = 20
```

Assembled by the caller from a list of historical `ConnectorResult` objects (the existing FIIDIIConnector).

### Three Computed Features

**1. Z-score (magnitude extremity)**
```
fii_zscore = (fii_net_today - rolling_mean(fii_net, 20)) / rolling_std(fii_net, 20)
dii_zscore = (dii_net_today - rolling_mean(dii_net, 20)) / rolling_std(dii_net, 20)
```
Measures how anomalous today's flow is relative to the past 20 trading days.

**2. Flow ratio (directional conviction)**
```
fii_ratio = fii_net / (fii_buy + fii_sell)   # range: -1.0 to +1.0
dii_ratio = dii_net / (dii_buy + dii_sell)
```
+1.0 = pure buying conviction, -1.0 = pure selling, 0 = balanced two-way flow.

**3. Streak metrics**
```
fii_streak = count of consecutive days where fii_net > 0 (positive int)
           = negative count if fii_net < 0 for consecutive days (negative int)
dii_streak = same for dii_net
```
Example: `fii_streak = 5` → 5-day buying streak. `fii_streak = -3` → 3-day selling streak.

**Combined signal:**
```
net_institutional = fii_net + dii_net   # total institutional pressure on the market
```

### Output Type

```python
class FlowStrengthResult(BaseModel):
    date: date
    fii_zscore: float
    fii_ratio: float
    fii_streak: int        # positive = buying, negative = selling
    dii_zscore: float
    dii_ratio: float
    dii_streak: int
    net_institutional: float
```

### Function Signature

```python
def compute_flow_strength(
    flow_history: pd.DataFrame,
    zscore_window: int = 20,
) -> FlowStrengthResult: ...
```

Returns metrics for the latest row only. Raises `ValueError` if DataFrame has fewer than `zscore_window` rows (caller must ensure sufficient history).

---

## Module 3: IPO GMP Connector + Disagreement Score

### Connector (`libs/connectors/connectors/ipo_gmp.py`)

Scrapes `ipowatch.in` using httpx + BeautifulSoup. Overrides `fetch()` directly (same pattern as `NSEQuotesConnector`) because the site returns structured HTML tables, not JSON.

Target fields per IPO row:
```
company_name, issue_price (float), gmp (float),
qib_subscription (float, x times), hni_subscription (float), retail_subscription (float)
```

On parse failure: `ConnectorError(code="PARSE_ERROR", retryable=False)` — graph continues without GMP data.

Ticker argument to `fetch()` is the company name substring used to filter the scraped table (e.g., `"Reliance"`) — not a stock ticker.

### Feature Function (`libs/features/features/ipo_gmp.py`)

```
gmp_implied_return   = gmp / issue_price
institutional_signal = log1p(qib_subscription) / log1p(qib_history_max)   # normalized 0–1
                       fallback: simple min-max if qib_history is None
retail_signal        = log1p(retail_subscription) / log1p(retail_history_max)

disagreement_score   = abs(gmp_implied_return - institutional_signal)
```

High score signals grey market excitement misaligned with institutional demand (or vice versa).

### Output Type

```python
class IPOGMPResult(BaseModel):
    company_name: str
    issue_price: float
    gmp: float
    gmp_implied_return: float     # gmp / issue_price
    institutional_signal: float   # normalized QIB subscription, 0.0–1.0
    retail_signal: float
    disagreement_score: float     # 0.0 = aligned, higher = more conflict
    data_available: bool          # False when scrape failed — caller checks before using
```

### Function Signature

```python
def compute_gmp_disagreement(
    connector_result: ConnectorResult,
    qib_history: list[float] | None = None,
) -> IPOGMPResult | None: ...    # None when connector_result.ok is False
```

---

## Module 4: Divergence Detector (`libs/features/features/divergence.py`)

### Signal → Direction Mapping

Each input signal is first converted to a directional vote:

| Signal | Bullish | Bearish | Neutral |
|--------|---------|---------|---------|
| RRG quadrant | Leading or Improving | Lagging or Weakening | — |
| FII z-score | > 0.5 | < -0.5 | -0.5 to 0.5 |
| FII ratio | > 0.1 | < -0.1 | -0.1 to 0.1 |
| DII z-score | > 0.5 | < -0.5 | -0.5 to 0.5 |
| Sentiment polarity | > 0.1 | < -0.1 | -0.1 to 0.1 |
| GMP disagreement | — | — | conflict flag only (not directional) |

Neutral votes are excluded from conflict detection but included in `signal_votes`.

### Binary Flags

For every non-neutral bullish/bearish pair that disagrees, emit a human-readable string:
```
"RRG=Leading conflicts with fii_zscore=bearish"
"sentiment=bullish conflicts with dii_zscore=bearish"
```
These go directly into `AnalysisState.contradictions`.

### Aggregate Divergence Score

```
signal_weights = {
    "rrg":        0.30,
    "fii_zscore": 0.25,
    "fii_ratio":  0.15,
    "dii_zscore": 0.15,
    "sentiment":  0.15,
}

majority_direction = mode of non-neutral directional votes

score = sum(weight for signal where vote != majority_direction and vote != "neutral")
```

Score ranges 0.0 (full consensus) to 1.0 (all signals conflict with majority). Goes into `AnalysisState.divergence_score`.

Score threshold for model routing (from `RoutingConfig.divergence_threshold = 0.7`): above this → escalate to Tier B or Tier C.

### Output Type

```python
class DivergenceResult(BaseModel):
    divergence_score: float
    contradictions: list[str]
    majority_direction: Literal["bullish", "bearish", "neutral"]
    signal_votes: dict[str, str]   # {"rrg": "bullish", "fii_zscore": "bearish", ...}
```

### Function Signature

```python
def compute_divergence(
    rrg: RRGPoint,
    flow: FlowStrengthResult,
    sentiment_polarity: float,
    gmp: IPOGMPResult | None = None,
) -> DivergenceResult: ...
```

GMP result is optional — if `gmp` is None or `gmp.data_available` is False, GMP is excluded from signal votes silently.

---

## AnalysisState Changes

Add one field to `libs/schemas/schemas/state.py`:

```python
divergence_score: float = Field(default=0.0, ge=0.0, le=1.0)
```

No other state changes. Feature results are stored by LangGraph nodes (Phase 3) into `AnalysisState.rotation` (RRG), `AnalysisState.alt_data` (FII/DII, GMP), and `AnalysisState.contradictions` (divergence flags).

---

## Testing Strategy

All feature tests use **synthetic fixture DataFrames** — no network calls, no connector dependencies.

| Test file | What it verifies |
|-----------|-----------------|
| `test_rrg.py` | Correct EMA order, quadrant boundaries, sector fallback, insufficient-history skip |
| `test_fii_dii_features.py` | Z-score with known mean/std, ratio edge cases (zero volume), streak direction and count |
| `test_ipo_gmp_features.py` | Disagreement score math, None return on failed connector result |
| `test_divergence.py` | Correct majority vote, score weights, neutral exclusion, None GMP handling |
| `test_ipo_gmp_connector.py` | BeautifulSoup parse with fixture HTML, PARSE_ERROR on missing table |

---

## Phase Exit Criteria

- All feature unit tests pass with synthetic data
- `compute_rrg` produces correct quadrant for at least 50 real tickers (manual spot check)
- `compute_divergence` returns a score that triggers the routing threshold on a known conflicting scenario
- `AnalysisState` schema passes existing schema tests with the new `divergence_score` field

---

## Dependencies Added

`libs/features/pyproject.toml`:
```toml
dependencies = [
    "schemas",
    "pandas>=2.2",
    "numpy>=1.26",
]
```

No new dependencies for `libs/connectors` (httpx and beautifulsoup4 already present).

## Workspace Changes

Root `pyproject.toml` must be updated to add `libs/features` as a uv workspace member and root dependency:

```toml
# [tool.uv.workspace] members — add:
"libs/features",

# [project] dependencies — add:
"features",

# [tool.uv.sources] — add:
features = { workspace = true }
```
