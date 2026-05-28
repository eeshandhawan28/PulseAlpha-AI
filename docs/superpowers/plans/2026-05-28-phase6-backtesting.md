# Phase 6: Backtesting Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a backtesting harness that replays Phase 1–5 analysis over historical Indian market data, evaluates directional stances against actual price outcomes at 30/90/180-day horizons, and produces a structured JSON report with four metric classes.

**Architecture:** `backtest/` sub-package under `services/worker/worker/` with `BacktestRunner` calling node functions directly (bypassing the LangGraph graph). Pluggable stance provider: full council (default) or RRG heuristic (fast mode). New `POST /backtest` API route. `as_of_date: date | None = None` added to `AnalysisState` — `None` means live mode, no change to existing behaviour.

**Tech Stack:** Python 3.11, pydantic v2, yfinance (already in connectors), `statistics.correlation` (stdlib, Python 3.10+), FastAPI, uv monorepo.

---

## File Map

```
libs/schemas/schemas/
├── backtest.py                    NEW — BacktestConfig, PredictionRecord, BacktestResult
└── state.py                       MODIFIED — add as_of_date: date | None = None

libs/schemas/schemas/__init__.py   MODIFIED — export backtest schemas

libs/connectors/connectors/
├── market_data.py                 MODIFIED — accept as_of_date, use historical yfinance
├── sentiment.py                   MODIFIED — return empty when as_of_date set
└── fii_dii.py                     MODIFIED — return empty when as_of_date set

services/worker/worker/
├── nodes/ingest.py                MODIFIED — pass state.as_of_date to connectors
└── backtest/
    ├── __init__.py                NEW
    ├── sampler.py                 NEW — generate_sample_dates()
    ├── outcomes.py                NEW — fetch_outcomes(), _compute_correct()
    ├── metrics.py                 NEW — hit_rate, confidence_calibration, persona_accuracy, divergence_correlation
    ├── heuristic.py               NEW — heuristic_stance()
    ├── results.py                 NEW — save_results()
    ├── runner.py                  NEW — BacktestRunner
    └── __main__.py                NEW — CLI entry point

services/api/api/routes/
└── backtest.py                    NEW — POST /backtest

services/api/api/main.py           MODIFIED — register backtest router

tests/unit/
├── schemas/
│   └── test_backtest_schema.py   NEW
└── worker/
    └── backtest/
        ├── __init__.py            NEW
        ├── test_sampler.py        NEW
        ├── test_outcomes.py       NEW
        ├── test_metrics.py        NEW
        ├── test_heuristic.py      NEW
        └── test_runner.py         NEW

tests/integration/
└── test_backtest_endpoint.py      NEW
```

---

### Task 1: Backtest Schemas + `as_of_date` on AnalysisState

**Files:**
- Create: `libs/schemas/schemas/backtest.py`
- Modify: `libs/schemas/schemas/state.py`
- Modify: `libs/schemas/schemas/__init__.py`
- Test: `tests/unit/schemas/test_backtest_schema.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/schemas/test_backtest_schema.py`:

```python
from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest

from schemas.backtest import BacktestConfig, BacktestResult, PredictionRecord
from schemas.state import AnalysisState


def test_backtest_config_defaults() -> None:
    config = BacktestConfig(
        tickers=["RELIANCE.NS"],
        start_date=date(2022, 1, 1),
        end_date=date(2023, 1, 1),
    )
    assert config.horizons_days == [30, 90, 180]
    assert config.frequency == "monthly"
    assert config.fast_mode is False
    assert config.output_dir == "backtest_results"


def test_backtest_config_rejects_empty_tickers() -> None:
    with pytest.raises(Exception):
        BacktestConfig(
            tickers=[],
            start_date=date(2022, 1, 1),
            end_date=date(2023, 1, 1),
        )


def test_prediction_record_with_none_outcomes() -> None:
    record = PredictionRecord(
        as_of_date=date(2022, 3, 7),
        ticker="TCS.NS",
        stance="bullish",
        confidence=0.75,
        divergence_score=0.2,
        persona_stances={"Contrarian": "bullish", "Momentum": "bullish"},
        outcomes={30: 0.04, 90: None, 180: None},
        correct={30: True, 90: None, 180: None},
    )
    assert record.outcomes[90] is None
    assert record.correct[30] is True


def test_backtest_result_serializes_to_json() -> None:
    config = BacktestConfig(
        tickers=["RELIANCE.NS"],
        start_date=date(2022, 1, 1),
        end_date=date(2022, 3, 1),
    )
    record = PredictionRecord(
        as_of_date=date(2022, 1, 3),
        ticker="RELIANCE.NS",
        stance="bullish",
        confidence=0.7,
        divergence_score=0.3,
        persona_stances={"Contrarian": "bullish"},
        outcomes={30: 0.02},
        correct={30: True},
    )
    result = BacktestResult(
        run_id="abc123",
        config=config,
        predictions=[record],
        metrics={"hit_rate_30d": {"overall": 1.0, "n_evaluated": 1}},
        output_file="/tmp/abc123.json",
        created_at=datetime(2022, 3, 1, 12, 0, tzinfo=timezone.utc),
    )
    dumped = result.model_dump(mode="json")
    serialized = json.dumps(dumped)
    assert "abc123" in serialized
    assert "2022-01-03" in serialized


def test_analysis_state_has_as_of_date_field() -> None:
    state = AnalysisState(
        user_query="backtest",
        ticker_universe=["TCS.NS"],
        as_of_date=date(2022, 6, 6),
    )
    assert state.as_of_date == date(2022, 6, 6)


def test_analysis_state_as_of_date_defaults_none() -> None:
    state = AnalysisState(user_query="live", ticker_universe=["TCS.NS"])
    assert state.as_of_date is None
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run pytest tests/unit/schemas/test_backtest_schema.py -v 2>&1 | head -30
```
Expected: `ModuleNotFoundError: No module named 'schemas.backtest'`

- [ ] **Step 3: Create `libs/schemas/schemas/backtest.py`**

```python
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class BacktestConfig(BaseModel):
    tickers: list[str] = Field(min_length=1)
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
    stance: str  # "bullish" | "bearish" | "neutral"
    confidence: float
    divergence_score: float
    persona_stances: dict[str, str]
    outcomes: dict[int, float | None]
    correct: dict[int, bool | None]


class BacktestResult(BaseModel):
    run_id: str
    config: BacktestConfig
    predictions: list[PredictionRecord]
    metrics: dict[str, Any]
    output_file: str = ""
    created_at: datetime
```

- [ ] **Step 4: Add `as_of_date` to `libs/schemas/schemas/state.py`**

Add the field after the `divergence_score` line. The full updated field block (insert before `audit_log`):

```python
    as_of_date: date | None = None
```

Add import: `from datetime import UTC, date, datetime` (add `date` to the existing `datetime` import).

- [ ] **Step 5: Update `libs/schemas/schemas/__init__.py`**

Add to imports and `__all__`:
```python
from .backtest import BacktestConfig, BacktestResult, PredictionRecord
```
And add `"BacktestConfig"`, `"BacktestResult"`, `"PredictionRecord"` to `__all__`.

- [ ] **Step 6: Run the tests**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run pytest tests/unit/schemas/test_backtest_schema.py -v
```
Expected: All 6 tests PASS.

- [ ] **Step 7: Commit**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && git add libs/schemas/ tests/unit/schemas/test_backtest_schema.py && git commit -m "feat(schemas): BacktestConfig, PredictionRecord, BacktestResult + as_of_date on AnalysisState"
```

---

### Task 2: `sampler.py` — Date Range Generator

**Files:**
- Create: `services/worker/worker/backtest/__init__.py`
- Create: `services/worker/worker/backtest/sampler.py`
- Test: `tests/unit/worker/backtest/__init__.py`
- Test: `tests/unit/worker/backtest/test_sampler.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/worker/backtest/__init__.py` (empty).

