# Phase 2: Feature Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `libs/features/` — a pure Python feature engineering library with an RRG engine, FII/DII flow strength metrics, IPO GMP disagreement scoring, and a multi-signal divergence detector — all as stateless transforms on top of the Phase 1 connector layer.

**Architecture:** Pure stateless functions in `libs/features/` accept pandas DataFrames and typed dicts, return Pydantic models defined in `libs/schemas/schemas/features.py`. No I/O, no LLM calls inside feature modules. A new `IPOGMPConnector` in `libs/connectors/` handles scraping. LangGraph nodes (Phase 3) will call these functions after fetching connector data.

**Tech Stack:** Python 3.11+, pandas 2.2, numpy 1.26, httpx, beautifulsoup4, pydantic v2, uv workspaces, pytest + pytest-asyncio.

---

## File Map

```
libs/features/                             NEW workspace member
├── pyproject.toml
└── features/
    ├── __init__.py
    ├── rrg.py                             RRG engine — RS ratio, momentum, quadrant
    ├── fii_dii.py                         Flow z-score, ratio, streak metrics
    ├── ipo_gmp.py                         GMP disagreement score (pure math)
    └── divergence.py                      Binary flags + weighted divergence score

libs/schemas/schemas/
├── features.py                            NEW — typed output models for all feature modules
├── state.py                               MODIFY — add divergence_score: float field
└── __init__.py                            MODIFY — export new types

libs/connectors/connectors/
└── ipo_gmp.py                             NEW — httpx + BS4 scraper for ipowatch.in

pyproject.toml                             MODIFY — add features workspace member

tests/unit/features/                       NEW directory
├── __init__.py
├── test_rrg.py
├── test_fii_dii_features.py
├── test_ipo_gmp_features.py
└── test_divergence.py

tests/unit/connectors/
└── test_ipo_gmp_connector.py              NEW
```

---

### Task 1: `libs/features` Workspace Scaffold + Feature Schemas

**Files:**
- Create: `libs/features/pyproject.toml`
- Create: `libs/features/features/__init__.py`
- Create: `libs/schemas/schemas/features.py`
- Modify: `libs/schemas/schemas/state.py`
- Modify: `libs/schemas/schemas/__init__.py`
- Modify: `pyproject.toml`
- Create: `tests/unit/features/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI"
mkdir -p libs/features/features
mkdir -p tests/unit/features
touch libs/features/features/__init__.py
touch tests/unit/features/__init__.py
```

- [ ] **Step 2: Create `libs/features/pyproject.toml`**

```toml
[project]
name = "features"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "schemas",
    "pandas>=2.2",
    "numpy>=1.26",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv.sources]
schemas = { workspace = true }
```

- [ ] **Step 3: Add `features` to root `pyproject.toml`**

Open `pyproject.toml` and make the following three additions:

```toml
[project]
name = "pulsealpha-ai"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "schemas",
  "connectors",
  "features",
  "api",
  "worker",
]

[tool.uv.sources]
schemas = { workspace = true }
connectors = { workspace = true }
features = { workspace = true }
api = { workspace = true }
worker = { workspace = true }

[tool.uv.workspace]
members = [
  "libs/schemas",
  "libs/connectors",
  "libs/features",
  "services/api",
  "services/worker",
]
```

- [ ] **Step 4: Write failing schema test**

Create `tests/unit/features/test_schemas.py`:

```python
from datetime import date
from schemas.features import (
    RRGPoint, RRGResult,
    FlowStrengthResult,
    IPOGMPResult,
    DivergenceResult,
)
from schemas.state import AnalysisState


def test_rrg_point_quadrant_literal():
    p = RRGPoint(
        ticker="RELIANCE.NS",
        rs_ratio=105.0,
        rs_momentum=1.5,
        quadrant="Leading",
        benchmark="^NSEI",
        as_of=date.today(),
    )
    assert p.quadrant == "Leading"


def test_rrg_result_holds_points():
    r = RRGResult(points=[], smoothing=10, momentum_lag=1)
    assert r.points == []


def test_flow_strength_result_fields():
    f = FlowStrengthResult(
        as_of=date.today(),
        fii_zscore=1.2,
        fii_ratio=0.3,
        fii_streak=5,
        dii_zscore=-0.4,
        dii_ratio=-0.1,
        dii_streak=-2,
        net_institutional=1500.0,
    )
    assert f.fii_streak == 5
    assert f.dii_streak == -2


def test_ipo_gmp_result_fields():
    r = IPOGMPResult(
        company_name="Test IPO",
        issue_price=500.0,
        gmp=75.0,
        gmp_implied_return=0.15,
        institutional_signal=0.8,
        retail_signal=0.6,
        disagreement_score=0.35,
        data_available=True,
    )
    assert r.data_available is True


def test_divergence_result_score_bounded():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        DivergenceResult(
            divergence_score=1.5,  # exceeds 1.0
            contradictions=[],
            majority_direction="bullish",
            signal_votes={},
        )


def test_analysis_state_has_divergence_score():
    state = AnalysisState(
        user_query="Analyze RELIANCE.NS",
        ticker_universe=["RELIANCE.NS"],
    )
    assert state.divergence_score == 0.0
```

- [ ] **Step 5: Run to confirm failure**

```bash
uv run pytest tests/unit/features/test_schemas.py -v
```
Expected: `ModuleNotFoundError: No module named 'schemas.features'`

- [ ] **Step 6: Create `libs/schemas/schemas/features.py`**

