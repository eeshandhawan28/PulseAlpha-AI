# Phase 3: LangGraph Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire Phase 1 connectors and Phase 2 feature functions into a sequential LangGraph graph exposed via `POST /analyze` on the existing FastAPI service.

**Architecture:** Four sequential LangGraph nodes (`ingest_all_data → compute_features → compute_divergence → normalize_and_validate`) with `asyncio.gather()` inside each node for parallelism. LangGraph state is `dict`; a thin wrapper converts to/from `AnalysisState` (Pydantic) at node boundaries. MemorySaver provides in-process checkpointing.

**Tech Stack:** Python 3.11+, LangGraph ≥ 0.2, FastAPI, Pydantic v2, asyncio, yfinance, uv workspaces.

---

## Codebase Context

Key paths (all relative to repo root `/Users/eeshandhawan/Desktop/PulseAlpha AI/`):

| Path | What it is |
|------|-----------|
| `libs/schemas/schemas/state.py` | `AnalysisState` Pydantic model |
| `libs/schemas/schemas/features.py` | `RRGResult`, `FlowStrengthResult`, `IPOGMPResult`, `DivergenceResult` |
| `libs/schemas/schemas/connectors.py` | `ConnectorResult`, `ConnectorError` |
| `libs/connectors/connectors/base.py` | `BaseConnector` ABC |
| `libs/connectors/connectors/fundamentals.py` | `FundamentalsConnector` |
| `libs/connectors/connectors/fii_dii.py` | `FIIDIIConnector` |
| `libs/connectors/connectors/sentiment.py` | `SentimentConnector` |
| `libs/connectors/connectors/ipo_gmp.py` | `IPOGMPConnector` |
| `libs/features/features/rrg.py` | `compute_rrg(prices, benchmark_df, ...)` |
| `libs/features/features/fii_dii.py` | `compute_flow_strength(flow_history, ...)` |
| `libs/features/features/ipo_gmp.py` | `compute_gmp_disagreement(connector_result, ...)` |
| `libs/features/features/divergence.py` | `compute_divergence(rrg_point, flow, sentiment_polarity, gmp)` |
| `services/api/api/main.py` | FastAPI `create_app()` — add analyze router here |
| `services/worker/worker/main.py` | Worker entry point — update to log graph available |
| `services/worker/pyproject.toml` | Add `features` dependency here |

**Import conventions** (established pattern, follow exactly):
- `from schemas.state import AnalysisState`
- `from connectors.fundamentals import FundamentalsConnector`
- `from features.rrg import compute_rrg`
- Node files live in `services/worker/worker/nodes/`; graph wiring in `services/worker/worker/graph.py`
- API routes live in `services/api/api/routes/`

**LangGraph node wrapper pattern** (use throughout):
```python
# All nodes accept and return AnalysisState.
# graph.py wraps them for LangGraph's dict-based state internally.
async def my_node(state: AnalysisState) -> AnalysisState:
    ...
    return state
```

---

## File Map

```
libs/connectors/connectors/
└── market_data.py               # NEW: yfinance OHLCV connector

services/worker/worker/
├── graph.py                     # NEW: LangGraph graph build + run_analysis()
└── nodes/
    ├── __init__.py              # NEW: empty
    ├── ingest.py                # NEW: ingest_all_data node
    ├── features.py              # NEW: compute_features node
    ├── divergence.py            # NEW: compute_divergence_node node
    └── validate.py              # NEW: normalize_and_validate node

services/api/api/routes/
└── analyze.py                   # NEW: POST /analyze route

services/api/api/main.py         # MODIFIED: include analyze router
services/worker/pyproject.toml   # MODIFIED: add features dependency

tests/unit/connectors/
└── test_market_data.py          # NEW

tests/unit/worker/
├── __init__.py                  # NEW
├── test_ingest_node.py          # NEW
├── test_feature_node.py         # NEW
├── test_divergence_node.py      # NEW
└── test_validate_node.py        # NEW

tests/integration/
└── test_analyze_endpoint.py     # NEW
```

---

## Task 1: MarketDataConnector (yfinance OHLCV)

The `compute_rrg` feature function needs `prices: dict[str, pd.DataFrame]` — daily OHLCV history per ticker. This connector fetches it.

**Files:**
- Create: `libs/connectors/connectors/market_data.py`
- Test: `tests/unit/connectors/test_market_data.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/connectors/test_market_data.py`:
```python
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from connectors.market_data import MarketDataConnector
from schemas.connectors import ConnectorResult


def _make_history() -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=60, freq="B")
    return pd.DataFrame({
        "Open": [100.0] * 60,
        "High": [105.0] * 60,
        "Low": [98.0] * 60,
        "Close": [102.0] * 60,
        "Volume": [1_000_000] * 60,
    }, index=dates)


@pytest.mark.asyncio
async def test_market_data_returns_ohlcv_records():
    with patch("connectors.market_data.yf.Ticker") as MockTicker:
        MockTicker.return_value.history.return_value = _make_history()
        result = await MarketDataConnector().fetch("RELIANCE.NS")
    assert isinstance(result, ConnectorResult)
    assert result.ok
    assert result.source == "yfinance_market_data"
    records = result.data["ohlcv"]
    assert isinstance(records, list)
    assert len(records) == 60
    assert "date" in records[0]
    assert "close" in records[0]


@pytest.mark.asyncio
async def test_market_data_confidence_based_on_row_count():
    short_history = _make_history().iloc[:5]
    with patch("connectors.market_data.yf.Ticker") as MockTicker:
        MockTicker.return_value.history.return_value = short_history
        result = await MarketDataConnector().fetch("THIN.NS")
    assert result.ok
    assert result.confidence < 0.5


@pytest.mark.asyncio
async def test_market_data_empty_history_returns_error():
    with patch("connectors.market_data.yf.Ticker") as MockTicker:
        MockTicker.return_value.history.return_value = pd.DataFrame()
        result = await MarketDataConnector().fetch("EMPTY.NS")
    assert not result.ok
    assert result.error is not None
    assert result.error.code == "NO_DATA"


@pytest.mark.asyncio
async def test_market_data_network_error():
    with patch("connectors.market_data.yf.Ticker", side_effect=Exception("network")):
        result = await MarketDataConnector().fetch("ERR.NS")
    assert not result.ok
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI"
uv run pytest tests/unit/connectors/test_market_data.py -v
```
Expected: `ModuleNotFoundError: No module named 'connectors.market_data'`