Create `tests/unit/worker/backtest/test_sampler.py`:

```python
from __future__ import annotations

from datetime import date

from worker.backtest.sampler import generate_sample_dates


def test_monthly_returns_first_monday_of_each_month() -> None:
    dates = generate_sample_dates(date(2022, 1, 1), date(2022, 3, 31), "monthly")
    # Jan 2022: first Monday on/after Jan 1 = Jan 3 (Sunday→Monday)
    assert date(2022, 1, 3) in dates
    # Feb 2022: first Monday on/after Feb 1 = Feb 7
    assert date(2022, 2, 7) in dates
    # Mar 2022: first Monday on/after Mar 1 = Mar 7
    assert date(2022, 3, 7) in dates
    assert len(dates) == 3


def test_weekly_returns_every_monday() -> None:
    dates = generate_sample_dates(date(2022, 1, 3), date(2022, 1, 31), "weekly")
    assert date(2022, 1, 3) in dates
    assert date(2022, 1, 10) in dates
    assert date(2022, 1, 17) in dates
    assert date(2022, 1, 24) in dates
    assert date(2022, 1, 31) in dates
    assert len(dates) == 5


def test_start_equals_end_returns_one_date() -> None:
    # Jan 3, 2022 is a Monday
    dates = generate_sample_dates(date(2022, 1, 3), date(2022, 1, 3), "monthly")
    assert dates == [date(2022, 1, 3)]


def test_start_after_end_returns_empty() -> None:
    dates = generate_sample_dates(date(2022, 6, 1), date(2022, 1, 1), "monthly")
    assert dates == []


def test_monthly_end_before_first_monday_returns_empty() -> None:
    # Jan 2 2022 is a Sunday; first Monday is Jan 3; end is Jan 2 → no dates
    dates = generate_sample_dates(date(2022, 1, 1), date(2022, 1, 2), "monthly")
    assert dates == []
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run pytest tests/unit/worker/backtest/test_sampler.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError: No module named 'worker.backtest'`

- [ ] **Step 3: Create `services/worker/worker/backtest/__init__.py`**

```python
```
(empty file)

- [ ] **Step 4: Create `services/worker/worker/backtest/sampler.py`**

```python
from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Literal


def _next_monday(d: date) -> date:
    """Return d if d is Monday, else the next Monday."""
    days_ahead = (7 - d.weekday()) % 7  # Monday = 0
    return d + timedelta(days=days_ahead)


def generate_sample_dates(
    start: date,
    end: date,
    frequency: Literal["monthly", "weekly"],
) -> list[date]:
    """Generate sample dates for backtesting.

    monthly: first Monday on or after the 1st of each calendar month in [start, end]
    weekly: every Monday in [start, end]
    """
    if start > end:
        return []

    results: list[date] = []

    if frequency == "monthly":
        # Iterate month by month
        year, month = start.year, start.month
        while True:
            first_of_month = date(year, month, 1)
            sample = _next_monday(first_of_month)
            if sample > end:
                break
            if sample >= start:
                results.append(sample)
            # Advance to next month
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
            if date(year, month, 1) > end:
                break
    else:  # weekly
        # Start from the first Monday >= start
        current = _next_monday(start)
        while current <= end:
            results.append(current)
            current += timedelta(weeks=1)

    return results
```

- [ ] **Step 5: Run the tests**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run pytest tests/unit/worker/backtest/test_sampler.py -v
```
Expected: All 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && git add services/worker/worker/backtest/ tests/unit/worker/backtest/ && git commit -m "feat(backtest): sampler — generate_sample_dates for monthly/weekly frequencies"
```

---

### Task 3: `outcomes.py` — Price Outcome Fetcher

**Files:**
- Create: `services/worker/worker/backtest/outcomes.py`
- Test: `tests/unit/worker/backtest/test_outcomes.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/worker/backtest/test_outcomes.py`:

```python
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from worker.backtest.outcomes import fetch_outcomes


def _make_df(dates: list[date], closes: list[float]) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
    return pd.DataFrame({"Close": closes}, index=idx)


@pytest.mark.asyncio
async def test_fetch_outcomes_returns_correct_returns() -> None:
    # as_of_date = 2022-01-03 (Mon), horizon 30d = Feb 2
    # We provide data: Jan 3 close=100, Feb 2 close=104 → return = 0.04
    as_of = date(2022, 1, 3)
    df = _make_df(
        [date(2022, 1, 3), date(2022, 2, 2), date(2022, 4, 3)],
        [100.0, 104.0, 90.0],
    )
    with patch("worker.backtest.outcomes.yf.download", return_value=df):
        outcomes = await fetch_outcomes("RELIANCE.NS", as_of, [30, 90])
    assert outcomes[30] == pytest.approx(0.04, abs=1e-6)
    assert outcomes[90] == pytest.approx(-0.10, abs=1e-6)


@pytest.mark.asyncio
async def test_fetch_outcomes_returns_none_for_missing_horizon() -> None:
    as_of = date(2022, 1, 3)
    # Only data for 30-day horizon, not 90-day
    df = _make_df([date(2022, 1, 3), date(2022, 2, 2)], [100.0, 105.0])
    with patch("worker.backtest.outcomes.yf.download", return_value=df):
        outcomes = await fetch_outcomes("TCS.NS", as_of, [30, 90])
    assert outcomes[30] == pytest.approx(0.05, abs=1e-6)
    assert outcomes[90] is None


@pytest.mark.asyncio
async def test_fetch_outcomes_returns_all_none_on_empty_df() -> None:
    empty_df = pd.DataFrame()
    with patch("worker.backtest.outcomes.yf.download", return_value=empty_df):
        outcomes = await fetch_outcomes("FAKE.NS", date(2022, 1, 3), [30, 90, 180])
    assert all(v is None for v in outcomes.values())


@pytest.mark.asyncio
async def test_fetch_outcomes_single_download_call() -> None:
    empty_df = pd.DataFrame()
    with patch("worker.backtest.outcomes.yf.download", return_value=empty_df) as mock_dl:
        await fetch_outcomes("INFY.NS", date(2022, 1, 3), [30, 90, 180])
    assert mock_dl.call_count == 1
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run pytest tests/unit/worker/backtest/test_outcomes.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError: No module named 'worker.backtest.outcomes'`

- [ ] **Step 3: Create `services/worker/worker/backtest/outcomes.py`**

```python
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

import yfinance as yf

logger = logging.getLogger(__name__)


async def fetch_outcomes(
    ticker: str,
    as_of_date: date,
    horizons: list[int],
) -> dict[int, float | None]:
    """Fetch actual price returns at each horizon from as_of_date.

    Returns dict mapping horizon_days → return (float) or None if unavailable.
    Single yfinance download call covers all horizons.
    """
    max_horizon = max(horizons)
    start_str = as_of_date.strftime("%Y-%m-%d")
    end_date = as_of_date + timedelta(days=max_horizon + 10)
    end_str = end_date.strftime("%Y-%m-%d")

    loop = asyncio.get_running_loop()
    try:
        df = await loop.run_in_executor(
            None,
            lambda: yf.download(ticker, start=start_str, end=end_str, progress=False),
        )
    except Exception as exc:
        logger.warning("fetch_outcomes yfinance error for %s: %s", ticker, exc)
        return {h: None for h in horizons}

    if df.empty:
        return {h: None for h in horizons}

    # Flatten multi-level columns if present
    if isinstance(df.columns, type(df.columns)) and hasattr(df.columns, "levels"):
        try:
            df.columns = df.columns.get_level_values(0)
        except Exception:
            pass

    # Get as_of_date closing price (first row)
    dates = [d.date() for d in df.index]
    closes = list(df["Close"])

    if as_of_date not in dates:
        # Use first available date on or after as_of_date
        base_idx = next((i for i, d in enumerate(dates) if d >= as_of_date), None)
    else:
        base_idx = dates.index(as_of_date)

    if base_idx is None:
        return {h: None for h in horizons}

    base_close = float(closes[base_idx])
    if base_close == 0.0:
        return {h: None for h in horizons}

    outcomes: dict[int, float | None] = {}
    for h in horizons:
        target = as_of_date + timedelta(days=h)
        # Find closest trading day on or after target
        horizon_idx = next((i for i, d in enumerate(dates) if d >= target), None)
        if horizon_idx is None:
            outcomes[h] = None
        else:
            horizon_close = float(closes[horizon_idx])
            outcomes[h] = (horizon_close / base_close) - 1.0

    return outcomes
```