```python
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class RRGPoint(BaseModel):
    ticker: str
    rs_ratio: float
    rs_momentum: float
    quadrant: Literal["Leading", "Weakening", "Lagging", "Improving"]
    benchmark: str
    as_of: date


class RRGResult(BaseModel):
    points: list[RRGPoint]
    smoothing: int
    momentum_lag: int


class FlowStrengthResult(BaseModel):
    as_of: date
    fii_zscore: float
    fii_ratio: float
    fii_streak: int       # positive = buying streak, negative = selling streak
    dii_zscore: float
    dii_ratio: float
    dii_streak: int
    net_institutional: float


class IPOGMPResult(BaseModel):
    company_name: str
    issue_price: float
    gmp: float
    gmp_implied_return: float
    institutional_signal: float
    retail_signal: float
    disagreement_score: float
    data_available: bool


class DivergenceResult(BaseModel):
    divergence_score: float = Field(ge=0.0, le=1.0)
    contradictions: list[str]
    majority_direction: Literal["bullish", "bearish", "neutral"]
    signal_votes: dict[str, str]
```

- [ ] **Step 7: Add `divergence_score` to `libs/schemas/schemas/state.py`**

In `libs/schemas/schemas/state.py`, add `divergence_score` to `AnalysisState` after the `confidence` field:

```python
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    divergence_score: float = Field(default=0.0, ge=0.0, le=1.0)
```

- [ ] **Step 8: Update `libs/schemas/schemas/__init__.py`**

```python
from .connectors import ConnectorError, ConnectorResult
from .features import (
    DivergenceResult,
    FlowStrengthResult,
    IPOGMPResult,
    RRGPoint,
    RRGResult,
)
from .models import ModelTier, RoutingConfig
from .state import AnalysisState, AuditEntry, Citation, CouncilOutput

__all__ = [
    "AnalysisState",
    "AuditEntry",
    "CouncilOutput",
    "Citation",
    "ConnectorResult",
    "ConnectorError",
    "ModelTier",
    "RoutingConfig",
    "RRGPoint",
    "RRGResult",
    "FlowStrengthResult",
    "IPOGMPResult",
    "DivergenceResult",
]
```

- [ ] **Step 9: Sync workspace**

```bash
uv sync --all-extras
```
Expected: `features` package resolved and installed.

- [ ] **Step 10: Run schema tests**

```bash
uv run pytest tests/unit/features/test_schemas.py -v
```
Expected: All 6 tests PASS.

- [ ] **Step 11: Verify existing schema tests still pass**

```bash
uv run pytest tests/unit/schemas/ -v
```
Expected: All tests PASS (divergence_score default=0.0 is backwards-compatible).

- [ ] **Step 12: Commit**

```bash
git add libs/features/ libs/schemas/ tests/unit/features/ pyproject.toml
git commit -m "feat(schemas): add features.py types and divergence_score to AnalysisState; scaffold libs/features workspace"
```

---

### Task 2: RRG Engine

**Files:**
- Create: `libs/features/features/rrg.py`
- Create: `tests/unit/features/test_rrg.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/features/test_rrg.py`:

```python
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from features.rrg import SECTOR_INDEX_MAP, compute_rrg
from schemas.features import RRGResult


def make_price_df(n: int = 60, trend: float = 1.002) -> pd.DataFrame:
    """Synthetic price series trending at `trend` per day."""
    prices = [100.0 * (trend**i) for i in range(n)]
    return pd.DataFrame({"close": prices})


def make_flat_benchmark(n: int = 60) -> pd.DataFrame:
    return pd.DataFrame({"close": [100.0] * n})


def test_rrg_leading_quadrant() -> None:
    """Ticker outperforming flat benchmark and accelerating → Leading."""
    result = compute_rrg(
        prices={"RELIANCE.NS": make_price_df(trend=1.003)},
        benchmark_df=make_flat_benchmark(),
    )
    assert len(result.points) == 1
    p = result.points[0]
    assert p.quadrant == "Leading"
    assert p.rs_ratio > 100.0


def test_rrg_lagging_quadrant() -> None:
    """Ticker underperforming → Lagging."""
    result = compute_rrg(
        prices={"WEAK.NS": make_price_df(trend=0.997)},
        benchmark_df=make_flat_benchmark(),
    )
    assert result.points[0].quadrant == "Lagging"
    assert result.points[0].rs_ratio < 100.0


def test_rrg_skips_ticker_with_insufficient_history() -> None:
    """Fewer rows than smoothing + momentum_lag + 5 → ticker excluded from result."""
    short_df = pd.DataFrame({"close": [100.0] * 5})
    result = compute_rrg(
        prices={"SHORT.NS": short_df},
        benchmark_df=make_flat_benchmark(),
        smoothing=10,
        momentum_lag=1,
    )
    assert len(result.points) == 0


def test_rrg_benchmark_ticker_stored_in_point() -> None:
    result = compute_rrg(
        prices={"TCS.NS": make_price_df()},
        benchmark_df=make_flat_benchmark(),
        benchmark_ticker="^NSEBANK",
    )
    assert result.points[0].benchmark == "^NSEBANK"


def test_rrg_result_metadata() -> None:
    result = compute_rrg(
        prices={"INFY.NS": make_price_df()},
        benchmark_df=make_flat_benchmark(),
        smoothing=10,
        momentum_lag=1,
    )
    assert result.smoothing == 10
    assert result.momentum_lag == 1
    assert isinstance(result.points[0].as_of, date)


def test_rrg_multiple_tickers() -> None:
    result = compute_rrg(
        prices={
            "A.NS": make_price_df(trend=1.002),
            "B.NS": make_price_df(trend=0.998),
        },
        benchmark_df=make_flat_benchmark(),
    )
    assert len(result.points) == 2
    tickers = {p.ticker for p in result.points}
    assert tickers == {"A.NS", "B.NS"}


def test_sector_index_map_known_sectors() -> None:
    assert "Financial Services" in SECTOR_INDEX_MAP
    assert SECTOR_INDEX_MAP["Financial Services"] == "^NSEBANK"
    assert "Information Technology" in SECTOR_INDEX_MAP


def test_sector_index_map_fallback_for_unknown() -> None:
    assert SECTOR_INDEX_MAP.get("Unknown Sector XYZ", "^NSEI") == "^NSEI"
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/unit/features/test_rrg.py -v
```
Expected: `ModuleNotFoundError: No module named 'features.rrg'`

