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
    fii_streak: int  # positive = buying streak, negative = selling streak
    dii_zscore: float
    dii_ratio: float
    dii_streak: int
    net_institutional: float


class IPOGMPResult(BaseModel):
    company_name: str
    issue_price: float
    gmp: float
    gmp_implied_return: float  # unbounded — can exceed 1.0
    institutional_signal: float = Field(ge=0.0, le=1.0)  # normalized 0-1
    retail_signal: float = Field(ge=0.0, le=1.0)  # normalized 0-1
    disagreement_score: float  # unbounded — abs difference
    data_available: bool


class DivergenceResult(BaseModel):
    divergence_score: float = Field(ge=0.0, le=1.0)
    contradictions: list[str]
    majority_direction: Literal["bullish", "bearish", "neutral"]
    signal_votes: dict[str, str]