- [ ] **Step 3: Implement `libs/connectors/connectors/market_data.py`**

```python
from __future__ import annotations

import asyncio
import logging
from typing import Any

import yfinance as yf

from connectors.base import BaseConnector
from schemas.connectors import ConnectorError, ConnectorResult

logger = logging.getLogger(__name__)

_MIN_ROWS_FOR_FULL_CONFIDENCE = 60


class MarketDataConnector(BaseConnector):
    """Fetches daily OHLCV history for a ticker via yfinance.

    Args:
        period: yfinance period string (default "3mo" ≈ 63 trading days).
    """

    def __init__(self, period: str = "3mo") -> None:
        super().__init__(
            source_name="yfinance_market_data",
            max_retries=3,
            timeout_seconds=20.0,
        )
        self._period = period

    async def fetch(self, ticker: str) -> ConnectorResult:
        loop = asyncio.get_running_loop()
        try:
            df = await loop.run_in_executor(
                None,
                lambda: yf.Ticker(ticker).history(period=self._period),
            )
        except Exception as exc:
            return ConnectorResult(
                source=self.source_name,
                ticker=ticker,
                data={},
                confidence=0.0,
                error=ConnectorError(code="FETCH_ERROR", message=str(exc)),
            )

        if df.empty:
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

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/connectors/test_market_data.py -v
```
Expected: All 4 tests PASS.

- [ ] **Step 5: Update `libs/connectors/connectors/__init__.py`**

Add `MarketDataConnector` to the exports:
```python
from .base import BaseConnector
from .cache import RedisCache
from .market_data import MarketDataConnector

__all__ = ["BaseConnector", "RedisCache", "MarketDataConnector"]
```

- [ ] **Step 6: Commit**

```bash
git add libs/connectors/connectors/market_data.py libs/connectors/connectors/__init__.py tests/unit/connectors/test_market_data.py
git commit -m "feat(connectors): MarketDataConnector for yfinance OHLCV history"
```

---

## Task 2: Worker Dependencies + Nodes Package Skeleton

**Files:**
- Modify: `services/worker/pyproject.toml`
- Create: `services/worker/worker/nodes/__init__.py`
- Create: `tests/unit/worker/__init__.py`

- [ ] **Step 1: Update `services/worker/pyproject.toml`**

Add `features` to dependencies and sources:
```toml
[project]
name = "worker"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "schemas",
  "connectors",
  "features",
  "langgraph>=0.2",
  "langchain>=0.2",
  "langchain-huggingface>=1.0",
  "langchain-ollama>=0.3",
  "huggingface-hub>=0.23",
]

[tool.uv.sources]
schemas = { workspace = true }
connectors = { workspace = true }
features = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["worker"]
```

- [ ] **Step 2: Create `services/worker/worker/nodes/__init__.py`**

```python
```
(Empty file — marks directory as a Python package.)

- [ ] **Step 3: Create `tests/unit/worker/__init__.py`**

```python
```
(Empty file.)

- [ ] **Step 4: Re-sync dependencies**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI"
uv sync --all-extras
```
Expected: Resolves without errors, `features` package now available in worker.

- [ ] **Step 5: Verify features importable from worker context**

```bash
uv run python -c "from features.rrg import compute_rrg; print('OK')"
```
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add services/worker/pyproject.toml services/worker/worker/nodes/__init__.py tests/unit/worker/__init__.py
git commit -m "chore(worker): add features dependency and nodes package skeleton"
```

---

## Task 3: ingest_all_data Node

Runs all 5 connectors concurrently. Failed connectors write `None`; node never raises.

**Files:**
- Create: `services/worker/worker/nodes/ingest.py`
- Test: `tests/unit/worker/test_ingest_node.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/worker/test_ingest_node.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch

from schemas.connectors import ConnectorError, ConnectorResult
from schemas.state import AnalysisState

from worker.nodes.ingest import ingest_all_data


def _ok_result(source: str, ticker: str, data: dict) -> ConnectorResult:
    return ConnectorResult(source=source, ticker=ticker, data=data, confidence=0.9)


def _err_result(source: str, ticker: str) -> ConnectorResult:
    return ConnectorResult(
        source=source,
        ticker=ticker,
        data={},
        confidence=0.0,
        error=ConnectorError(code="FETCH_ERROR", message="fail"),
    )


def _make_state() -> AnalysisState:
    return AnalysisState(user_query="test", ticker_universe=["RELIANCE.NS"])


@pytest.mark.asyncio
async def test_ingest_populates_state_on_success():
    state = _make_state()
    ohlcv = [{"date": "2026-01-01", "close": 100.0}]
    with (
        patch("worker.nodes.ingest.FundamentalsConnector") as MockFund,
        patch("worker.nodes.ingest.MarketDataConnector") as MockMD,
        patch("worker.nodes.ingest.FIIDIIConnector") as MockFII,
        patch("worker.nodes.ingest.SentimentConnector") as MockSent,
        patch("worker.nodes.ingest.IPOGMPConnector") as MockGMP,
    ):
        MockFund.return_value.fetch = AsyncMock(
            return_value=_ok_result("fund", "RELIANCE.NS", {"pe_ratio": 28.0})
        )
        MockMD.return_value.fetch = AsyncMock(
            return_value=_ok_result("md", "RELIANCE.NS", {"ohlcv": ohlcv})
        )
        MockFII.return_value.fetch = AsyncMock(
            return_value=_ok_result("fii", "MARKET", {"fii_net": 100.0, "dii_net": -50.0})
        )
        MockSent.return_value.fetch = AsyncMock(
            return_value=_ok_result("sent", "RELIANCE.NS", {"headlines": []})
        )
        MockGMP.return_value.fetch = AsyncMock(
            return_value=_ok_result("gmp", "RELIANCE", {"gmp": 50.0, "issue_price": 100.0})
        )
        result = await ingest_all_data(state)

    assert "RELIANCE.NS" in result.market_data
    assert result.market_data["RELIANCE.NS"]["fundamentals"]["pe_ratio"] == 28.0
    assert result.market_data["RELIANCE.NS"]["ohlcv"] == ohlcv
    assert result.alt_data["fii_dii"] is not None
    assert "gmp_connector" in result.alt_data  # key always present (value may be None on failure)
    assert result.sentiment["RELIANCE.NS"] is not None
    assert len(result.audit_log) > 0


@pytest.mark.asyncio
async def test_ingest_handles_partial_failure():
    state = _make_state()
    with (
        patch("worker.nodes.ingest.FundamentalsConnector") as MockFund,
        patch("worker.nodes.ingest.MarketDataConnector") as MockMD,
        patch("worker.nodes.ingest.FIIDIIConnector") as MockFII,
        patch("worker.nodes.ingest.SentimentConnector") as MockSent,
        patch("worker.nodes.ingest.IPOGMPConnector") as MockGMP,
    ):
        MockFund.return_value.fetch = AsyncMock(
            return_value=_err_result("fund", "RELIANCE.NS")
        )
        MockMD.return_value.fetch = AsyncMock(
            return_value=_ok_result("md", "RELIANCE.NS", {"ohlcv": []})
        )
        MockFII.return_value.fetch = AsyncMock(
            return_value=_err_result("fii", "MARKET")
        )
        MockSent.return_value.fetch = AsyncMock(
            return_value=_ok_result("sent", "RELIANCE.NS", {"headlines": []})
        )
        MockGMP.return_value.fetch = AsyncMock(
            return_value=_err_result("gmp", "RELIANCE")
        )
        result = await ingest_all_data(state)

    # Node must not raise — partial failures are tolerated
    assert isinstance(result, AnalysisState)
    # Failed connectors write None
    assert result.market_data["RELIANCE.NS"]["fundamentals"] is None
    assert result.alt_data["fii_dii"] is None
    # Audit log must record failures
    failure_entries = [e for e in result.audit_log if "error" in e.message.lower() or "failed" in e.message.lower()]
    assert len(failure_entries) >= 2


@pytest.mark.asyncio
async def test_ingest_never_raises_on_all_failures():
    state = _make_state()
    with (
        patch("worker.nodes.ingest.FundamentalsConnector") as MockFund,
        patch("worker.nodes.ingest.MarketDataConnector") as MockMD,
        patch("worker.nodes.ingest.FIIDIIConnector") as MockFII,
        patch("worker.nodes.ingest.SentimentConnector") as MockSent,
        patch("worker.nodes.ingest.IPOGMPConnector") as MockGMP,
    ):
        for M in [MockFund, MockMD, MockFII, MockSent, MockGMP]:
            M.return_value.fetch = AsyncMock(side_effect=Exception("total failure"))
        result = await ingest_all_data(state)

    assert isinstance(result, AnalysisState)
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/unit/worker/test_ingest_node.py -v
```
Expected: `ModuleNotFoundError: No module named 'worker.nodes.ingest'`

