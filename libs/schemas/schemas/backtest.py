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
