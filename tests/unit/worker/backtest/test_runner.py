from __future__ import annotations

import json
import os
import tempfile
from datetime import date
from unittest.mock import AsyncMock, patch

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
            patch(
                "worker.backtest.runner.compute_divergence_node", new_callable=AsyncMock
            ) as p_div,
            patch(
                "worker.backtest.runner.normalize_and_validate", new_callable=AsyncMock
            ) as p_norm,
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
            patch(
                "worker.backtest.runner.compute_divergence_node", new_callable=AsyncMock
            ) as p_div,
            patch(
                "worker.backtest.runner.normalize_and_validate", new_callable=AsyncMock
            ) as p_norm,
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
            patch(
                "worker.backtest.runner.compute_divergence_node", new_callable=AsyncMock
            ) as p_div,
            patch(
                "worker.backtest.runner.normalize_and_validate", new_callable=AsyncMock
            ) as p_norm,
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
                CouncilOutput(
                    persona="Contrarian", stance="neutral", rationale="x", confidence=0.5
                ),
            ]
            state.confidence = 0.5
            return state

        with (
            patch("worker.backtest.runner.ingest_all_data", new_callable=AsyncMock) as p_ingest,
            patch("worker.backtest.runner.compute_features", new_callable=AsyncMock) as p_feat,
            patch(
                "worker.backtest.runner.compute_divergence_node", new_callable=AsyncMock
            ) as p_div,
            patch(
                "worker.backtest.runner.normalize_and_validate", new_callable=AsyncMock
            ) as p_norm,
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

        assert result.metrics["hit_rate_30d"]["n_evaluated"] == 0