- [ ] **Step 3: Implement `libs/features/features/rrg.py`**

```python
from __future__ import annotations

from datetime import date
from typing import Literal

import pandas as pd

from schemas.features import RRGPoint, RRGResult

SECTOR_INDEX_MAP: dict[str, str] = {
    "Financial Services": "^NSEBANK",
    "Information Technology": "^CNXIT",
    "Pharmaceuticals": "^CNXPHARMA",
    "Healthcare": "^CNXPHARMA",
    "Energy": "^CNXENERGY",
    "Utilities": "^CNXENERGY",
    "Consumer Defensive": "^CNXFMCG",
    "Consumer Cyclical": "^CNXFMCG",
    "Basic Materials": "^CNXMETAL",
    "Industrials": "^CNXINFRA",
    "Real Estate": "^CNXREALTY",
    "Communication Services": "^CNXMEDIA",
}

_Quadrant = Literal["Leading", "Weakening", "Lagging", "Improving"]


def _classify(rs_ratio: float, rs_momentum: float) -> _Quadrant:
    if rs_ratio > 100.0 and rs_momentum > 0.0:
        return "Leading"
    elif rs_ratio > 100.0:
        return "Weakening"
    elif rs_momentum > 0.0:
        return "Improving"
    return "Lagging"


def compute_rrg(
    prices: dict[str, pd.DataFrame],
    benchmark_df: pd.DataFrame,
    smoothing: int = 10,
    momentum_lag: int = 1,
    benchmark_ticker: str = "^NSEI",
) -> RRGResult:
    """Compute Relative Rotation Graph positions for a universe of tickers.

    Args:
        prices: Dict of ticker → DataFrame with a 'close' column, sorted ascending.
        benchmark_df: DataFrame with a 'close' column for the benchmark index.
        smoothing: EMA span applied to both RS ratio and RS momentum.
        momentum_lag: Shift period for the rate-of-change calculation.
        benchmark_ticker: Label stored in each RRGPoint (does not fetch data).

    Returns:
        RRGResult with one RRGPoint per ticker that had sufficient history.
        Tickers with fewer than (smoothing + momentum_lag + 5) rows are skipped.
    """
    min_rows = smoothing + momentum_lag + 5
    points: list[RRGPoint] = []

    for ticker, df in prices.items():
        n = min(len(df), len(benchmark_df))
        if n < min_rows:
            continue

        ticker_close = df["close"].iloc[-n:].reset_index(drop=True)
        bench_close = benchmark_df["close"].iloc[-n:].reset_index(drop=True)

        # Step 1 — smooth the raw RS ratio first (common bug: ROC before EMA)
        raw_rs = ticker_close / bench_close * 100.0
        rs_ratio = raw_rs.ewm(span=smoothing, adjust=False).mean()

        # Step 2 — compute ROC on the smoothed ratio, then smooth again
        raw_momentum = (rs_ratio / rs_ratio.shift(momentum_lag) - 1.0) * 100.0
        rs_momentum = raw_momentum.ewm(span=smoothing, adjust=False).mean()

        latest_ratio = float(rs_ratio.iloc[-1])
        latest_momentum = float(rs_momentum.iloc[-1])

        points.append(
            RRGPoint(
                ticker=ticker,
                rs_ratio=latest_ratio,
                rs_momentum=latest_momentum,
                quadrant=_classify(latest_ratio, latest_momentum),
                benchmark=benchmark_ticker,
                as_of=date.today(),
            )
        )

    return RRGResult(points=points, smoothing=smoothing, momentum_lag=momentum_lag)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/features/test_rrg.py -v
```
Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add libs/features/features/rrg.py tests/unit/features/test_rrg.py
git commit -m "feat(features): RRG engine with corrected EMA-first momentum formula"
```

---

### Task 3: FII/DII Flow Strength

**Files:**
- Create: `libs/features/features/fii_dii.py`
- Create: `tests/unit/features/test_fii_dii_features.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/features/test_fii_dii_features.py`:

```python
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from features.fii_dii import compute_flow_strength
from schemas.features import FlowStrengthResult


def make_flow_df(
    n: int = 25,
    fii_net: float = 1000.0,
    dii_net: float = -500.0,
    fii_buy: float = 5000.0,
    dii_buy: float = 3000.0,
) -> pd.DataFrame:
    """Constant-value flow DataFrame for deterministic tests."""
    return pd.DataFrame(
        {
            "fii_net": [fii_net] * n,
            "fii_buy": [fii_buy] * n,
            "fii_sell": [fii_buy - fii_net] * n,
            "dii_net": [dii_net] * n,
            "dii_buy": [dii_buy] * n,
            "dii_sell": [dii_buy - dii_net] * n,
        }
    )


def test_flow_strength_returns_result() -> None:
    result = compute_flow_strength(make_flow_df())
    assert isinstance(result, FlowStrengthResult)
    assert isinstance(result.as_of, date)