- [ ] **Step 4: Run the tests**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run pytest tests/unit/worker/backtest/test_outcomes.py -v
```
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && git add services/worker/worker/backtest/outcomes.py tests/unit/worker/backtest/test_outcomes.py && git commit -m "feat(backtest): outcomes — fetch_outcomes with single yfinance download per ticker"
```

---

### Task 4: `metrics.py` — Four Metric Functions

**Files:**
- Create: `services/worker/worker/backtest/metrics.py`
- Test: `tests/unit/worker/backtest/test_metrics.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/worker/backtest/test_metrics.py`:

```python
from __future__ import annotations

from datetime import date

import pytest

from schemas.backtest import PredictionRecord
from worker.backtest.metrics import (
    confidence_calibration,
    divergence_correlation,
    hit_rate,
    persona_accuracy,
)


def _make_record(
    stance: str,
    confidence: float,
    divergence_score: float,
    correct_30: bool | None,
    persona_stances: dict[str, str] | None = None,
) -> PredictionRecord:
    return PredictionRecord(
        as_of_date=date(2022, 1, 3),
        ticker="RELIANCE.NS",
        stance=stance,
        confidence=confidence,
        divergence_score=divergence_score,
        persona_stances=persona_stances or {},
        outcomes={30: 0.02 if correct_30 else (-0.02 if correct_30 is False else None)},
        correct={30: correct_30},
    )


# ── hit_rate ──────────────────────────────────────────────────────────────────

def test_hit_rate_overall() -> None:
    records = [
        _make_record("bullish", 0.7, 0.2, True),
        _make_record("bullish", 0.7, 0.2, False),
        _make_record("bearish", 0.6, 0.3, True),
        _make_record("neutral", 0.5, 0.1, None),
    ]
    result = hit_rate(records, 30)
    assert result["overall"] == pytest.approx(2 / 3, abs=1e-6)
    assert result["n_evaluated"] == 3
    assert result["n_excluded_neutral"] == 1


def test_hit_rate_excludes_neutral() -> None:
    records = [_make_record("neutral", 0.5, 0.1, None) for _ in range(5)]
    result = hit_rate(records, 30)
    assert result["overall"] == 0.0
    assert result["n_evaluated"] == 0
    assert result["n_excluded_neutral"] == 5


def test_hit_rate_empty_returns_zeroed() -> None:
    result = hit_rate([], 30)
    assert result["overall"] == 0.0
    assert result["n_evaluated"] == 0


# ── confidence_calibration ────────────────────────────────────────────────────

def test_confidence_calibration_buckets() -> None:
    records = [
        _make_record("bullish", 0.5, 0.2, True),   # bucket 0.4-0.6
        _make_record("bullish", 0.5, 0.2, False),   # bucket 0.4-0.6
        _make_record("bullish", 0.7, 0.2, True),    # bucket 0.6-0.8
        _make_record("bullish", 0.7, 0.2, True),    # bucket 0.6-0.8
    ]
    buckets = confidence_calibration(records, 30)
    by_label = {b["bucket"]: b for b in buckets}
    assert by_label["0.4-0.6"]["n"] == 2
    assert by_label["0.4-0.6"]["accuracy"] == pytest.approx(0.5, abs=1e-6)
    assert by_label["0.6-0.8"]["n"] == 2
    assert by_label["0.6-0.8"]["accuracy"] == pytest.approx(1.0, abs=1e-6)


def test_confidence_calibration_empty_bucket_excluded() -> None:
    records = [_make_record("bullish", 0.9, 0.2, True)]
    buckets = confidence_calibration(records, 30)
    labels = [b["bucket"] for b in buckets]
    assert "0.8-1.0" in labels
    assert "0.0-0.4" not in labels


# ── persona_accuracy ──────────────────────────────────────────────────────────

def test_persona_accuracy_per_persona() -> None:
    records = [
        _make_record("bullish", 0.7, 0.2, True,
                     persona_stances={"Contrarian": "bullish", "Momentum": "bearish"}),
        _make_record("bullish", 0.7, 0.2, True,
                     persona_stances={"Contrarian": "bearish", "Momentum": "bullish"}),
    ]
    result = persona_accuracy(records, 30)
    # Contrarian: first correct (bullish+correct=True), second wrong (bearish+correct=True)
    assert result["Contrarian"]["n"] == 2
    assert result["Contrarian"]["accuracy"] == pytest.approx(0.5, abs=1e-6)
    # Momentum: first wrong (bearish+correct=True→outcome positive→bearish wrong), second correct
    assert result["Momentum"]["n"] == 2
    assert result["Momentum"]["accuracy"] == pytest.approx(0.5, abs=1e-6)


# ── divergence_correlation ────────────────────────────────────────────────────

def test_divergence_correlation_negative_sign() -> None:
    # Lower divergence → more correct → negative correlation expected
    records = [
        _make_record("bullish", 0.8, 0.1, True),   # low divergence, correct
        _make_record("bullish", 0.8, 0.1, True),
        _make_record("bullish", 0.5, 0.9, False),   # high divergence, wrong
        _make_record("bullish", 0.5, 0.9, False),
    ]
    result = divergence_correlation(records, 30)
    assert result["n"] == 4
    assert result["correlation"] < 0


def test_divergence_correlation_returns_zero_for_constant() -> None:
    # All correct — variance in correct is 0 → correlation undefined → return 0.0
    records = [_make_record("bullish", 0.7, 0.2, True) for _ in range(4)]
    result = divergence_correlation(records, 30)
    assert result["correlation"] == 0.0
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run pytest tests/unit/worker/backtest/test_metrics.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError: No module named 'worker.backtest.metrics'`

- [ ] **Step 3: Create `services/worker/worker/backtest/metrics.py`**

