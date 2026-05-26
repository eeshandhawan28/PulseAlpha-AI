from schemas.report import EvidenceBlock
from schemas.state import Citation
from worker.report.parser import parse_citations


def _blocks() -> dict[str, EvidenceBlock]:
    return {
        "RELIANCE_FUNDAMENTALS": EvidenceBlock(
            name="RELIANCE_FUNDAMENTALS", content="PE=28", confidence=0.9, source="s"
        ),
        "COUNCIL_STANCES": EvidenceBlock(
            name="COUNCIL_STANCES", content="bullish", confidence=0.8, source="s"
        ),
    }


def test_valid_tag_returns_citation():
    text = "Reliance has a PE of 28 [SRC:RELIANCE_FUNDAMENTALS:pe_ratio] which is below average."
    citations = parse_citations(text, _blocks())
    assert len(citations) == 1
    assert citations[0].source == "RELIANCE_FUNDAMENTALS"
    assert "Reliance has a PE of 28" in citations[0].claim


def test_unknown_block_is_dropped():
    text = "Some claim [SRC:UNKNOWN_BLOCK:field] about markets."
    citations = parse_citations(text, _blocks())
    assert len(citations) == 0


def test_no_tags_returns_empty_list():
    text = "This report has no citation tags at all."
    citations = parse_citations(text, _blocks())
    assert citations == []


def test_multiple_tags_in_one_line_returns_multiple_citations():
    text = "Bullish stance [SRC:COUNCIL_STANCES:Contrarian] with strong PE [SRC:RELIANCE_FUNDAMENTALS:pe_ratio]."
    citations = parse_citations(text, _blocks())
    assert len(citations) == 2
    sources = {c.source for c in citations}
    assert "COUNCIL_STANCES" in sources
    assert "RELIANCE_FUNDAMENTALS" in sources


def test_citation_claim_is_the_full_line():
    text = "Line one.\nReliance PE is strong [SRC:RELIANCE_FUNDAMENTALS:pe_ratio].\nLine three."
    citations = parse_citations(text, _blocks())
    assert len(citations) == 1
    assert "Reliance PE is strong" in citations[0].claim


def test_citations_are_citation_instances():
    text = "A claim [SRC:RELIANCE_FUNDAMENTALS:pe_ratio] here."
    citations = parse_citations(text, _blocks())
    assert all(isinstance(c, Citation) for c in citations)


def test_url_and_timestamp_are_none():
    text = "A claim [SRC:COUNCIL_STANCES:Contrarian] here."
    citations = parse_citations(text, _blocks())
    assert citations[0].url is None
    assert citations[0].timestamp is None