def test_flow_strength_zscore_zero_for_constant_series() -> None:
    """Constant series → std=0 → zscore must be 0.0, never NaN."""
    result = compute_flow_strength(make_flow_df(fii_net=1000.0))
    assert result.fii_zscore == 0.0


def test_flow_strength_ratio_in_range() -> None:
    result = compute_flow_strength(make_flow_df(fii_net=1000.0))
    assert -1.0 <= result.fii_ratio <= 1.0


def test_flow_strength_buying_streak() -> None:
    """All positive fii_net → streak equals number of rows."""
    result = compute_flow_strength(make_flow_df(n=25, fii_net=500.0))
    assert result.fii_streak == 25


def test_flow_strength_selling_streak() -> None:
    """All negative fii_net → streak is negative and equal to -n."""
    result = compute_flow_strength(make_flow_df(n=25, fii_net=-500.0))
    assert result.fii_streak == -25


def test_flow_strength_mixed_streak() -> None:
    """Last 3 days positive, preceded by negatives → streak = 3."""
    vals = [-100.0] * 22 + [200.0] * 3
    df = pd.DataFrame(
        {
            "fii_net": vals,
            "fii_buy": [5000.0] * 25,
            "fii_sell": [4000.0] * 25,
            "dii_net": [100.0] * 25,
            "dii_buy": [3000.0] * 25,
            "dii_sell": [2900.0] * 25,
        }
    )
    result = compute_flow_strength(df)
    assert result.fii_streak == 3


def test_flow_strength_insufficient_history_raises() -> None:
    df = make_flow_df(n=5)
    with pytest.raises(ValueError, match="at least"):
        compute_flow_strength(df, zscore_window=20)


def test_flow_strength_net_institutional() -> None:
    result = compute_flow_strength(make_flow_df(fii_net=1000.0, dii_net=-500.0))
    assert result.net_institutional == pytest.approx(500.0)
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/unit/features/test_fii_dii_features.py -v
```
Expected: `ModuleNotFoundError: No module named 'features.fii_dii'`

- [ ] **Step 3: Implement `libs/features/features/fii_dii.py`**

```python
from __future__ import annotations

from datetime import date

import pandas as pd

from schemas.features import FlowStrengthResult


def _streak(series: pd.Series) -> int:  # type: ignore[type-arg]
    """Count consecutive same-sign values at tail. Positive = buying, negative = selling."""
    if series.empty:
        return 0
    last_positive = float(series.iloc[-1]) > 0
    count = 0
    for val in reversed(series.tolist()):
        if (float(val) > 0) == last_positive:
            count += 1
        else:
            break
    return count if last_positive else -count


def _zscore(series: pd.Series, window: int) -> float:  # type: ignore[type-arg]
    """Rolling z-score of the last value. Returns 0.0 when std is zero."""
    rolling = series.rolling(window)
    mean = float(rolling.mean().iloc[-1])
    std = float(rolling.std().iloc[-1])
    if pd.isna(std) or std == 0.0:
        return 0.0
    return (float(series.iloc[-1]) - mean) / std


def _ratio(net: float, buy: float, sell: float) -> float:
    """Directional conviction: net / total_flow. Range [-1, 1]."""
    total = abs(buy) + abs(sell)
    return net / total if total > 0.0 else 0.0


def compute_flow_strength(
    flow_history: pd.DataFrame,
    zscore_window: int = 20,
) -> FlowStrengthResult:
    """Compute FII/DII flow strength metrics from a historical flow DataFrame.

    Args:
        flow_history: DataFrame with columns fii_net, fii_buy, fii_sell,
                      dii_net, dii_buy, dii_sell. Sorted ascending by date.
        zscore_window: Rolling window size for z-score normalisation.

    Returns:
        FlowStrengthResult for the most recent row.

    Raises:
        ValueError: If fewer rows than zscore_window are provided.
    """
    if len(flow_history) < zscore_window:
        raise ValueError(
            f"flow_history must have at least {zscore_window} rows, got {len(flow_history)}"
        )

    last = flow_history.iloc[-1]

    return FlowStrengthResult(
        as_of=date.today(),
        fii_zscore=_zscore(flow_history["fii_net"], zscore_window),
        fii_ratio=_ratio(float(last["fii_net"]), float(last["fii_buy"]), float(last["fii_sell"])),
        fii_streak=_streak(flow_history["fii_net"]),
        dii_zscore=_zscore(flow_history["dii_net"], zscore_window),
        dii_ratio=_ratio(float(last["dii_net"]), float(last["dii_buy"]), float(last["dii_sell"])),
        dii_streak=_streak(flow_history["dii_net"]),
        net_institutional=float(last["fii_net"]) + float(last["dii_net"]),
    )
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/features/test_fii_dii_features.py -v
```
Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add libs/features/features/fii_dii.py tests/unit/features/test_fii_dii_features.py
git commit -m "feat(features): FII/DII flow strength — z-score, ratio, streak metrics"
```

---

### Task 4: IPO GMP Connector

