from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field


class ModelTier(str, Enum):
    HF_API = "hf_api"
    OLLAMA = "ollama"
    PAID = "paid"


class RoutingConfig(BaseModel):
    default_tier: ModelTier = ModelTier.HF_API
    divergence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    confidence_threshold: float = Field(default=0.4, ge=0.0, le=1.0)
    daily_paid_cap_usd: float = Field(default=2.0, gt=0)
    per_request_token_budget: int = Field(default=4096, gt=0)
    degraded_mode: bool = False