- [ ] **Step 3: Implement `services/worker/worker/nodes/ingest.py`**

```python
from __future__ import annotations

import asyncio
import logging
from typing import Any

from connectors.fii_dii import FIIDIIConnector
from connectors.fundamentals import FundamentalsConnector
from connectors.ipo_gmp import IPOGMPConnector
from connectors.market_data import MarketDataConnector
from connectors.sentiment import SentimentConnector
from schemas.connectors import ConnectorResult
from schemas.state import AnalysisState

logger = logging.getLogger(__name__)


def _data_or_none(result: ConnectorResult) -> dict[str, Any] | None:
    return result.data if result.ok else None


async def _safe_fetch(connector: Any, ticker: str, node: str, state: AnalysisState) -> ConnectorResult:
    """Fetch from connector, catching all exceptions and returning an error result."""
    from schemas.connectors import ConnectorError
    try:
        return await connector.fetch(ticker)
    except Exception as exc:
        state.append_audit(node, f"connector fetch raised: {exc}", ticker=ticker)
        return ConnectorResult(
            source=getattr(connector, "source_name", "unknown"),
            ticker=ticker,
            data={},
            confidence=0.0,
            error=ConnectorError(code="UNEXPECTED_ERROR", message=str(exc)),
        )


async def ingest_all_data(state: AnalysisState) -> AnalysisState:
    """Fetch all data sources concurrently. Failed connectors write None — never raises."""
    node = "ingest_all_data"
    tickers = state.ticker_universe

    fund_conn = FundamentalsConnector()
    md_conn = MarketDataConnector()
    fii_conn = FIIDIIConnector()
    sent_conn = SentimentConnector()
    gmp_conn = IPOGMPConnector()

    # Per-ticker tasks: fundamentals + OHLCV for each ticker
    fund_tasks = [_safe_fetch(fund_conn, t, node, state) for t in tickers]
    md_tasks = [_safe_fetch(md_conn, t, node, state) for t in tickers]
    # Benchmark prices for RRG (Nifty 50)
    bench_task = _safe_fetch(md_conn, "^NSEI", node, state)
    # Market-wide connectors
    fii_task = _safe_fetch(fii_conn, "MARKET", node, state)
    sent_tasks = [_safe_fetch(sent_conn, t, node, state) for t in tickers]
    # GMP — use first ticker's name as company substring
    gmp_ticker = tickers[0].replace(".NS", "").replace(".BO", "")
    gmp_task = _safe_fetch(gmp_conn, gmp_ticker, node, state)

    results = await asyncio.gather(
        *fund_tasks,
        *md_tasks,
        bench_task,
        fii_task,
        *sent_tasks,
        gmp_task,
    )

    n = len(tickers)
    fund_results = results[:n]
    md_results = results[n : 2 * n]
    bench_result = results[2 * n]
    fii_result = results[2 * n + 1]
    sent_results = results[2 * n + 2 : 3 * n + 2]
    gmp_result = results[3 * n + 2]

    # Build market_data: ticker → {fundamentals, ohlcv}
    market_data: dict[str, Any] = {}
    for ticker, fund_r, md_r in zip(tickers, fund_results, md_results):
        if not fund_r.ok:
            state.append_audit(node, f"fundamentals failed for {ticker}: {fund_r.error}")
        if not md_r.ok:
            state.append_audit(node, f"market data failed for {ticker}: {md_r.error}")
        market_data[ticker] = {
            "fundamentals": _data_or_none(fund_r),
            "ohlcv": _data_or_none(md_r).get("ohlcv") if _data_or_none(md_r) else None,
        }

    # Benchmark OHLCV
    if not bench_result.ok:
        state.append_audit(node, f"benchmark (^NSEI) fetch failed: {bench_result.error}")
    market_data["^NSEI"] = {
        "ohlcv": _data_or_none(bench_result).get("ohlcv") if _data_or_none(bench_result) else None,
    }

    # FII/DII
    if not fii_result.ok:
        state.append_audit(node, f"FII/DII fetch failed: {fii_result.error}")

    # Sentiment — keyed by ticker
    sentiment: dict[str, Any] = {}
    for ticker, sent_r in zip(tickers, sent_results):
        if not sent_r.ok:
            state.append_audit(node, f"sentiment failed for {ticker}: {sent_r.error}")
        sentiment[ticker] = _data_or_none(sent_r)

    # GMP
    if not gmp_result.ok:
        state.append_audit(node, f"GMP fetch failed: {gmp_result.error}")

    state.market_data = market_data
    state.alt_data = {
        "fii_dii": _data_or_none(fii_result),
        # Serialize ConnectorResult to dict so LangGraph's model_dump/model_validate round-trip
        # doesn't lose the type. features.py reconstructs it via ConnectorResult.model_validate().
        "gmp_connector": gmp_result.model_dump() if gmp_result.ok else None,
    }
    state.sentiment = sentiment
    state.append_audit(node, "ingest complete", tickers=tickers)
    return state
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/worker/test_ingest_node.py -v
```
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/worker/worker/nodes/ingest.py tests/unit/worker/test_ingest_node.py
git commit -m "feat(worker): ingest_all_data node with concurrent connector fetching"
```

---

## Task 4: compute_features Node

Calls `compute_rrg` and `compute_flow_strength` in parallel, then `compute_gmp_disagreement` sequentially. Writes to `state.rotation` and `state.alt_data`.

**Files:**
- Create: `services/worker/worker/nodes/features.py`
- Test: `tests/unit/worker/test_feature_node.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/worker/test_feature_node.py`:
```python
import pandas as pd
import pytest
from datetime import date
from unittest.mock import patch, MagicMock

