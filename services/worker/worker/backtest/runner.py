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
