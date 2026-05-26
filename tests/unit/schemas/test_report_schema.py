import pytest
from pydantic import ValidationError
from schemas.report import EvidenceBlock


def test_evidence_block_valid():
    block = EvidenceBlock(
        name="RELIANCE_FUNDAMENTALS",
        content="PE=28.0, ROE=0.12",
        confidence=0.9,
        source="YFinance fundamentals",
    )
    assert block.name == "RELIANCE_FUNDAMENTALS"
    assert block.confidence == 0.9


def test_evidence_block_confidence_too_high_raises():
    with pytest.raises(ValidationError):
        EvidenceBlock(name="X", content="y", confidence=1.5, source="z")


def test_evidence_block_confidence_negative_raises():
    with pytest.raises(ValidationError):
        EvidenceBlock(name="X", content="y", confidence=-0.1, source="z")


def test_evidence_block_zero_confidence_valid():
    block = EvidenceBlock(name="X", content="No data available", confidence=0.0, source="missing")
    assert block.confidence == 0.0