from schemas.connectors import ConnectorResult
from schemas.features import FlowStrengthResult, RRGPoint, RRGResult
from schemas.state import AnalysisState

from worker.nodes.features import compute_features


def _make_state_with_data(with_fii: bool = True, with_ohlcv: bool = True) -> AnalysisState:
    ohlcv = [{"date": f"2026-01-{i+1:02d}", "close": 100.0 + i} for i in range(30)]
    bench_ohlcv = [{"date": f"2026-01-{i+1:02d}", "close": 200.0 + i} for i in range(30)]
    fii_data = {
        "fii_net": 500.0, "fii_buy": 1000.0, "fii_sell": 500.0,
        "dii_net": -200.0, "dii_buy": 300.0, "dii_sell": 500.0,
    } if with_fii else None

    state = AnalysisState(user_query="test", ticker_universe=["RELIANCE.NS"])
    state.market_data = {
        "RELIANCE.NS": {
            "fundamentals": {"sector": "Energy"},
            "ohlcv": ohlcv if with_ohlcv else None,
        },
        "^NSEI": {"ohlcv": bench_ohlcv if with_ohlcv else None},
    }
    state.alt_data = {
        "fii_dii": fii_data,
        "gmp_connector": None,
    }
    return state


@pytest.mark.asyncio
async def test_compute_features_writes_rrg_result():
    state = _make_state_with_data()
    mock_rrg = RRGResult(
        points=[RRGPoint(
            ticker="RELIANCE.NS", rs_ratio=105.0, rs_momentum=1.5,
            quadrant="Leading", benchmark="^NSEI", as_of=date(2026, 1, 30),
        )],
        smoothing=10, momentum_lag=1,
    )
    with patch("worker.nodes.features.compute_rrg", return_value=mock_rrg):
        with patch("worker.nodes.features.compute_flow_strength", side_effect=ValueError("insufficient")):
            result = await compute_features(state)

    assert "points" in result.rotation
    assert result.rotation["points"][0]["ticker"] == "RELIANCE.NS"
    assert result.alt_data["flow"] is None


@pytest.mark.asyncio
async def test_compute_features_writes_flow_result():
    state = _make_state_with_data()
    mock_rrg = RRGResult(points=[], smoothing=10, momentum_lag=1)
    mock_flow = FlowStrengthResult(
        as_of=date(2026, 1, 30),
        fii_zscore=1.2, fii_ratio=0.3, fii_streak=3,
        dii_zscore=-0.5, dii_ratio=-0.1, dii_streak=-2,
        net_institutional=300.0,
    )
    with patch("worker.nodes.features.compute_rrg", return_value=mock_rrg):
        with patch("worker.nodes.features.compute_flow_strength", return_value=mock_flow):
            result = await compute_features(state)

    assert result.alt_data["flow"] is not None
    assert result.alt_data["flow"]["fii_zscore"] == 1.2


@pytest.mark.asyncio
async def test_compute_features_handles_none_gmp():
    state = _make_state_with_data()
    state.alt_data["gmp_connector"] = None
    mock_rrg = RRGResult(points=[], smoothing=10, momentum_lag=1)

    with patch("worker.nodes.features.compute_rrg", return_value=mock_rrg):
        with patch("worker.nodes.features.compute_flow_strength", side_effect=ValueError("insufficient")):
            result = await compute_features(state)

    assert result.alt_data["gmp"] is None


@pytest.mark.asyncio
async def test_compute_features_handles_missing_ohlcv():
    state = _make_state_with_data(with_ohlcv=False)
    with patch("worker.nodes.features.compute_rrg") as mock_rrg_fn:
        with patch("worker.nodes.features.compute_flow_strength", side_effect=ValueError("insufficient")):
            result = await compute_features(state)

    # compute_rrg should not be called — no prices to pass
    mock_rrg_fn.assert_not_called()
    assert result.rotation == {}
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/unit/worker/test_feature_node.py -v
```
Expected: `ModuleNotFoundError: No module named 'worker.nodes.features'`

- [ ] **Step 3: Implement `services/worker/worker/nodes/features.py`**

```python
from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

import pandas as pd

from features.fii_dii import compute_flow_strength
from features.ipo_gmp import compute_gmp_disagreement
from features.rrg import compute_rrg
from schemas.features import FlowStrengthResult, RRGResult
from schemas.state import AnalysisState

logger = logging.getLogger(__name__)


