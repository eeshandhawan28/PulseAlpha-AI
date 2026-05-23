from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ConnectorError(BaseModel):
    code: str
    message: str
    retryable: bool = True


class ConnectorResult(BaseModel):
    source: str
    ticker: str
    data: dict[str, Any]
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    freshness_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    error: ConnectorError | None = None

    @model_validator(mode="after")
    def _validate_consistency(self) -> ConnectorResult:
        if self.error is None and not self.data:
            # An empty-data result with no error is logged as a warning but allowed.
            # ok will return False in this case — callers should treat it as failed.
            pass
        return self

    @property
    def ok(self) -> bool:
        """True only when there is no error AND data is non-empty."""
        return self.error is None and bool(self.data)
