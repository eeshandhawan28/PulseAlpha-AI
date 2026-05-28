from __future__ import annotations

import json
from datetime import UTC, date, datetime

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
        created_at=datetime(2022, 3, 1, 12, 0, tzinfo=UTC),
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
