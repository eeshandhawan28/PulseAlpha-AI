from schemas.report import EvidenceBlock
from worker.report.prompt import SECTION_HEADERS, build_report_prompt


def _blocks() -> dict[str, EvidenceBlock]:
    return {
        "RELIANCE.NS_FUNDAMENTALS": EvidenceBlock(
            name="RELIANCE.NS_FUNDAMENTALS", content="PE=28.0", confidence=0.9, source="s"
        ),
        "FII_DII_FLOWS": EvidenceBlock(
            name="FII_DII_FLOWS", content="FII net: 500", confidence=0.8, source="s"
        ),
        "COUNCIL_STANCES": EvidenceBlock(
            name="COUNCIL_STANCES", content="Contrarian: bullish", confidence=0.8, source="s"
        ),
        "DIVERGENCE_SUMMARY": EvidenceBlock(
            name="DIVERGENCE_SUMMARY", content="Score: 0.2", confidence=0.8, source="s"
        ),
    }


def test_prompt_contains_all_seven_section_headers():
    prompt = build_report_prompt(_blocks(), "Analyze Reliance")
    for header in SECTION_HEADERS:
        assert header in prompt, f"Missing section header: {header}"


def test_prompt_contains_user_query():
    prompt = build_report_prompt(_blocks(), "Analyze Reliance Industries")
    assert "Analyze Reliance Industries" in prompt


def test_prompt_contains_evidence_content():
    prompt = build_report_prompt(_blocks(), "test query")
    assert "PE=28.0" in prompt
    assert "FII net: 500" in prompt


def test_prompt_instructs_no_citation_tags():
    prompt = build_report_prompt(_blocks(), "test")
    # The prompt explicitly tells the LLM NOT to use [SRC:...] citation tags
    assert "Do NOT include [SRC:" in prompt or "citation tags" in prompt


def test_prompt_contains_block_names():
    prompt = build_report_prompt(_blocks(), "test")
    assert "RELIANCE.NS_FUNDAMENTALS" in prompt
    assert "FII_DII_FLOWS" in prompt


def test_section_headers_has_seven_items():
    assert len(SECTION_HEADERS) == 7