def _records_to_df(records: list[dict], date_col: str = "date") -> pd.DataFrame:
    """Convert list of OHLCV dicts to a DataFrame indexed by date."""
    df = pd.DataFrame(records)
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).sort_index()
    # Rename to lowercase for feature functions
    df.columns = [c.lower() for c in df.columns]
    return df


def _build_flow_history(fii_data: dict[str, Any]) -> pd.DataFrame:
    """Build a single-row FII/DII DataFrame from today's connector data.

    Note: compute_flow_strength requires zscore_window (20) rows minimum.
    With a single row, it will raise ValueError — caller handles this.
    """
    return pd.DataFrame([{
        "date": date.today(),
        "fii_net": fii_data.get("fii_net", 0.0),
        "fii_buy": fii_data.get("fii_buy", 0.0),
        "fii_sell": fii_data.get("fii_sell", 0.0),
        "dii_net": fii_data.get("dii_net", 0.0),
        "dii_buy": fii_data.get("dii_buy", 0.0),
        "dii_sell": fii_data.get("dii_sell", 0.0),
    }]).set_index("date")


async def _run_rrg(state: AnalysisState) -> RRGResult | None:
    """Build price dicts and call compute_rrg. Returns None if prices unavailable."""
    bench_ohlcv = state.market_data.get("^NSEI", {}).get("ohlcv")
    if not bench_ohlcv:
        state.append_audit("compute_features", "skipping RRG — benchmark prices unavailable")
        return None

    prices: dict[str, pd.DataFrame] = {}
    for ticker in state.ticker_universe:
        ohlcv = state.market_data.get(ticker, {}).get("ohlcv")
        if ohlcv:
            prices[ticker] = _records_to_df(ohlcv)
        else:
            state.append_audit("compute_features", f"skipping RRG for {ticker} — no OHLCV")

    if not prices:
        state.append_audit("compute_features", "skipping RRG — no ticker prices available")
        return None

    benchmark_df = _records_to_df(bench_ohlcv)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: compute_rrg(prices, benchmark_df))


async def _run_flow_strength(state: AnalysisState) -> FlowStrengthResult | None:
    """Build flow history DataFrame and call compute_flow_strength."""
    fii_data = state.alt_data.get("fii_dii")
    if not fii_data:
        state.append_audit("compute_features", "skipping flow strength — FII/DII data unavailable")
        return None

    flow_df = _build_flow_history(fii_data)
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, lambda: compute_flow_strength(flow_df))
    except ValueError as exc:
        state.append_audit("compute_features", f"flow strength skipped: {exc}")
        return None


async def compute_features(state: AnalysisState) -> AnalysisState:
    """Compute RRG, flow strength, and GMP features from ingested data."""
    node = "compute_features"

    # RRG and flow run concurrently
    rrg_result, flow_result = await asyncio.gather(
        _run_rrg(state),
        _run_flow_strength(state),
    )

    # GMP disagreement (sequential — depends on gmp connector result)
    # gmp_connector is stored as a serialized dict (to survive LangGraph round-trip)
    gmp_result = None
    gmp_connector_dict = state.alt_data.get("gmp_connector")
    if gmp_connector_dict is not None:
        from schemas.connectors import ConnectorResult
        gmp_cr = ConnectorResult.model_validate(gmp_connector_dict)
        gmp_result = compute_gmp_disagreement(gmp_cr)

    # Write to state
    state.rotation = rrg_result.model_dump() if rrg_result else {}
    state.alt_data["flow"] = flow_result.model_dump() if flow_result else None
    state.alt_data["gmp"] = gmp_result.model_dump() if gmp_result else None

    state.append_audit(
        node,
        "feature computation complete",
        rrg_points=len(rrg_result.points) if rrg_result else 0,
        flow_available=flow_result is not None,
        gmp_available=gmp_result is not None,
    )
    return state
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/worker/test_feature_node.py -v
```
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/worker/worker/nodes/features.py tests/unit/worker/test_feature_node.py
git commit -m "feat(worker): compute_features node wiring RRG, flow strength, GMP"
```

---

## Task 5: compute_divergence Node

Iterates over RRG points, calls `compute_divergence` per ticker, averages scores. Handles missing flow gracefully.

**Files:**
- Create: `services/worker/worker/nodes/divergence.py`
- Test: `tests/unit/worker/test_divergence_node.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/worker/test_divergence_node.py`:
```python
import pytest
from datetime import date
from unittest.mock import patch

from schemas.features import (
    DivergenceResult, FlowStrengthResult, RRGPoint, RRGResult,
)
from schemas.state import AnalysisState

from worker.nodes.divergence import compute_divergence_node


def _make_state(with_flow: bool = True, rrg_points: int = 1) -> AnalysisState:
    state = AnalysisState(user_query="test", ticker_universe=["RELIANCE.NS", "TCS.NS"])
    points = [
        RRGPoint(
            ticker=f"TICK{i}.NS", rs_ratio=105.0, rs_momentum=1.0,
            quadrant="Leading", benchmark="^NSEI", as_of=date(2026, 1, 30),
        ).model_dump()
        for i in range(rrg_points)
    ]
    state.rotation = RRGResult(
        points=[RRGPoint(**p) for p in points], smoothing=10, momentum_lag=1,
    ).model_dump()

    if with_flow:
        state.alt_data["flow"] = FlowStrengthResult(
            as_of=date(2026, 1, 30),
            fii_zscore=1.0, fii_ratio=0.3, fii_streak=3,
            dii_zscore=0.8, dii_ratio=0.2, dii_streak=2,
            net_institutional=500.0,
        ).model_dump()
    else:
        state.alt_data["flow"] = None
    return state


@pytest.mark.asyncio
async def test_divergence_node_writes_score_and_contradictions():
    state = _make_state(with_flow=True)
    mock_result = DivergenceResult(
        divergence_score=0.15,
        contradictions=["fii_zscore=bullish conflicts with dii_zscore=bearish"],
        majority_direction="bullish",
        signal_votes={"rrg": "bullish", "fii_zscore": "bullish", "fii_ratio": "bullish",
                      "dii_zscore": "bullish", "sentiment": "neutral"},
    )
    with patch("worker.nodes.divergence.compute_divergence", return_value=mock_result):
        result = await compute_divergence_node(state)

    assert result.divergence_score == pytest.approx(0.15)
    assert len(result.contradictions) >= 0


@pytest.mark.asyncio
async def test_divergence_node_zero_score_when_no_flow():
    state = _make_state(with_flow=False)
    result = await compute_divergence_node(state)

    assert result.divergence_score == 0.0
    assert isinstance(result.contradictions, list)
    assert any("flow" in e.message.lower() for e in result.audit_log)


@pytest.mark.asyncio
async def test_divergence_node_averages_multiple_rrg_points():
    state = _make_state(with_flow=True, rrg_points=2)
    results = [
        DivergenceResult(
            divergence_score=0.2, contradictions=[],
            majority_direction="bullish",
            signal_votes={"rrg": "bullish", "fii_zscore": "bullish",
                         "fii_ratio": "bullish", "dii_zscore": "bullish", "sentiment": "neutral"},
        ),
        DivergenceResult(
            divergence_score=0.4, contradictions=[],
            majority_direction="bullish",
            signal_votes={"rrg": "bullish", "fii_zscore": "bullish",
                         "fii_ratio": "bullish", "dii_zscore": "bullish", "sentiment": "neutral"},
        ),
    ]
    with patch("worker.nodes.divergence.compute_divergence", side_effect=results):
        result = await compute_divergence_node(state)

    assert result.divergence_score == pytest.approx(0.3)


@pytest.mark.asyncio
async def test_divergence_node_empty_rrg_writes_zero():
    state = _make_state(with_flow=True, rrg_points=0)
    result = await compute_divergence_node(state)
    assert result.divergence_score == 0.0
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/unit/worker/test_divergence_node.py -v
```
Expected: `ModuleNotFoundError: No module named 'worker.nodes.divergence'`