```python
from __future__ import annotations

import statistics
import logging
from typing import Any

from schemas.backtest import PredictionRecord

logger = logging.getLogger(__name__)

_CALIBRATION_BUCKETS: list[tuple[float, float, str]] = [
    (0.0, 0.4, "0.0-0.4"),
    (0.4, 0.6, "0.4-0.6"),
    (0.6, 0.8, "0.6-0.8"),
    (0.8, 1.01, "0.8-1.0"),
]


def hit_rate(predictions: list[PredictionRecord], horizon: int) -> dict[str, Any]:
    """Directional hit rate at a given horizon. Neutral stances excluded."""
    correct_all: list[bool] = []
    correct_bull: list[bool] = []
    correct_bear: list[bool] = []
    n_neutral = 0

    for p in predictions:
        if p.stance == "neutral":
            n_neutral += 1
            continue
        c = p.correct.get(horizon)
        if c is None:
            continue
        correct_all.append(c)
        if p.stance == "bullish":
            correct_bull.append(c)
        elif p.stance == "bearish":
            correct_bear.append(c)

    def _rate(lst: list[bool]) -> float:
        return sum(lst) / len(lst) if lst else 0.0

    return {
        "overall": _rate(correct_all),
        "bullish": _rate(correct_bull),
        "bearish": _rate(correct_bear),
        "n_evaluated": len(correct_all),
        "n_excluded_neutral": n_neutral,
    }


def confidence_calibration(
    predictions: list[PredictionRecord], horizon: int
) -> list[dict[str, Any]]:
    """Group predictions by confidence bucket and compute accuracy per bucket."""
    buckets: dict[str, list[bool]] = {label: [] for _, _, label in _CALIBRATION_BUCKETS}

    for p in predictions:
        if p.stance == "neutral":
            continue
        c = p.correct.get(horizon)
        if c is None:
            continue
        for lo, hi, label in _CALIBRATION_BUCKETS:
            if lo <= p.confidence < hi:
                buckets[label].append(c)
                break

    result = []
    for _, _, label in _CALIBRATION_BUCKETS:
        items = buckets[label]
        if not items:
            continue
        result.append({
            "bucket": label,
            "accuracy": sum(items) / len(items),
            "n": len(items),
        })
    return result


def persona_accuracy(
    predictions: list[PredictionRecord], horizon: int
) -> dict[str, dict[str, Any]]:
    """Per-persona directional accuracy at a given horizon."""
    persona_data: dict[str, list[bool]] = {}

    for p in predictions:
        c = p.correct.get(horizon)
        if c is None:
            continue
        # outcome_positive: True if outcome > 0
        outcome = p.outcomes.get(horizon)
        if outcome is None:
            continue

        for persona, persona_stance in p.persona_stances.items():
            if persona_stance == "neutral":
                continue
            if persona not in persona_data:
                persona_data[persona] = []
            # persona correct if (bullish and outcome>0) or (bearish and outcome<0)
            persona_correct = (
                (persona_stance == "bullish" and outcome > 0)
                or (persona_stance == "bearish" and outcome < 0)
            )
            persona_data[persona].append(persona_correct)

    return {
        persona: {
            "accuracy": sum(lst) / len(lst) if lst else 0.0,
            "n": len(lst),
        }
        for persona, lst in persona_data.items()
    }


def divergence_correlation(
    predictions: list[PredictionRecord], horizon: int
) -> dict[str, Any]:
    """Pearson correlation between divergence_score and correct (1/0) at horizon."""
    divergences: list[float] = []
    corrects: list[float] = []

    for p in predictions:
        if p.stance == "neutral":
            continue
        c = p.correct.get(horizon)
        if c is None:
            continue
        divergences.append(p.divergence_score)
        corrects.append(1.0 if c else 0.0)

    n = len(divergences)
    if n < 2:
        return {"correlation": 0.0, "n": n}

    try:
        corr = statistics.correlation(divergences, corrects)
    except statistics.StatisticsError:
        # Constant sequence — correlation undefined
        corr = 0.0

    return {"correlation": corr, "n": n}
```

- [ ] **Step 4: Run the tests**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run pytest tests/unit/worker/backtest/test_metrics.py -v
```
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && git add services/worker/worker/backtest/metrics.py tests/unit/worker/backtest/test_metrics.py && git commit -m "feat(backtest): metrics — hit_rate, confidence_calibration, persona_accuracy, divergence_correlation"
```

---

### Task 5: `heuristic.py` + `results.py`

**Files:**
- Create: `services/worker/worker/backtest/heuristic.py`
- Create: `services/worker/worker/backtest/results.py`
- Test: `tests/unit/worker/backtest/test_heuristic.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/worker/backtest/test_heuristic.py`:

```python
from __future__ import annotations

from schemas.state import AnalysisState
from worker.backtest.heuristic import heuristic_stance

_PERSONAS = ["Contrarian", "FirstPrinciples", "Momentum", "Quant", "Macro"]


def _make_state(leading_count: int, total: int = 3) -> AnalysisState:
    tickers = [f"TICK{i}.NS" for i in range(total)]
    rotation = {}
    for i, t in enumerate(tickers):
        rotation[t] = {"quadrant": "Leading" if i < leading_count else "Lagging"}
    return AnalysisState(
        user_query="backtest",
        ticker_universe=tickers,
        rotation=rotation,
    )


def test_majority_leading_produces_bullish() -> None:
    state = _make_state(leading_count=2, total=3)
    result = heuristic_stance(state)
    assert result.confidence == 0.5
    assert result.council_outputs[0].stance == "bullish"
    assert len(result.council_outputs) == 5


def test_minority_leading_produces_bearish() -> None:
    state = _make_state(leading_count=1, total=3)
    result = heuristic_stance(state)
    assert result.council_outputs[0].stance == "bearish"


def test_all_five_personas_written() -> None:
    state = _make_state(leading_count=2, total=3)
    result = heuristic_stance(state)
    personas = [o.persona for o in result.council_outputs]
    for p in _PERSONAS:
        assert p in personas


def test_all_persona_stances_match_overall_stance() -> None:
    state = _make_state(leading_count=2, total=3)
    result = heuristic_stance(state)
    for output in result.council_outputs:
        assert output.stance == "bullish"
        assert output.confidence == 0.5


def test_audit_log_has_entry() -> None:
    state = _make_state(leading_count=2, total=3)
    result = heuristic_stance(state)
    assert any("heuristic" in e.node for e in result.audit_log)
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run pytest tests/unit/worker/backtest/test_heuristic.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError: No module named 'worker.backtest.heuristic'`

- [ ] **Step 3: Create `services/worker/worker/backtest/heuristic.py`**

```python
from __future__ import annotations

from schemas.state import AnalysisState, CouncilOutput

_PERSONAS = ["Contrarian", "FirstPrinciples", "Momentum", "Quant", "Macro"]


def heuristic_stance(state: AnalysisState) -> AnalysisState:
    """Fast-mode stance provider: derives stance from RRG quadrant majority.

    Leading majority → bullish; otherwise → bearish.
    All 5 personas assigned the same stance with confidence=0.5.
    No LLM calls.
    """
    rotation = state.rotation or {}
    leading = sum(
        1 for v in rotation.values() if isinstance(v, dict) and v.get("quadrant") == "Leading"
    )
    total = len(rotation)
    stance = "bullish" if total > 0 and leading > total / 2 else "bearish"

    outputs = [
        CouncilOutput(
            persona=p,
            stance=stance,  # type: ignore[arg-type]
            rationale="Heuristic: RRG quadrant majority",
            confidence=0.5,
        )
        for p in _PERSONAS
    ]

    state.council_outputs = outputs
    state.confidence = 0.5
    state.append_audit(
        "heuristic_stance",
        f"heuristic stance={stance} leading={leading}/{total}",
    )
    return state
```

- [ ] **Step 4: Create `services/worker/worker/backtest/results.py`**

```python
from __future__ import annotations

import json
import logging
from pathlib import Path

from schemas.backtest import BacktestResult

logger = logging.getLogger(__name__)


def save_results(result: BacktestResult, output_dir: str) -> str:
    """Serialize BacktestResult to JSON and write to output_dir.

    Returns absolute file path.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    filename = f"{result.run_id}_{result.config.start_date}_{result.config.end_date}.json"
    file_path = out_path / filename

    payload = result.model_dump(mode="json")
    file_path.write_text(json.dumps(payload, indent=2))

    logger.info("Backtest results written to %s", file_path.resolve())
    return str(file_path.resolve())
```

- [ ] **Step 5: Run the tests**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run pytest tests/unit/worker/backtest/test_heuristic.py -v
```
Expected: All 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && git add services/worker/worker/backtest/heuristic.py services/worker/worker/backtest/results.py tests/unit/worker/backtest/test_heuristic.py && git commit -m "feat(backtest): heuristic_stance (RRG fast mode) and save_results"
```

---

### Task 6: Connector Modifications + Ingest Node Update

