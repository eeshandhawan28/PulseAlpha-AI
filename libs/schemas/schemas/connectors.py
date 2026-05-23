from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ConnectorError(BaseModel):
    code: str
    message: str
    retryable: bool = True


class ConnectorResult(BaseModel):
    source: str
    ticker: str
    data: dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    freshness_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    error: ConnectorError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.data)