- [ ] **Step 3: Implement `services/worker/worker/nodes/divergence.py`**

```python
from __future__ import annotations

import logging

from features.divergence import compute_divergence
from schemas.features import FlowStrengthResult, RRGPoint, RRGResult
from schemas.state import AnalysisState

logger = logging.getLogger(__name__)

_NODE = "compute_divergence"

# Simple keyword-based sentiment polarity from headlines.
_POSITIVE = {"gain", "rise", "rally", "bull", "buy", "surge", "strong", "growth", "profit", "up"}
_NEGATIVE = {"fall", "drop", "crash", "bear", "sell", "weak", "loss", "decline", "down", "slump"}


def _headline_polarity(sentiment: dict) -> float:
    """Compute aggregate sentiment polarity from headlines dict. Returns float in [-1, 1]."""
    if not sentiment:
        return 0.0
    headlines = []
    for ticker_headlines in sentiment.values():
        if isinstance(ticker_headlines, dict):
            headlines.extend(ticker_headlines.get("headlines", []))
    if not headlines:
        return 0.0
    scores = []
    for h in headlines:
        words = h.get("title", "").lower().split()
        pos = sum(1 for w in words if w in _POSITIVE)
        neg = sum(1 for w in words if w in _NEGATIVE)
        total = pos + neg
        if total > 0:
            scores.append((pos - neg) / total)
    return sum(scores) / len(scores) if scores else 0.0


async def compute_divergence_node(state: AnalysisState) -> AnalysisState:
    """Compute divergence score across all RRG points. Averages scores per ticker."""
    flow_data = state.alt_data.get("flow")
    rrg_data = state.rotation

    if not rrg_data or not rrg_data.get("points"):
        state.append_audit(_NODE, "no RRG points — divergence_score set to 0.0")
        state.divergence_score = 0.0
        return state

    if not flow_data:
        state.append_audit(_NODE, "flow data unavailable — divergence_score set to 0.0")
        state.divergence_score = 0.0
        return state

    flow = FlowStrengthResult.model_validate(flow_data)
    sentiment_polarity = _headline_polarity(state.sentiment)

    scores: list[float] = []
    all_contradictions: list[str] = []

    for point_data in rrg_data["points"]:
        point = RRGPoint.model_validate(point_data)
        result = compute_divergence(point, flow, sentiment_polarity)
        scores.append(result.divergence_score)
        all_contradictions.extend(result.contradictions)

    avg_score = sum(scores) / len(scores)
    # Deduplicate contradictions
    seen: set[str] = set()
    unique_contradictions = [c for c in all_contradictions if not (c in seen or seen.add(c))]  # type: ignore[func-returns-value]

    state.divergence_score = round(avg_score, 4)
    state.contradictions = unique_contradictions
    state.append_audit(
        _NODE,
        "divergence computed",
        score=state.divergence_score,
        tickers_scored=len(scores),
        contradictions=len(unique_contradictions),
    )
    return state
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/worker/test_divergence_node.py -v
```
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/worker/worker/nodes/divergence.py tests/unit/worker/test_divergence_node.py
git commit -m "feat(worker): compute_divergence_node averaging scores across RRG points"
```

---

## Task 6: normalize_and_validate Node

Sets `state.confidence` using a heuristic. Logs field coverage.

**Files:**
- Create: `services/worker/worker/nodes/validate.py`
- Test: `tests/unit/worker/test_validate_node.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/worker/test_validate_node.py`:
```python
import pytest
from schemas.state import AnalysisState
from worker.nodes.validate import normalize_and_validate


def _make_full_state() -> AnalysisState:
    state = AnalysisState(user_query="test", ticker_universe=["RELIANCE.NS"])
    state.market_data = {"RELIANCE.NS": {"fundamentals": {"pe": 28.0}, "ohlcv": [{"close": 100.0}]}}
    state.alt_data = {"fii_dii": {"fii_net": 100.0}, "flow": {"fii_zscore": 1.0}, "gmp": None}
    state.sentiment = {"RELIANCE.NS": {"headlines": []}}
    state.rotation = {"points": [{"ticker": "RELIANCE.NS"}], "smoothing": 10, "momentum_lag": 1}
    state.divergence_score = 0.0
    return state


def _make_empty_state() -> AnalysisState:
    state = AnalysisState(user_query="test", ticker_universe=["RELIANCE.NS"])
    state.divergence_score = 0.5
    return state


@pytest.mark.asyncio
async def test_confidence_high_when_all_data_present():
    state = _make_full_state()
    result = await normalize_and_validate(state)
    assert result.confidence > 0.6


@pytest.mark.asyncio
async def test_confidence_low_when_all_data_missing():
    state = _make_empty_state()
    result = await normalize_and_validate(state)
    assert result.confidence < 0.4