**Files:**
- Create: `libs/connectors/connectors/ipo_gmp.py`
- Create: `tests/unit/connectors/test_ipo_gmp_connector.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/connectors/test_ipo_gmp_connector.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from connectors.ipo_gmp import IPOGMPConnector

SAMPLE_HTML = """
<table>
  <tr>
    <th>Company</th><th>Issue Price</th><th>GMP</th>
    <th>QIB</th><th>HNI</th><th>Retail</th>
  </tr>
  <tr>
    <td>Reliance Infra IPO</td><td>500</td><td>75</td>
    <td>45.23</td><td>120.5</td><td>8.3</td>
  </tr>
  <tr>
    <td>SBI Life IPO</td><td>800</td><td>20</td>
    <td>5.1</td><td>3.2</td><td>1.1</td>
  </tr>
</table>
"""

NO_TABLE_HTML = "<html><body>No IPO data today</body></html>"


def _mock_client(html: str) -> MagicMock:
    resp = MagicMock()
    resp.text = html
    resp.raise_for_status = MagicMock()
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(return_value=resp)
    return client


@pytest.mark.asyncio
async def test_ipo_gmp_connector_parses_matching_ipo() -> None:
    with patch("connectors.ipo_gmp.httpx.AsyncClient", return_value=_mock_client(SAMPLE_HTML)):
        result = await IPOGMPConnector().fetch("Reliance")
    assert result.ok
    assert result.data["issue_price"] == 500.0
    assert result.data["gmp"] == 75.0
    assert result.data["qib_subscription"] == pytest.approx(45.23)


@pytest.mark.asyncio
async def test_ipo_gmp_connector_second_ipo_found() -> None:
    with patch("connectors.ipo_gmp.httpx.AsyncClient", return_value=_mock_client(SAMPLE_HTML)):
        result = await IPOGMPConnector().fetch("SBI")
    assert result.ok
    assert result.data["issue_price"] == 800.0
    assert result.data["gmp"] == 20.0


@pytest.mark.asyncio
async def test_ipo_gmp_connector_not_found_returns_error() -> None:
    with patch("connectors.ipo_gmp.httpx.AsyncClient", return_value=_mock_client(SAMPLE_HTML)):
        result = await IPOGMPConnector().fetch("NONEXISTENT_COMPANY")
    assert not result.ok
    assert result.error is not None
    assert result.error.code == "NOT_FOUND"
    assert result.error.retryable is False


@pytest.mark.asyncio
async def test_ipo_gmp_connector_parse_error_on_no_table() -> None:
    with patch("connectors.ipo_gmp.httpx.AsyncClient", return_value=_mock_client(NO_TABLE_HTML)):
        result = await IPOGMPConnector().fetch("Any")
    assert not result.ok
    assert result.error is not None
    assert result.error.code == "PARSE_ERROR"
    assert result.error.retryable is False
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/unit/connectors/test_ipo_gmp_connector.py -v
```
Expected: `ModuleNotFoundError: No module named 'connectors.ipo_gmp'`

- [ ] **Step 3: Implement `libs/connectors/connectors/ipo_gmp.py`**

```python
from __future__ import annotations

import logging
from typing import Any

import httpx
from bs4 import BeautifulSoup

from connectors.base import BaseConnector
from schemas.connectors import ConnectorError, ConnectorResult

logger = logging.getLogger(__name__)

_IPOWATCH_URL = "https://www.ipowatch.in/ipo-gmp/"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}


class _GmpError(Exception):
    """Internal exception carrying a ConnectorError code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class IPOGMPConnector(BaseConnector):
    """Scrapes ipowatch.in for live IPO GMP data.

    The `ticker` argument to `fetch()` is a company name substring used
    to filter the scraped table — not a stock ticker symbol.
    """

    def __init__(self) -> None:
        super().__init__(source_name="ipo_gmp_ipowatch", max_retries=3, timeout_seconds=15.0)

    async def _fetch(self, ticker: str) -> dict[str, Any]:
        # Not used — fetch() is overridden to handle non-exception None returns
        return {}

    async def fetch(self, ticker: str) -> ConnectorResult:  # type: ignore[override]
        try:
            async with httpx.AsyncClient(
                headers=_HEADERS, follow_redirects=True
            ) as client:
                r = await client.get(_IPOWATCH_URL, timeout=self.timeout_seconds)
                r.raise_for_status()
                data = self._parse(r.text, ticker)
        except _GmpError as exc:
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(code=exc.code, message=str(exc), retryable=False),
            )
        except Exception as exc:
            logger.warning("IPOGMPConnector unexpected error for %r: %s", ticker, exc)
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(code="FETCH_ERROR", message=str(exc), retryable=True),
            )
        return ConnectorResult(
            source=self.source_name,
            ticker=ticker,
            data=data,
            confidence=0.9,
        )

    def _parse(self, html: str, query: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            raise _GmpError("PARSE_ERROR", "No GMP table found on ipowatch page")

        for row in table.find_all("tr")[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 6:
                continue
            if query.lower() not in cells[0].lower():
                continue
            try:
                return {
                    "company_name": cells[0],
                    "issue_price": float(cells[1].replace(",", "")),
                    "gmp": float(cells[2].replace(",", "")),
                    "qib_subscription": float(cells[3].replace(",", "").rstrip("x")),
                    "hni_subscription": float(cells[4].replace(",", "").rstrip("x")),
                    "retail_subscription": float(cells[5].replace(",", "").rstrip("x")),
                }
            except (ValueError, IndexError):
                continue

        raise _GmpError("NOT_FOUND", f"No IPO matching {query!r} found in GMP table")
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/connectors/test_ipo_gmp_connector.py -v
```
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add libs/connectors/connectors/ipo_gmp.py tests/unit/connectors/test_ipo_gmp_connector.py
git commit -m "feat(connectors): IPOGMPConnector — httpx + BeautifulSoup scraper for ipowatch.in"
```

---

### Task 5: IPO GMP Feature (Disagreement Score)

**Files:**
- Create: `libs/features/features/ipo_gmp.py`
- Create: `tests/unit/features/test_ipo_gmp_features.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/features/test_ipo_gmp_features.py`:

```python
from __future__ import annotations

import pytest

from features.ipo_gmp import compute_gmp_disagreement
from schemas.connectors import ConnectorError, ConnectorResult
from schemas.features import IPOGMPResult


