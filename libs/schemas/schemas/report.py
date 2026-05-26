from __future__ import annotations

from pydantic import BaseModel, Field


class EvidenceBlock(BaseModel):
    name: str
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: str
