from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class AuditEntry(BaseModel):
    node: str
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class CouncilOutput(BaseModel):
    persona: str
    stance: Literal["bullish", "bearish", "neutral"]
    rationale: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    citations: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    claim: str
    source: str
    url: str | None = None
    timestamp: datetime | None = None


class AnalysisState(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_query: str
    ticker_universe: list[str]

    market_data: dict[str, Any] = Field(default_factory=dict)
    alt_data: dict[str, Any] = Field(default_factory=dict)
    sentiment: dict[str, Any] = Field(default_factory=dict)
    rotation: dict[str, Any] = Field(default_factory=dict)

    council_outputs: list[CouncilOutput] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    divergence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    citations: list[Citation] = Field(default_factory=list)
    report: str | None = None
    charts: list[dict[str, Any]] = Field(default_factory=list)
    as_of_date: date | None = None

    audit_log: list[AuditEntry] = Field(default_factory=list)

    @field_validator("ticker_universe")
    @classmethod
    def ticker_universe_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("ticker_universe must contain at least one ticker")
        cleaned = [t.upper().strip() for t in v]
        if not all(cleaned):
            raise ValueError("ticker_universe items must be non-empty after stripping")
        return cleaned

    def append_audit(self, node: str, message: str, **metadata: Any) -> None:
        self.audit_log.append(AuditEntry(node=node, message=message, metadata=metadata))