**Files:**
- Modify: `libs/connectors/connectors/market_data.py`
- Modify: `libs/connectors/connectors/sentiment.py`
- Modify: `libs/connectors/connectors/fii_dii.py`
- Modify: `services/worker/worker/nodes/ingest.py`

There are no new test files for this task — the existing connector tests must still pass after modification.

- [ ] **Step 1: Modify `libs/connectors/connectors/market_data.py`**

Replace `__init__` and `fetch` to accept and use `as_of_date`:

```python
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

import yfinance as yf
from schemas.connectors import ConnectorError, ConnectorResult

from connectors.base import BaseConnector

logger = logging.getLogger(__name__)

_MIN_ROWS_FOR_FULL_CONFIDENCE = 60


class MarketDataConnector(BaseConnector):
    """Fetches daily OHLCV history for a ticker via yfinance.

    Args:
        period: yfinance period string (default "3mo" ≈ 63 trading days).
            Ignored when as_of_date is set.
        as_of_date: If set, fetch history ending on this date (backtest mode).
    """

    def __init__(self, period: str = "3mo", as_of_date: date | None = None) -> None:
        super().__init__(source_name="yfinance_market_data")
        self._period = period
        self._as_of_date = as_of_date

    async def fetch(self, ticker: str) -> ConnectorResult:
        loop = asyncio.get_running_loop()
        try:
            if self._as_of_date is not None:
                start_dt = self._as_of_date - timedelta(days=90)
                end_dt = self._as_of_date + timedelta(days=1)
                df = await loop.run_in_executor(
                    None,
                    lambda: yf.Ticker(ticker).history(
                        start=start_dt.strftime("%Y-%m-%d"),
                        end=end_dt.strftime("%Y-%m-%d"),
                    ),
                )
            else:
                df = await loop.run_in_executor(
                    None,
                    lambda: yf.Ticker(ticker).history(period=self._period),
                )
        except Exception as exc:
            logger.warning("MarketDataConnector FETCH_ERROR for %s: %s", ticker, exc)
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(code="FETCH_ERROR", message=str(exc), retryable=False),
            )

        if df.empty:
            logger.warning(
                "MarketDataConnector NO_DATA for %s: yfinance returned empty history",
                ticker,
            )
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(
                    code="NO_DATA",
                    message=f"yfinance returned empty history for {ticker}",
                    retryable=False,
                ),
            )

        records = [
            {
                "date": idx.strftime("%Y-%m-%d"),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]),
            }
            for idx, row in df.iterrows()
        ]

        confidence = min(len(records) / _MIN_ROWS_FOR_FULL_CONFIDENCE, 1.0)

        return ConnectorResult(
            source=self.source_name,
            ticker=ticker,
            data={"ohlcv": records, "ticker": ticker},
            confidence=confidence,
        )

    async def _fetch(self, ticker: str) -> dict[str, Any]:
        # Not used — fetch() is overridden directly.
        raise NotImplementedError
```

- [ ] **Step 2: Modify `libs/connectors/connectors/sentiment.py`**

Add `as_of_date` param and early-return when set:

```python
from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

import feedparser

from connectors.base import BaseConnector
from schemas.connectors import ConnectorResult

logger = logging.getLogger(__name__)

_FEEDS = [
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://www.moneycontrol.com/rss/business.xml",
]


class SentimentConnector(BaseConnector):
    """Fetches news headlines from RSS feeds and filters by ticker keyword.

    Returns raw headlines only — NLP scoring added in Phase 4.
    Cache TTL recommendation: 5-30 minutes.
    """

    def __init__(self, as_of_date: date | None = None) -> None:
        super().__init__(
            source_name="rss_sentiment",
            max_retries=2,
            timeout_seconds=10.0,
        )
        self._as_of_date = as_of_date

    async def fetch(self, ticker: str) -> ConnectorResult:
        if self._as_of_date is not None:
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={"headlines": [], "ticker": ticker},
                confidence=0.0,
            )
        return await super().fetch(ticker)

    async def _fetch(self, ticker: str) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        base = ticker.replace(".NS", "").replace(".BO", "").upper()
        headlines: list[dict[str, str]] = []
        for url in _FEEDS:
            feed = await loop.run_in_executor(None, feedparser.parse, url)
            for entry in feed.entries[:20]:
                title = getattr(entry, "title", "")
                if base in title.upper():
                    headlines.append(
                        {
                            "title": title,
                            "url": getattr(entry, "link", ""),
                            "published": (
                                entry.get("published", "") if hasattr(entry, "get") else ""
                            ),
                        }
                    )
        return {"headlines": headlines, "ticker": ticker}
```

- [ ] **Step 3: Modify `libs/connectors/connectors/fii_dii.py`**

Add `as_of_date` param and early-return when set. Replace `__init__` and `fetch`:

```python
    def __init__(self, as_of_date: date | None = None) -> None:
        super().__init__(
            source_name="nse_fii_dii",
            max_retries=3,
            timeout_seconds=15.0,
        )
        self._as_of_date = as_of_date

    async def fetch(self, ticker: str) -> ConnectorResult:
        """Override to convert ValueError from _parse into PARSE_ERROR ConnectorError."""
        if self._as_of_date is not None:
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
            )
        try:
            data = await self._fetch(ticker)
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data=data,
                confidence=1.0 if {"fii_net", "dii_net"}.issubset(data) else 0.5,
            )
        except ValueError as exc:
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(code="PARSE_ERROR", message=str(exc)),
            )
        except Exception as exc:
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(code="FETCH_ERROR", message=str(exc)),
            )
```

Add `from datetime import date` to imports at the top of `fii_dii.py`.

- [ ] **Step 4: Modify `services/worker/worker/nodes/ingest.py`**

Pass `state.as_of_date` when constructing connectors. Replace the four connector instantiation lines:

```python
    fund_conn = FundamentalsConnector()
    md_conn = MarketDataConnector(as_of_date=state.as_of_date)
    fii_conn = FIIDIIConnector(as_of_date=state.as_of_date)
    sent_conn = SentimentConnector(as_of_date=state.as_of_date)
    gmp_conn = IPOGMPConnector()
```

- [ ] **Step 5: Run existing connector tests to confirm no regressions**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run pytest tests/unit/connectors/ tests/unit/worker/ -v 2>&1 | tail -30
```
Expected: All previously passing tests still PASS.

- [ ] **Step 6: Commit**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && git add libs/connectors/connectors/ services/worker/worker/nodes/ingest.py && git commit -m "feat(connectors): as_of_date support — market_data historical, sentiment/fii_dii empty in backtest mode"
```

---

### Task 7: `runner.py` — BacktestRunner

**Files:**
- Create: `services/worker/worker/backtest/runner.py`
- Test: `tests/unit/worker/backtest/test_runner.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/worker/backtest/test_runner.py`:

```python
from __future__ import annotations

import json
import os
import tempfile
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from schemas.backtest import BacktestConfig
from schemas.state import AnalysisState, CouncilOutput
from worker.backtest.runner import BacktestRunner


def _mock_state_after_ingest(state: AnalysisState) -> AnalysisState:
    state.market_data = {t: {"fundamentals": None, "ohlcv": None} for t in state.ticker_universe}
    state.rotation = {t: {"quadrant": "Leading"} for t in state.ticker_universe}
    state.divergence_score = 0.2
    return state


def _mock_state_after_council(state: AnalysisState) -> AnalysisState:
    state.council_outputs = [
        CouncilOutput(persona="Contrarian", stance="bullish", rationale="test", confidence=0.7),
        CouncilOutput(persona="FirstPrinciples", stance="bullish", rationale="test", confidence=0.7),
        CouncilOutput(persona="Momentum", stance="bullish", rationale="test", confidence=0.7),
        CouncilOutput(persona="Quant", stance="bullish", rationale="test", confidence=0.7),
        CouncilOutput(persona="Macro", stance="bullish", rationale="test", confidence=0.7),
    ]
    state.confidence = 0.7
    return state


@pytest.mark.asyncio
async def test_runner_produces_predictions() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        config = BacktestConfig(
            tickers=["RELIANCE.NS"],
            start_date=date(2022, 1, 3),
            end_date=date(2022, 1, 3),
            horizons_days=[30],
            frequency="monthly",
            fast_mode=False,
            output_dir=tmpdir,
        )

        with (
            patch("worker.backtest.runner.ingest_all_data", new_callable=AsyncMock) as p_ingest,
            patch("worker.backtest.runner.compute_features", new_callable=AsyncMock) as p_feat,
            patch("worker.backtest.runner.compute_divergence_node", new_callable=AsyncMock) as p_div,
            patch("worker.backtest.runner.normalize_and_validate", new_callable=AsyncMock) as p_norm,
            patch("worker.backtest.runner.run_council", new_callable=AsyncMock) as p_council,
            patch("worker.backtest.runner.fetch_outcomes", new_callable=AsyncMock) as p_outcomes,
        ):
            p_ingest.side_effect = _mock_state_after_ingest
            p_feat.side_effect = lambda s: s
            p_div.side_effect = lambda s: s
            p_norm.side_effect = lambda s: s
            p_council.side_effect = _mock_state_after_council
            p_outcomes.return_value = {30: 0.05}

            runner = BacktestRunner(config)
            result = await runner.run()

        assert len(result.predictions) == 1
        assert result.predictions[0].stance == "bullish"
        assert result.predictions[0].correct[30] is True


@pytest.mark.asyncio
async def test_runner_fast_mode_uses_heuristic() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        config = BacktestConfig(
            tickers=["TCS.NS"],
            start_date=date(2022, 1, 3),
            end_date=date(2022, 1, 3),
            horizons_days=[30],
            fast_mode=True,
            output_dir=tmpdir,
        )

        with (
            patch("worker.backtest.runner.ingest_all_data", new_callable=AsyncMock) as p_ingest,
            patch("worker.backtest.runner.compute_features", new_callable=AsyncMock) as p_feat,
            patch("worker.backtest.runner.compute_divergence_node", new_callable=AsyncMock) as p_div,
            patch("worker.backtest.runner.normalize_and_validate", new_callable=AsyncMock) as p_norm,
            patch("worker.backtest.runner.run_council", new_callable=AsyncMock) as p_council,
            patch("worker.backtest.runner.fetch_outcomes", new_callable=AsyncMock) as p_outcomes,
        ):
            p_ingest.side_effect = _mock_state_after_ingest
            p_feat.side_effect = lambda s: s
            p_div.side_effect = lambda s: s
            p_norm.side_effect = lambda s: s
            p_council.side_effect = _mock_state_after_council
            p_outcomes.return_value = {30: 0.05}

            runner = BacktestRunner(config)
            result = await runner.run()

        # fast mode → council NOT called
        p_council.assert_not_called()
        assert len(result.predictions) == 1


@pytest.mark.asyncio
async def test_runner_writes_json_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        config = BacktestConfig(
            tickers=["INFY.NS"],
            start_date=date(2022, 1, 3),
            end_date=date(2022, 1, 3),
            horizons_days=[30],
            fast_mode=True,
            output_dir=tmpdir,
        )

        with (
            patch("worker.backtest.runner.ingest_all_data", new_callable=AsyncMock) as p_ingest,
            patch("worker.backtest.runner.compute_features", new_callable=AsyncMock) as p_feat,
            patch("worker.backtest.runner.compute_divergence_node", new_callable=AsyncMock) as p_div,
            patch("worker.backtest.runner.normalize_and_validate", new_callable=AsyncMock) as p_norm,
            patch("worker.backtest.runner.fetch_outcomes", new_callable=AsyncMock) as p_outcomes,
        ):
            p_ingest.side_effect = _mock_state_after_ingest
            p_feat.side_effect = lambda s: s
            p_div.side_effect = lambda s: s
            p_norm.side_effect = lambda s: s
            p_outcomes.return_value = {30: -0.03}

            runner = BacktestRunner(config)
            result = await runner.run()

        assert os.path.exists(result.output_file)
        with open(result.output_file) as f:
            data = json.load(f)
        assert "predictions" in data
        assert "metrics" in data


@pytest.mark.asyncio
async def test_runner_neutral_excluded_from_hit_rate() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        config = BacktestConfig(
            tickers=["WIPRO.NS"],
            start_date=date(2022, 1, 3),
            end_date=date(2022, 1, 3),
            horizons_days=[30],
            fast_mode=False,
            output_dir=tmpdir,
        )

        def _neutral_council(state: AnalysisState) -> AnalysisState:
            state.council_outputs = [
                CouncilOutput(persona="Contrarian", stance="neutral", rationale="x", confidence=0.5),
            ]
            state.confidence = 0.5
            return state

        with (
            patch("worker.backtest.runner.ingest_all_data", new_callable=AsyncMock) as p_ingest,
            patch("worker.backtest.runner.compute_features", new_callable=AsyncMock) as p_feat,
            patch("worker.backtest.runner.compute_divergence_node", new_callable=AsyncMock) as p_div,
            patch("worker.backtest.runner.normalize_and_validate", new_callable=AsyncMock) as p_norm,
            patch("worker.backtest.runner.run_council", new_callable=AsyncMock) as p_council,
            patch("worker.backtest.runner.fetch_outcomes", new_callable=AsyncMock) as p_outcomes,
        ):
            p_ingest.side_effect = _mock_state_after_ingest
            p_feat.side_effect = lambda s: s
            p_div.side_effect = lambda s: s
            p_norm.side_effect = lambda s: s
            p_council.side_effect = _neutral_council
            p_outcomes.return_value = {30: 0.05}

            runner = BacktestRunner(config)
            result = await runner.run()

        # neutral → excluded → n_evaluated=0
        assert result.metrics["hit_rate_30d"]["n_evaluated"] == 0
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run pytest tests/unit/worker/backtest/test_runner.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError: No module named 'worker.backtest.runner'`

- [ ] **Step 3: Create `services/worker/worker/backtest/runner.py`**

