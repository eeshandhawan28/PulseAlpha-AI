from schemas.report import EvidenceBlock
from schemas.state import Citation
from worker.report.flags import apply_confidence_flags

_LOW = EvidenceBlock(name="LOW_BLOCK", content="x", confidence=0.3, source="s")
_HIGH = EvidenceBlock(name="HIGH_BLOCK", content="x", confidence=0.8, source="s")
_BLOCKS = {"LOW_BLOCK": _LOW, "HIGH_BLOCK": _HIGH}


def _citation(source: str, claim: str = "Some claim") -> Citation:
    return Citation(claim=claim, source=source, url=None, timestamp=None)


def test_low_confidence_appends_warning():
    citations = [_citation("LOW_BLOCK", "Claim about low source")]
    result = apply_confidence_flags(citations, _BLOCKS)
    assert "⚠ low-confidence source" in result[0].claim


def test_high_confidence_unchanged():
    citations = [_citation("HIGH_BLOCK", "Claim about high source")]
    result = apply_confidence_flags(citations, _BLOCKS)
    assert "⚠" not in result[0].claim
    assert result[0].claim == "Claim about high source"


def test_empty_citations_returns_empty():
    result = apply_confidence_flags([], _BLOCKS)
    assert result == []


def test_exactly_at_threshold_is_not_flagged():
    blocks = {
        "EDGE_BLOCK": EvidenceBlock(name="EDGE_BLOCK", content="x", confidence=0.5, source="s")
    }
    citations = [_citation("EDGE_BLOCK", "Edge case claim")]
    result = apply_confidence_flags(citations, blocks)
    assert "⚠" not in result[0].claim


def test_custom_threshold():
    citations = [_citation("HIGH_BLOCK", "High confidence claim")]
    # threshold=0.9 means confidence=0.8 should be flagged
    result = apply_confidence_flags(citations, _BLOCKS, threshold=0.9)
    assert "⚠ low-confidence source" in result[0].claim


def test_original_citations_not_mutated():
    original_claim = "Original claim"
    citations = [_citation("LOW_BLOCK", original_claim)]
    apply_confidence_flags(citations, _BLOCKS)
    # original list item should not be mutated — function returns new list
    assert citations[0].claim == original_claim


def test_multiple_citations_flagged_correctly():
    citations = [
        _citation("LOW_BLOCK", "Low claim"),
        _citation("HIGH_BLOCK", "High claim"),
    ]
    result = apply_confidence_flags(citations, _BLOCKS)
    assert "⚠" in result[0].claim
    assert "⚠" not in result[1].claim