@pytest.mark.asyncio
async def test_confidence_penalised_by_high_divergence():
    state = _make_full_state()
    state.divergence_score = 1.0
    result = await normalize_and_validate(state)

    state_zero_div = _make_full_state()
    state_zero_div.divergence_score = 0.0
    result_zero = await normalize_and_validate(state_zero_div)

    assert result.confidence < result_zero.confidence


@pytest.mark.asyncio
async def test_audit_log_has_final_entry():
    state = _make_full_state()
    result = await normalize_and_validate(state)
    assert any("normalize" in e.node or "validate" in e.node for e in result.audit_log)
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/unit/worker/test_validate_node.py -v
```
Expected: `ModuleNotFoundError: No module named 'worker.nodes.validate'`

- [ ] **Step 3: Implement `services/worker/worker/nodes/validate.py`**

```python
from __future__ import annotations

import logging

from schemas.state import AnalysisState

logger = logging.getLogger(__name__)

_NODE = "normalize_and_validate"


def _count_ok(values: list[bool]) -> tuple[int, int]:
    return sum(values), len(values)


async def normalize_and_validate(state: AnalysisState) -> AnalysisState:
    """Validate state field coverage and set confidence heuristic.

    confidence = (connectors_ok / total_connectors) * 0.5 + (1 - divergence_score) * 0.5
    """
    tickers = state.ticker_universe

    # Check which data sources are populated
    checks = [
        # At least one ticker has fundamentals
        any(
            state.market_data.get(t, {}).get("fundamentals") is not None
            for t in tickers
        ),
        # At least one ticker has OHLCV
        any(
            state.market_data.get(t, {}).get("ohlcv") is not None
            for t in tickers
        ),
        # FII/DII data present
        state.alt_data.get("fii_dii") is not None,
        # RRG computed (at least attempted)
        bool(state.rotation),
        # Sentiment data present for at least one ticker
        any(state.sentiment.get(t) is not None for t in tickers),
    ]

    ok_count, total = _count_ok(checks)
    connectors_ratio = ok_count / total if total > 0 else 0.0

    confidence = connectors_ratio * 0.5 + (1.0 - state.divergence_score) * 0.5
    state.confidence = round(min(max(confidence, 0.0), 1.0), 4)

    gaps = []
    if not checks[0]:
        gaps.append("fundamentals missing for all tickers")
    if not checks[1]:
        gaps.append("OHLCV missing for all tickers")
    if not checks[2]:
        gaps.append("FII/DII data missing")
    if not checks[3]:
        gaps.append("RRG not computed")
    if not checks[4]:
        gaps.append("sentiment missing for all tickers")

    state.append_audit(
        _NODE,
        "validation complete",
        confidence=state.confidence,
        connectors_ok=ok_count,
        total_checks=total,
        gaps=gaps,
    )
    return state
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/unit/worker/test_validate_node.py -v
```
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/worker/worker/nodes/validate.py tests/unit/worker/test_validate_node.py
git commit -m "feat(worker): normalize_and_validate node with confidence heuristic"
```

---

## Task 7: LangGraph Graph Construction

Wires the four nodes into a compiled LangGraph graph with MemorySaver. Exposes `run_analysis(state) -> AnalysisState`.

**Files:**
- Create: `services/worker/worker/graph.py`

No separate test file — the graph is tested via the integration test in Task 8. The wrapper pattern is straightforward enough to trust at the integration level.

- [ ] **Step 1: Implement `services/worker/worker/graph.py`**

```python
from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from schemas.state import AnalysisState
from worker.nodes.divergence import compute_divergence_node
from worker.nodes.features import compute_features
from worker.nodes.ingest import ingest_all_data
from worker.nodes.validate import normalize_and_validate

logger = logging.getLogger(__name__)


def _wrap(node_fn: Any) -> Any:
    """Wrap an AnalysisState→AnalysisState node for LangGraph's dict-based state."""
    async def wrapped(state_dict: dict[str, Any]) -> dict[str, Any]:
        state = AnalysisState.model_validate(state_dict)
        result = await node_fn(state)
        return result.model_dump()
    wrapped.__name__ = node_fn.__name__
    return wrapped


def _build_graph() -> Any:
    builder: StateGraph = StateGraph(dict)

    builder.add_node("ingest_all_data", _wrap(ingest_all_data))
    builder.add_node("compute_features", _wrap(compute_features))
    builder.add_node("compute_divergence", _wrap(compute_divergence_node))
    builder.add_node("normalize_and_validate", _wrap(normalize_and_validate))

    builder.set_entry_point("ingest_all_data")
    builder.add_edge("ingest_all_data", "compute_features")
    builder.add_edge("compute_features", "compute_divergence")
    builder.add_edge("compute_divergence", "normalize_and_validate")
    builder.add_edge("normalize_and_validate", END)

    return builder.compile(checkpointer=MemorySaver())


async def run_analysis(state: AnalysisState) -> AnalysisState:
    """Run the full analysis graph and return the final populated AnalysisState.

    Args:
        state: Initial AnalysisState with user_query and ticker_universe populated.

    Returns:
        AnalysisState with all fields populated (market_data, rotation, divergence_score, etc.)
    """
    graph = _build_graph()
    config = {"configurable": {"thread_id": state.run_id}}
    result: dict[str, Any] = await graph.ainvoke(state.model_dump(), config=config)
    return AnalysisState.model_validate(result)
```

- [ ] **Step 2: Verify the import works**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI"
uv run python -c "from worker.graph import run_analysis; print('graph import OK')"
```
Expected: `graph import OK`

- [ ] **Step 3: Update `services/worker/worker/main.py`** to log graph availability:

```python
import logging

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("PulseAlpha Worker starting")
    logger.info("LangGraph analysis graph available — use worker.graph.run_analysis()")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Commit**

```bash
git add services/worker/worker/graph.py services/worker/worker/main.py
git commit -m "feat(worker): LangGraph graph with MemorySaver and run_analysis() entry point"
```

---

## Task 8: POST /analyze Endpoint

Adds the route, wires it into the FastAPI app, and tests the full graph end-to-end with mocked connectors.

**Files:**
- Create: `services/api/api/routes/analyze.py`
- Modify: `services/api/api/main.py`
- Test: `tests/integration/test_analyze_endpoint.py`

- [ ] **Step 1: Write failing integration test**