def make_ok_result(
    issue_price: float,
    gmp: float,
    qib: float,
    hni: float,
    retail: float,
) -> ConnectorResult:
    return ConnectorResult(
        source="ipo_gmp_ipowatch",
        ticker="TestIPO",
        data={
            "company_name": "Test IPO Ltd",
            "issue_price": issue_price,
            "gmp": gmp,
            "qib_subscription": qib,
            "hni_subscription": hni,
            "retail_subscription": retail,
        },
        confidence=0.9,
    )


def make_error_result() -> ConnectorResult:
    return ConnectorResult(
        source="ipo_gmp_ipowatch",
        ticker="FAIL",
        data={},
        confidence=0.0,
        error=ConnectorError(code="PARSE_ERROR", message="no table", retryable=False),
    )


def test_gmp_returns_none_when_connector_failed() -> None:
    assert compute_gmp_disagreement(make_error_result()) is None


def test_gmp_implied_return_correct() -> None:
    """gmp=100, issue_price=500 → implied_return=0.20"""
    result = compute_gmp_disagreement(
        make_ok_result(issue_price=500.0, gmp=100.0, qib=50.0, hni=30.0, retail=5.0)
    )
    assert result is not None
    assert result.gmp_implied_return == pytest.approx(0.20)


def test_gmp_disagreement_score_is_nonnegative_float() -> None:
    result = compute_gmp_disagreement(
        make_ok_result(issue_price=500.0, gmp=75.0, qib=40.0, hni=20.0, retail=5.0)
    )
    assert result is not None
    assert isinstance(result.disagreement_score, float)
    assert result.disagreement_score >= 0.0


def test_gmp_data_available_true_on_success() -> None:
    result = compute_gmp_disagreement(
        make_ok_result(issue_price=400.0, gmp=50.0, qib=10.0, hni=5.0, retail=2.0)
    )
    assert result is not None
    assert result.data_available is True


def test_gmp_high_disagreement_when_gmp_high_qib_low() -> None:
    """High GMP + minimal QIB → high disagreement vs low GMP + strong QIB."""
    high_conflict = compute_gmp_disagreement(
        make_ok_result(issue_price=500.0, gmp=250.0, qib=1.0, hni=1.0, retail=1.0)
    )
    low_conflict = compute_gmp_disagreement(
        make_ok_result(issue_price=500.0, gmp=25.0, qib=80.0, hni=50.0, retail=10.0)
    )
    assert high_conflict is not None and low_conflict is not None
    assert high_conflict.disagreement_score > low_conflict.disagreement_score


def test_gmp_with_qib_history_uses_percentile_normalization() -> None:
    """Passing qib_history changes the institutional_signal — result must not crash."""
    result = compute_gmp_disagreement(
        make_ok_result(issue_price=500.0, gmp=100.0, qib=30.0, hni=20.0, retail=5.0),
        qib_history=[10.0, 50.0, 100.0, 30.0, 20.0],
    )
    assert result is not None
    assert 0.0 <= result.institutional_signal <= 1.0
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/unit/features/test_ipo_gmp_features.py -v
```
Expected: `ModuleNotFoundError: No module named 'features.ipo_gmp'`

- [ ] **Step 3: Implement `libs/features/features/ipo_gmp.py`**

```python
from __future__ import annotations

import math

from schemas.connectors import ConnectorResult
from schemas.features import IPOGMPResult

# Upper bounds used when no historical data is provided for normalization.
_QIB_UPPER_BOUND = 100.0    # 100x QIB subscription treated as maximum
_RETAIL_UPPER_BOUND = 20.0  # 20x retail subscription treated as maximum


def compute_gmp_disagreement(
    connector_result: ConnectorResult,
    qib_history: list[float] | None = None,
) -> IPOGMPResult | None:
    """Compute GMP vs institutional demand disagreement score.

    Args:
        connector_result: Output from IPOGMPConnector.fetch(). Returns None
                          immediately if result.ok is False.
        qib_history: Historical QIB subscription multiples for percentile
                     normalization. Falls back to log-scale with a fixed upper
                     bound when None.

    Returns:
        IPOGMPResult with disagreement_score, or None if data unavailable.
    """
    if not connector_result.ok:
        return None

    data = connector_result.data
    issue_price = float(data["issue_price"])
    gmp = float(data["gmp"])
    qib = float(data["qib_subscription"])
    hni = float(data.get("hni_subscription", 1.0))
    retail = float(data.get("retail_subscription", 1.0))

    gmp_implied_return = gmp / issue_price if issue_price > 0.0 else 0.0

    if qib_history and len(qib_history) > 0:
        max_qib = max(qib_history)
        institutional_signal = (
            math.log1p(qib) / math.log1p(max_qib) if max_qib > 0.0 else 0.0
        )
        retail_signal = (
            math.log1p(retail) / math.log1p(max_qib) if max_qib > 0.0 else 0.0
        )
    else:
        institutional_signal = min(
            math.log1p(qib) / math.log1p(_QIB_UPPER_BOUND), 1.0
        )
        retail_signal = min(
            math.log1p(retail) / math.log1p(_RETAIL_UPPER_BOUND), 1.0
        )

    return IPOGMPResult(
        company_name=str(data.get("company_name", "")),
        issue_price=issue_price,
        gmp=gmp,
        gmp_implied_return=gmp_implied_return,
        institutional_signal=institutional_signal,
        retail_signal=retail_signal,
        disagreement_score=abs(gmp_implied_return - institutional_signal),
        data_available=True,
    )
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/features/test_ipo_gmp_features.py -v
```
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add libs/features/features/ipo_gmp.py tests/unit/features/test_ipo_gmp_features.py
git commit -m "feat(features): IPO GMP disagreement score with log-scale normalization"
```

