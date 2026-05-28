from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from api.main import app
from httpx import ASGITransport, AsyncClient
from schemas.state import AnalysisState, CouncilOutput


def _mock_ingest(state: AnalysisState) -> AnalysisState:
    state.market_data = {t: {"fundamentals": None, "ohlcv": None} for t in state.ticker_universe}
    state.rotation = {t: {"quadrant": "Leading"} for t in state.ticker_universe}
    state.divergence_score = 0.2
    return state


def _mock_council(state: AnalysisState) -> AnalysisState:
    state.council_outputs = [
        CouncilOutput(persona="Contrarian", stance="bullish", rationale="test", confidence=0.7),
        CouncilOutput(
            persona="FirstPrinciples", stance="bullish", rationale="test", confidence=0.7
        ),
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