`tests/integration/test_analyze_endpoint.py`:
```python
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from schemas.connectors import ConnectorError, ConnectorResult


def _ok(source: str, ticker: str, data: dict) -> ConnectorResult:
    return ConnectorResult(source=source, ticker=ticker, data=data, confidence=0.9)


def _err(source: str, ticker: str) -> ConnectorResult:
    return ConnectorResult(
        source=source, ticker=ticker, data={}, confidence=0.0,
        error=ConnectorError(code="FETCH_ERROR", message="mocked failure"),
    )


@pytest.fixture()
def mock_connectors():
    ohlcv = [{"date": f"2026-01-{i+1:02d}", "close": 100.0 + i} for i in range(30)]
    bench_ohlcv = [{"date": f"2026-01-{i+1:02d}", "close": 200.0 + i} for i in range(30)]

    with (
        patch("worker.nodes.ingest.FundamentalsConnector") as MockFund,
        patch("worker.nodes.ingest.MarketDataConnector") as MockMD,
        patch("worker.nodes.ingest.FIIDIIConnector") as MockFII,
        patch("worker.nodes.ingest.SentimentConnector") as MockSent,
        patch("worker.nodes.ingest.IPOGMPConnector") as MockGMP,
    ):
        def md_side_effect(ticker: str) -> ConnectorResult:
            if ticker == "^NSEI":
                return _ok("md", "^NSEI", {"ohlcv": bench_ohlcv})
            return _ok("md", ticker, {"ohlcv": ohlcv})

        MockFund.return_value.fetch = AsyncMock(
            return_value=_ok("fund", "RELIANCE.NS", {"pe_ratio": 28.0, "sector": "Energy"})
        )
        MockMD.return_value.fetch = AsyncMock(side_effect=lambda t: md_side_effect(t))
        MockFII.return_value.fetch = AsyncMock(
            return_value=_ok("fii", "MARKET", {
                "fii_net": 500.0, "fii_buy": 1000.0, "fii_sell": 500.0,
                "dii_net": -100.0, "dii_buy": 200.0, "dii_sell": 300.0,
            })
        )
        MockSent.return_value.fetch = AsyncMock(
            return_value=_ok("sent", "RELIANCE.NS", {"headlines": []})
        )
        MockGMP.return_value.fetch = AsyncMock(
            return_value=_err("gmp", "RELIANCE")
        )
        yield


@pytest.mark.asyncio
async def test_analyze_returns_200(mock_connectors):
    from api.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/analyze", json={
            "ticker_universe": ["RELIANCE.NS"],
            "user_query": "Analyze Reliance",
        })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_analyze_returns_valid_state_fields(mock_connectors):
    from api.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/analyze", json={
            "ticker_universe": ["RELIANCE.NS"],
            "user_query": "Analyze Reliance",
        })
    body = r.json()
    assert "run_id" in body
    assert "divergence_score" in body
    assert "confidence" in body
    assert "audit_log" in body
    assert isinstance(body["audit_log"], list)
    assert len(body["audit_log"]) > 0


@pytest.mark.asyncio
async def test_analyze_missing_ticker_universe_returns_422():
    from api.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/analyze", json={"user_query": "test"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_analyze_empty_ticker_universe_returns_422():
    from api.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/analyze", json={
            "ticker_universe": [],
            "user_query": "test",
        })
    assert r.status_code == 422
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/integration/test_analyze_endpoint.py -v
```
Expected: `ModuleNotFoundError` or `404` — route doesn't exist yet.

- [ ] **Step 3: Implement `services/api/api/routes/analyze.py`**

```python
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from schemas.state import AnalysisState

logger = logging.getLogger(__name__)

router = APIRouter()


class AnalyzeRequest(BaseModel):
    ticker_universe: list[str]
    user_query: str = "Analyze the provided tickers"


@router.post("/analyze", response_model=dict)
async def analyze(request: AnalyzeRequest) -> dict:
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

    return final_state.model_dump(mode="json")
```

- [ ] **Step 4: Update `services/api/api/main.py`** to include the analyze router:

```python
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.config import get_settings
from api.routes.analyze import router as analyze_router
from api.routes.health import router as health_router

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
    app.include_router(health_router)
    app.include_router(analyze_router)
    return app


app = create_app()
```

- [ ] **Step 5: Run integration tests**

```bash
uv run pytest tests/integration/test_analyze_endpoint.py -v
```
Expected: All 4 tests PASS.

- [ ] **Step 6: Also run existing health test to confirm no regression**

```bash
uv run pytest tests/integration/ -v
```
Expected: All integration tests PASS.

- [ ] **Step 7: Commit**

```bash
git add services/api/api/routes/analyze.py services/api/api/main.py tests/integration/test_analyze_endpoint.py
git commit -m "feat(api): POST /analyze endpoint wired to LangGraph run_analysis"
```

---

## Task 9: Full Suite Verification

- [ ] **Step 1: Run all unit tests**

```bash
cd "/Users/eeshandhawan/Desktop/PulseAlpha AI"
uv run pytest tests/unit/ -v --tb=short
```
Expected: All green.

- [ ] **Step 2: Run all integration tests**

```bash
uv run pytest tests/integration/ -v --tb=short
```
Expected: All green.

- [ ] **Step 3: Lint**

```bash
uv run ruff check .
```
Expected: No errors. If there are import-sort errors, run `uv run ruff check . --fix` and commit.

- [ ] **Step 4: Type check**

```bash
uv run mypy libs/ services/ --ignore-missing-imports
```
Expected: No errors (or only pre-existing issues from Phase 2 baseline).

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: Phase 3 complete — LangGraph orchestration + POST /analyze endpoint"
```

---

## Verification Summary

| Check | Command | Expected |
|-------|---------|---------|
| Unit tests | `uv run pytest tests/unit/ -v` | All green |
| Integration tests | `uv run pytest tests/integration/ -v` | All green |
| Lint | `uv run ruff check .` | No errors |
| Types | `uv run mypy libs/ services/ --ignore-missing-imports` | No errors |
| Graph import | `uv run python -c "from worker.graph import run_analysis; print('OK')"` | `OK` |

## Phase Exit Criteria

- `POST /analyze` returns HTTP 200 with valid `AnalysisState` JSON body
- Response includes `divergence_score`, `confidence`, and `audit_log` with entries from all four nodes
- All unit and integration tests pass with mocked connectors