---

### Task 6: Divergence Detector

**Files:**
- Create: `libs/features/features/divergence.py`
- Create: `tests/unit/features/test_divergence.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/features/test_divergence.py`:

```python
from __future__ import annotations

from datetime import date

import pytest

from features.divergence import compute_divergence
from schemas.features import DivergenceResult, FlowStrengthResult, IPOGMPResult, RRGPoint


def make_rrg(quadrant: str) -> RRGPoint:
    rs_ratio = 105.0 if quadrant in ("Leading", "Weakening") else 95.0
    rs_momentum = 1.0 if quadrant in ("Leading", "Improving") else -1.0
    return RRGPoint(
        ticker="TEST.NS",
        rs_ratio=rs_ratio,
        rs_momentum=rs_momentum,
        quadrant=quadrant,  # type: ignore[arg-type]
        benchmark="^NSEI",
        as_of=date.today(),
    )


def make_flow(
    fii_zscore: float = 1.0,
    fii_ratio: float = 0.3,
    dii_zscore: float = 0.8,
    dii_ratio: float = 0.2,
) -> FlowStrengthResult:
    return FlowStrengthResult(
        as_of=date.today(),
        fii_zscore=fii_zscore,
        fii_ratio=fii_ratio,
        fii_streak=5,
        dii_zscore=dii_zscore,
        dii_ratio=dii_ratio,
        dii_streak=3,
        net_institutional=1500.0,
    )


def test_full_bullish_consensus_score_zero() -> None:
    result = compute_divergence(
        rrg=make_rrg("Leading"),
        flow=make_flow(fii_zscore=1.0, fii_ratio=0.3, dii_zscore=0.8, dii_ratio=0.2),
        sentiment_polarity=0.5,
    )
    assert result.divergence_score == pytest.approx(0.0)
    assert result.majority_direction == "bullish"
    assert result.contradictions == []


def test_rrg_outlier_raises_score() -> None:
    """RRG=Lagging but all flow signals bullish → nonzero score."""
    result = compute_divergence(
        rrg=make_rrg("Lagging"),
        flow=make_flow(fii_zscore=1.5, fii_ratio=0.4, dii_zscore=1.2, dii_ratio=0.3),
        sentiment_polarity=0.6,
    )
    assert result.divergence_score > 0.0
    assert result.signal_votes["rrg"] == "bearish"
    assert result.majority_direction == "bullish"


def test_neutral_signals_excluded_from_contradictions() -> None:
    """Near-zero flow + neutral sentiment → only RRG vote is non-neutral."""
    result = compute_divergence(
        rrg=make_rrg("Leading"),
        flow=make_flow(fii_zscore=0.1, fii_ratio=0.05, dii_zscore=0.1, dii_ratio=0.05),
        sentiment_polarity=0.0,
    )
    # Only RRG is bullish; others are neutral — no contradictions
    assert result.contradictions == []


def test_gmp_none_excluded_from_votes() -> None:
    result = compute_divergence(
        rrg=make_rrg("Leading"),
        flow=make_flow(),
        sentiment_polarity=0.3,
        gmp=None,
    )
    assert isinstance(result, DivergenceResult)
    assert "gmp" not in result.signal_votes


def test_contradictions_contain_conflicts_with_phrase() -> None:
    result = compute_divergence(
        rrg=make_rrg("Lagging"),
        flow=make_flow(fii_zscore=1.5, fii_ratio=0.4, dii_zscore=0.0, dii_ratio=0.0),
        sentiment_polarity=0.5,
    )
    for c in result.contradictions:
        assert "conflicts with" in c


def test_divergence_score_bounded_to_one() -> None:
    """Score must never exceed 1.0 regardless of weight configuration."""
    result = compute_divergence(
        rrg=make_rrg("Lagging"),
        flow=make_flow(fii_zscore=-1.5, fii_ratio=-0.4, dii_zscore=-1.2, dii_ratio=-0.3),
        sentiment_polarity=-0.6,
    )
    assert result.divergence_score <= 1.0


def test_signal_votes_contains_all_expected_keys() -> None:
    result = compute_divergence(
        rrg=make_rrg("Leading"),
        flow=make_flow(),
        sentiment_polarity=0.2,
    )
    expected_keys = {"rrg", "fii_zscore", "fii_ratio", "dii_zscore", "sentiment"}
    assert expected_keys.issubset(result.signal_votes.keys())
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/unit/features/test_divergence.py -v
```
Expected: `ModuleNotFoundError: No module named 'features.divergence'`

- [ ] **Step 3: Implement `libs/features/features/divergence.py`**