```python
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from schemas.backtest import BacktestConfig, BacktestResult, PredictionRecord
from schemas.state import AnalysisState
from worker.backtest.heuristic import heuristic_stance
from worker.backtest.metrics import (
    confidence_calibration,
    divergence_correlation,
    hit_rate,
    persona_accuracy,
)
from worker.backtest.outcomes import fetch_outcomes
from worker.backtest.results import save_results
from worker.backtest.sampler import generate_sample_dates
from worker.nodes.council import run_council
from worker.nodes.divergence import compute_divergence_node
from worker.nodes.features import compute_features
from worker.nodes.ingest import ingest_all_data
from worker.nodes.validate import normalize_and_validate

logger = logging.getLogger(__name__)


def _determine_stance(council_outputs: list[Any]) -> str:
    """Majority vote from council outputs."""
    if not council_outputs:
        return "neutral"
    counts: dict[str, int] = {}
    for o in council_outputs:
        counts[o.stance] = counts.get(o.stance, 0) + 1
    return max(counts, key=lambda k: counts[k])


def _compute_correct(
    stance: str,
    outcomes: dict[int, float | None],
) -> dict[int, bool | None]:
    correct: dict[int, bool | None] = {}
    for h, outcome in outcomes.items():
        if outcome is None or stance == "neutral":
            correct[h] = None
        elif stance == "bullish":
            correct[h] = outcome > 0
        else:  # bearish
            correct[h] = outcome < 0
    return correct


def _compute_all_metrics(
    predictions: list[PredictionRecord], horizons: list[int]
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for h in horizons:
        metrics[f"hit_rate_{h}d"] = hit_rate(predictions, h)
        metrics[f"confidence_calibration_{h}d"] = confidence_calibration(predictions, h)
        metrics[f"persona_accuracy_{h}d"] = persona_accuracy(predictions, h)
        metrics[f"divergence_correlation_{h}d"] = divergence_correlation(predictions, h)
    return metrics


class BacktestRunner:
    def __init__(self, config: BacktestConfig) -> None:
        self._config = config

    async def run(self) -> BacktestResult:
        config = self._config
        run_id = str(uuid.uuid4())
        sample_dates = generate_sample_dates(config.start_date, config.end_date, config.frequency)
        predictions: list[PredictionRecord] = []

        for sample_date in sample_dates:
            for ticker in config.tickers:
                logger.info("Backtesting %s as_of %s", ticker, sample_date)
                try:
                    state = AnalysisState(
                        user_query=config.user_query,
                        ticker_universe=[ticker],
                        as_of_date=sample_date,
                    )
                    state = await ingest_all_data(state)
                    state = await compute_features(state)
                    state = await compute_divergence_node(state)
                    state = await normalize_and_validate(state)

                    if config.fast_mode:
                        state = heuristic_stance(state)
                    else:
                        state = await run_council(state)

                    stance = _determine_stance(state.council_outputs)
                    outcomes = await fetch_outcomes(ticker, sample_date, config.horizons_days)
                    correct = _compute_correct(stance, outcomes)
                    persona_stances = {o.persona: o.stance for o in state.council_outputs}

                    predictions.append(
                        PredictionRecord(
                            as_of_date=sample_date,
                            ticker=ticker,
                            stance=stance,
                            confidence=state.confidence,
                            divergence_score=state.divergence_score,
                            persona_stances=persona_stances,
                            outcomes=outcomes,
                            correct=correct,
                        )
                    )
                except Exception as exc:
                    logger.warning(
                        "Backtest run failed for %s @ %s: %s", ticker, sample_date, exc
                    )

        metrics = _compute_all_metrics(predictions, config.horizons_days)
        result = BacktestResult(
            run_id=run_id,
            config=config,
            predictions=predictions,
            metrics=metrics,
            created_at=datetime.now(UTC),
        )
        output_file = save_results(result, config.output_dir)
        result = result.model_copy(update={"output_file": output_file})
        return result
```

- [ ] **Step 4: Run the tests**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run pytest tests/unit/worker/backtest/test_runner.py -v
```
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && git add services/worker/worker/backtest/runner.py tests/unit/worker/backtest/test_runner.py && git commit -m "feat(backtest): BacktestRunner — sequential per-ticker execution with pluggable stance"
```

---

### Task 8: CLI + API Route + Register Router

**Files:**
- Create: `services/worker/worker/backtest/__main__.py`
- Create: `services/api/api/routes/backtest.py`
- Modify: `services/api/api/main.py`

- [ ] **Step 1: Create `services/worker/worker/backtest/__main__.py`**

```python
"""CLI entry point: python -m worker.backtest"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def main() -> None:
    parser = argparse.ArgumentParser(description="PulseAlpha backtesting CLI")
    parser.add_argument("--tickers", required=True, help="Comma-separated tickers e.g. RELIANCE.NS,TCS.NS")
    parser.add_argument("--start", required=True, type=_parse_date, metavar="YYYY-MM-DD")
    parser.add_argument("--end", required=True, type=_parse_date, metavar="YYYY-MM-DD")
    parser.add_argument("--frequency", default="monthly", choices=["monthly", "weekly"])
    parser.add_argument("--fast", action="store_true", help="Use heuristic stance (no LLM)")
    parser.add_argument("--output-dir", default="backtest_results")
    parser.add_argument("--horizons", default="30,90,180", help="Comma-separated horizon days")
    args = parser.parse_args()

    from schemas.backtest import BacktestConfig
    from worker.backtest.runner import BacktestRunner

    config = BacktestConfig(
        tickers=[t.strip() for t in args.tickers.split(",")],
        start_date=args.start,
        end_date=args.end,
        frequency=args.frequency,
        fast_mode=args.fast,
        output_dir=args.output_dir,
        horizons_days=[int(h.strip()) for h in args.horizons.split(",")],
    )

    result = asyncio.run(BacktestRunner(config).run())

    n_dates = len({p.as_of_date for p in result.predictions})
    n_tickers = len({p.ticker for p in result.predictions})
    n_total = len(result.predictions)
    print(f"\nBacktest complete — {n_dates} dates × {n_tickers} tickers = {n_total} predictions")
    print(f"Output: {result.output_file}")

    # Print summary for first horizon
    h = config.horizons_days[0]
    hr = result.metrics.get(f"hit_rate_{h}d", {})
    cal = result.metrics.get(f"confidence_calibration_{h}d", [])
    dc = result.metrics.get(f"divergence_correlation_{h}d", {})

    print(f"\nHit rate ({h}d):  overall={hr.get('overall', 0):.2f}  "
          f"bullish={hr.get('bullish', 0):.2f}  bearish={hr.get('bearish', 0):.2f}")
    cal_str = "  ".join(f"{b['bucket']}: {b['accuracy']:.2f}" for b in cal)
    print(f"Calibration:     {cal_str or 'no data'}")
    print(f"Divergence corr: {dc.get('correlation', 0):.2f} "
          f"(lower divergence → better accuracy)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create `services/api/api/routes/backtest.py`**

```python
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from schemas.backtest import BacktestConfig, BacktestResult
from worker.backtest.runner import BacktestRunner

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/backtest", response_model=BacktestResult)
async def run_backtest(config: BacktestConfig) -> BacktestResult:
    """Run a backtesting session over historical data.

    Returns predictions, metrics, and the path to the saved JSON results file.
    """
    try:
        result = await BacktestRunner(config).run()
    except Exception as exc:
        logger.exception("Backtest runner failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result
```

- [ ] **Step 3: Register backtest router in `services/api/api/main.py`**

Read the current `main.py` to confirm its structure, then add:

```python
from api.routes.backtest import router as backtest_router
```

And inside `create_app()`:
```python
    app.include_router(backtest_router)
```

- [ ] **Step 4: Verify the API starts without errors**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run python -c "from api.main import app; print('API import OK')"
```
Expected: `API import OK`

- [ ] **Step 5: Commit**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && git add services/worker/worker/backtest/__main__.py services/api/api/routes/backtest.py services/api/api/main.py && git commit -m "feat(backtest): CLI entry point and POST /backtest API route"
```

---

### Task 9: Integration Test — `POST /backtest`

**Files:**
- Create: `tests/integration/test_backtest_endpoint.py`

- [ ] **Step 1: Write the integration test**

Create `tests/integration/test_backtest_endpoint.py`:

```python
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app
from schemas.backtest import BacktestResult
from schemas.state import AnalysisState, CouncilOutput


def _mock_ingest(state: AnalysisState) -> AnalysisState:
    state.market_data = {t: {"fundamentals": None, "ohlcv": None} for t in state.ticker_universe}
    state.rotation = {t: {"quadrant": "Leading"} for t in state.ticker_universe}
    state.divergence_score = 0.2
    return state


def _mock_council(state: AnalysisState) -> AnalysisState:
    state.council_outputs = [
        CouncilOutput(persona="Contrarian", stance="bullish", rationale="test", confidence=0.7),
        CouncilOutput(persona="FirstPrinciples", stance="bullish", rationale="test", confidence=0.7),
        CouncilOutput(persona="Momentum", stance="bullish", rationale="test", confidence=0.7),
        CouncilOutput(persona="Quant", stance="bullish", rationale="test", confidence=0.7),
        CouncilOutput(persona="Macro", stance="bullish", rationale="test", confidence=0.7),
    ]
    state.confidence = 0.7
    return state


@pytest.mark.asyncio
async def test_backtest_endpoint_returns_200() -> None:
    with (
        patch("worker.backtest.runner.ingest_all_data", new_callable=AsyncMock) as p_ingest,
        patch("worker.backtest.runner.compute_features", new_callable=AsyncMock) as p_feat,
        patch("worker.backtest.runner.compute_divergence_node", new_callable=AsyncMock) as p_div,
        patch("worker.backtest.runner.normalize_and_validate", new_callable=AsyncMock) as p_norm,
        patch("worker.backtest.runner.run_council", new_callable=AsyncMock) as p_council,
        patch("worker.backtest.runner.fetch_outcomes", new_callable=AsyncMock) as p_outcomes,
        patch("worker.backtest.runner.save_results") as p_save,
    ):
        p_ingest.side_effect = _mock_ingest
        p_feat.side_effect = lambda s: s
        p_div.side_effect = lambda s: s
        p_norm.side_effect = lambda s: s
        p_council.side_effect = _mock_council
        p_outcomes.return_value = {30: 0.05, 90: -0.02, 180: 0.08}
        p_save.return_value = "/tmp/test_result.json"

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/backtest",
                json={
                    "tickers": ["RELIANCE.NS"],
                    "start_date": "2022-01-03",
                    "end_date": "2022-01-03",
                    "horizons_days": [30, 90, 180],
                    "frequency": "monthly",
                    "fast_mode": False,
                },
            )

    assert r.status_code == 200


