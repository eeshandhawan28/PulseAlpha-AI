from schemas.report import EvidenceBlock
from schemas.state import AnalysisState, CouncilOutput
from worker.report.evidence import build_evidence_blocks


def _full_state() -> AnalysisState:
    state = AnalysisState(user_query="Analyze", ticker_universe=["RELIANCE.NS"])
    state.market_data = {
        "RELIANCE.NS": {
            "fundamentals": {
                "pe_ratio": 28.0,
                "roe": 0.12,
                "market_cap": 1e12,
                "debt_to_equity": 0.3,
            },
            "ohlcv": [{"date": f"2026-01-{i + 1:02d}", "close": 100.0 + i} for i in range(30)],
            "_connector_confidence": {"fundamentals": 0.9, "ohlcv": 0.85},
        }
    }
    state.sentiment = {
        "RELIANCE.NS": {
            "headlines": [{"title": "Reliance posts strong Q4"}, {"title": "FII buying Reliance"}],
            "_connector_confidence": 0.7,
        }
    }
    state.rotation = {
        "points": [{"ticker": "RELIANCE.NS", "rs_ratio": 105.0, "rs_momentum": 102.0}]
    }
    state.alt_data = {
        "fii_dii": {"fii_net": 500.0, "dii_net": -100.0},
        "_fii_confidence": 0.8,
    }
    state.council_outputs = [
        CouncilOutput(persona="Contrarian", stance="bullish", rationale="r", confidence=0.8),
        CouncilOutput(persona="FirstPrinciples", stance="bullish", rationale="r", confidence=0.9),
        CouncilOutput(persona="Expansionist", stance="bullish", rationale="r", confidence=0.85),
        CouncilOutput(persona="Outsider", stance="neutral", rationale="r", confidence=0.6),
        CouncilOutput(persona="Synthesizer", stance="bullish", rationale="r", confidence=0.75),
    ]
    state.divergence_score = 0.2
    state.confidence = 0.75
    return state


def test_all_expected_blocks_present():
    state = _full_state()
    blocks = build_evidence_blocks(state)
    assert "RELIANCE.NS_FUNDAMENTALS" in blocks
    assert "RELIANCE.NS_OHLCV" in blocks
    assert "RELIANCE.NS_NEWS" in blocks
    assert "RELIANCE.NS_RRG" in blocks
    assert "RELIANCE.NS_ANNOUNCEMENTS" in blocks
    assert "RELIANCE.NS_SCREENER" in blocks
    assert "FII_DII_FLOWS" in blocks
    assert "COUNCIL_STANCES" in blocks
    assert "DIVERGENCE_SUMMARY" in blocks


def test_blocks_are_evidence_block_instances():
    state = _full_state()
    blocks = build_evidence_blocks(state)
    for block in blocks.values():
        assert isinstance(block, EvidenceBlock)


def test_missing_fundamentals_gives_zero_confidence():
    state = AnalysisState(user_query="q", ticker_universe=["TCS.NS"])
    blocks = build_evidence_blocks(state)
    assert "TCS.NS_FUNDAMENTALS" in blocks
    assert blocks["TCS.NS_FUNDAMENTALS"].confidence == 0.0
    assert blocks["TCS.NS_FUNDAMENTALS"].content == "No fundamental data available"


def test_council_stances_confidence_is_average():
    state = _full_state()
    blocks = build_evidence_blocks(state)
    # avg of 0.8, 0.9, 0.85, 0.6, 0.75 = 0.78
    assert abs(blocks["COUNCIL_STANCES"].confidence - 0.78) < 0.01


def test_divergence_summary_confidence_is_one_minus_score():
    state = _full_state()
    blocks = build_evidence_blocks(state)
    assert abs(blocks["DIVERGENCE_SUMMARY"].confidence - 0.8) < 0.01


def test_divergence_summary_content_has_contradictions():
    state = _full_state()
    state.contradictions = ["Bullish momentum vs bearish fundamentals"]
    blocks = build_evidence_blocks(state)
    assert "Bullish momentum" in blocks["DIVERGENCE_SUMMARY"].content


def test_rrg_block_shows_quadrant():
    state = _full_state()
    blocks = build_evidence_blocks(state)
    assert "Leading" in blocks["RELIANCE.NS_RRG"].content


def test_news_block_has_headlines():
    state = _full_state()
    blocks = build_evidence_blocks(state)
    assert "Reliance posts strong Q4" in blocks["RELIANCE.NS_NEWS"].content