```python
from __future__ import annotations

from typing import Literal

from schemas.features import DivergenceResult, FlowStrengthResult, IPOGMPResult, RRGPoint

_Direction = Literal["bullish", "bearish", "neutral"]

_WEIGHTS: dict[str, float] = {
    "rrg": 0.30,
    "fii_zscore": 0.25,
    "fii_ratio": 0.15,
    "dii_zscore": 0.15,
    "sentiment": 0.15,
}

_ZSCORE_THRESHOLD = 0.5
_RATIO_THRESHOLD = 0.1
_SENTIMENT_THRESHOLD = 0.1


def _rrg_vote(point: RRGPoint) -> _Direction:
    if point.quadrant in ("Leading", "Improving"):
        return "bullish"
    elif point.quadrant in ("Lagging", "Weakening"):
        return "bearish"
    return "neutral"


def _zscore_vote(z: float) -> _Direction:
    if z > _ZSCORE_THRESHOLD:
        return "bullish"
    elif z < -_ZSCORE_THRESHOLD:
        return "bearish"
    return "neutral"


def _ratio_vote(r: float) -> _Direction:
    if r > _RATIO_THRESHOLD:
        return "bullish"
    elif r < -_RATIO_THRESHOLD:
        return "bearish"
    return "neutral"


def _sentiment_vote(polarity: float) -> _Direction:
    if polarity > _SENTIMENT_THRESHOLD:
        return "bullish"
    elif polarity < -_SENTIMENT_THRESHOLD:
        return "bearish"
    return "neutral"


def _majority(votes: dict[str, str]) -> _Direction:
    non_neutral = [v for v in votes.values() if v != "neutral"]
    if not non_neutral:
        return "neutral"
    bullish = sum(1 for v in non_neutral if v == "bullish")
    bearish = len(non_neutral) - bullish
    return "bullish" if bullish >= bearish else "bearish"


def _build_contradictions(votes: dict[str, str], majority_dir: str) -> list[str]:
    """Deduplicated human-readable conflict strings for signals disagreeing with majority."""
    outliers = {s: v for s, v in votes.items() if v != "neutral" and v != majority_dir}
    aligned = {s: v for s, v in votes.items() if v != "neutral" and v == majority_dir}

    seen: set[frozenset[str]] = set()
    result: list[str] = []

    for out_signal, out_vote in outliers.items():
        for aln_signal, aln_vote in aligned.items():
            key = frozenset({out_signal, aln_signal})
            if key not in seen:
                seen.add(key)
                result.append(f"{out_signal}={out_vote} conflicts with {aln_signal}={aln_vote}")

    return result


def compute_divergence(
    rrg: RRGPoint,
    flow: FlowStrengthResult,
    sentiment_polarity: float,
    gmp: IPOGMPResult | None = None,
) -> DivergenceResult:
    """Detect conflicts across technical, flow, and sentiment signals.

    Args:
        rrg: RRGPoint for the ticker (single ticker's latest quadrant position).
        flow: FII/DII flow strength metrics for the current session.
        sentiment_polarity: Aggregate sentiment polarity float in [-1, 1].
        gmp: IPO GMP result (optional). Excluded from votes when None.

    Returns:
        DivergenceResult with score [0, 1], contradiction strings, and signal votes.
    """
    votes: dict[str, str] = {
        "rrg": _rrg_vote(rrg),
        "fii_zscore": _zscore_vote(flow.fii_zscore),
        "fii_ratio": _ratio_vote(flow.fii_ratio),
        "dii_zscore": _zscore_vote(flow.dii_zscore),
        "sentiment": _sentiment_vote(sentiment_polarity),
    }

    majority_dir = _majority(votes)

    # Weighted score: sum weights of signals conflicting with majority
    score = sum(
        _WEIGHTS.get(signal, 0.0)
        for signal, vote in votes.items()
        if vote != "neutral" and vote != majority_dir
    )

    contradictions = _build_contradictions(votes, majority_dir)

    return DivergenceResult(
        divergence_score=min(score, 1.0),
        contradictions=contradictions,
        majority_direction=majority_dir,
        signal_votes=votes,
    )
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/features/test_divergence.py -v
```
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add libs/features/features/divergence.py tests/unit/features/test_divergence.py
git commit -m "feat(features): divergence detector — binary conflict flags and weighted score"
```

---

### Task 7: Full Suite Verification

- [ ] **Step 1: Run all unit tests**

```bash
uv run pytest tests/unit/ -v --tb=short
```
Expected: All green. Zero failures.

- [ ] **Step 2: Run integration tests**

```bash
uv run pytest tests/integration/ -v --tb=short
```
Expected: All green.

- [ ] **Step 3: Lint**

```bash
uv run ruff check .
```
Expected: No errors.

- [ ] **Step 4: Type check**

```bash
uv run mypy libs/ services/ --ignore-missing-imports
```
Expected: No errors (the `# type: ignore` comments in feature files are intentional — pandas Series generics and Literal assignment).

- [ ] **Step 5: Verify feature schemas are importable from root**

```bash
uv run python -c "
from schemas.features import RRGResult, FlowStrengthResult, IPOGMPResult, DivergenceResult
from schemas.state import AnalysisState
s = AnalysisState(user_query='test', ticker_universe=['RELIANCE.NS'])
print('divergence_score default:', s.divergence_score)
print('All imports OK')
"
```
Expected:
```
divergence_score default: 0.0
All imports OK
```

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: Phase 2 complete — feature engineering layer fully tested and green"
```

---

## Verification Summary

| Check | Command | Expected |
|-------|---------|---------|
| Feature unit tests | `uv run pytest tests/unit/features/ -v` | All green |
| Connector unit tests | `uv run pytest tests/unit/connectors/ -v` | All green |
| Schema unit tests | `uv run pytest tests/unit/schemas/ -v` | All green |
| Integration tests | `uv run pytest tests/integration/ -v` | All green |
| Lint | `uv run ruff check .` | No errors |
| Types | `uv run mypy libs/ services/ --ignore-missing-imports` | No errors |

## Phase Exit Criteria

- All feature unit tests pass with synthetic fixture data
- `compute_rrg` correctly classifies Leading quadrant for an outperforming ticker
- `compute_divergence` returns nonzero score when RRG contradicts flow signals
- `AnalysisState` validates with `divergence_score` field present

## Next Phase

Phase 3 (LangGraph Orchestration): Supervisor graph with deterministic edge logic, node-level contracts calling these feature functions, resume/retry from partial state. Requires a separate plan.