@pytest.mark.asyncio
async def test_backtest_endpoint_returns_predictions_list() -> None:
    with (
        patch("worker.backtest.runner.ingest_all_data", new_callable=AsyncMock) as p_ingest,
        patch("worker.backtest.runner.compute_features", new_callable=AsyncMock) as p_feat,
        patch("worker.backtest.runner.compute_divergence_node", new_callable=AsyncMock) as p_div,
        patch("worker.backtest.runner.normalize_and_validate", new_callable=AsyncMock) as p_norm,
        patch("worker.backtest.runner.run_council", new_callable=AsyncMock) as p_council,
        patch("worker.backtest.runner.fetch_outcomes", new_callable=AsyncMock) as p_outcomes,
        patch("worker.backtest.runner.save_results") as p_save,
    ):
        p_ingest.side_effect = _mock_ingest
        p_feat.side_effect = lambda s: s
        p_div.side_effect = lambda s: s
        p_norm.side_effect = lambda s: s
        p_council.side_effect = _mock_council
        p_outcomes.return_value = {30: 0.04}
        p_save.return_value = "/tmp/test_result.json"

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/backtest",
                json={
                    "tickers": ["TCS.NS"],
                    "start_date": "2022-01-03",
                    "end_date": "2022-01-03",
                    "horizons_days": [30],
                    "frequency": "monthly",
                    "fast_mode": False,
                },
            )
    body = r.json()
    assert isinstance(body["predictions"], list)
    assert len(body["predictions"]) == 1
    assert body["predictions"][0]["stance"] == "bullish"


@pytest.mark.asyncio
async def test_backtest_endpoint_returns_metrics_dict() -> None:
    with (
        patch("worker.backtest.runner.ingest_all_data", new_callable=AsyncMock) as p_ingest,
        patch("worker.backtest.runner.compute_features", new_callable=AsyncMock) as p_feat,
        patch("worker.backtest.runner.compute_divergence_node", new_callable=AsyncMock) as p_div,
        patch("worker.backtest.runner.normalize_and_validate", new_callable=AsyncMock) as p_norm,
        patch("worker.backtest.runner.run_council", new_callable=AsyncMock) as p_council,
        patch("worker.backtest.runner.fetch_outcomes", new_callable=AsyncMock) as p_outcomes,
        patch("worker.backtest.runner.save_results") as p_save,
    ):
        p_ingest.side_effect = _mock_ingest
        p_feat.side_effect = lambda s: s
        p_div.side_effect = lambda s: s
        p_norm.side_effect = lambda s: s
        p_council.side_effect = _mock_council
        p_outcomes.return_value = {30: 0.04}
        p_save.return_value = "/tmp/test_result.json"

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/backtest",
                json={
                    "tickers": ["INFY.NS"],
                    "start_date": "2022-01-03",
                    "end_date": "2022-01-03",
                    "horizons_days": [30],
                },
            )
    body = r.json()
    assert isinstance(body["metrics"], dict)
    assert "hit_rate_30d" in body["metrics"]


@pytest.mark.asyncio
async def test_backtest_endpoint_returns_output_file() -> None:
    with (
        patch("worker.backtest.runner.ingest_all_data", new_callable=AsyncMock) as p_ingest,
        patch("worker.backtest.runner.compute_features", new_callable=AsyncMock) as p_feat,
        patch("worker.backtest.runner.compute_divergence_node", new_callable=AsyncMock) as p_div,
        patch("worker.backtest.runner.normalize_and_validate", new_callable=AsyncMock) as p_norm,
        patch("worker.backtest.runner.run_council", new_callable=AsyncMock) as p_council,
        patch("worker.backtest.runner.fetch_outcomes", new_callable=AsyncMock) as p_outcomes,
        patch("worker.backtest.runner.save_results") as p_save,
    ):
        p_ingest.side_effect = _mock_ingest
        p_feat.side_effect = lambda s: s
        p_div.side_effect = lambda s: s
        p_norm.side_effect = lambda s: s
        p_council.side_effect = _mock_council
        p_outcomes.return_value = {30: 0.04}
        p_save.return_value = "/tmp/backtest_abc.json"

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/backtest",
                json={
                    "tickers": ["WIPRO.NS"],
                    "start_date": "2022-01-03",
                    "end_date": "2022-01-03",
                    "horizons_days": [30],
                },
            )
    body = r.json()
    assert body["output_file"] == "/tmp/backtest_abc.json"
```

- [ ] **Step 2: Run the integration test**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run pytest tests/integration/test_backtest_endpoint.py -v
```
Expected: All 4 tests PASS.

- [ ] **Step 3: Commit**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && git add tests/integration/test_backtest_endpoint.py && git commit -m "test(backtest): integration test for POST /backtest endpoint"
```

---

### Task 10: Full Suite Verification

- [ ] **Step 1: Run all tests**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run pytest tests/ -v --tb=short 2>&1 | tail -40
```
Expected: All tests green (count should be previous total + new Phase 6 tests).

- [ ] **Step 2: Run ruff lint**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run ruff check .
```
Expected: No errors. If errors, run `uv run ruff check . --fix` then fix remaining manually.

- [ ] **Step 3: Run mypy**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && uv run mypy libs/ services/ --ignore-missing-imports 2>&1 | tail -20
```
Expected: No errors.

- [ ] **Step 4: Final commit**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && git add -A && git status
```
Confirm only expected files are staged, then:
```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI" && git commit -m "chore: Phase 6 complete — backtesting harness, CLI, POST /backtest, all tests green" --allow-empty-message || true
```
(Only run if there are uncommitted changes from the lint/mypy fix step.)

---

## Verification Summary

| Check | Command | Expected |
|---|---|---|
| All tests | `uv run pytest tests/ -v` | All green |
| Lint | `uv run ruff check .` | No errors |
| Types | `uv run mypy libs/ services/ --ignore-missing-imports` | No errors |
| API import | `python -c "from api.main import app"` | No error |
| CLI help | `python -m worker.backtest --help` | Prints usage |

## Phase Exit Criteria

- `POST /backtest` returns 200 with `predictions` list, `metrics` dict, `output_file` path
- CLI `python -m worker.backtest` prints summary and writes JSON
- `hit_rate_30d`, `confidence_calibration_30d`, `persona_accuracy_30d`, `divergence_correlation_30d` all in `metrics`
- `as_of_date=None` on live `POST /analyze` — no behaviour change
- All unit + integration tests pass
- `ruff check .` clean, `mypy` clean
