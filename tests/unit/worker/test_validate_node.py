import pytest
from schemas.state import AnalysisState
from worker.nodes.validate import normalize_and_validate


def _make_full_state() -> AnalysisState:
    state = AnalysisState(user_query="test", ticker_universe=["RELIANCE.NS"])
    state.market_data = {"RELIANCE.NS": {"fundamentals": {"pe": 28.0}, "ohlcv": [{"close": 100.0}]}}
    state.alt_data = {"fii_dii": {"fii_net": 100.0}, "flow": {"fii_zscore": 1.0}, "gmp": None}
    state.sentiment = {"RELIANCE.NS": {"headlines": []}}
    state.rotation = {"points": [{"ticker": "RELIANCE.NS"}], "smoothing": 10, "momentum_lag": 1}
    state.divergence_score = 0.0
    return state


def _make_empty_state() -> AnalysisState:
    state = AnalysisState(user_query="test", ticker_universe=["RELIANCE.NS"])
    state.divergence_score = 0.5
    return state


@pytest.mark.asyncio
async def test_confidence_high_when_all_data_present():
    state = _make_full_state()
    result = await normalize_and_validate(state)
    assert result.confidence == 1.0


@pytest.mark.asyncio
async def test_confidence_low_when_all_data_missing():
    state = _make_empty_state()
    result = await normalize_and_validate(state)
    assert result.confidence == 0.25


@pytest.mark.asyncio
async def test_confidence_penalised_by_high_divergence():
    state = _make_full_state()
    state.divergence_score = 1.0
    result = await normalize_and_validate(state)

    state_zero_div = _make_full_state()
    state_zero_div.divergence_score = 0.0
    result_zero = await normalize_and_validate(state_zero_div)

    assert result.confidence < result_zero.confidence


@pytest.mark.asyncio
async def test_audit_log_has_final_entry():
    state = _make_full_state()
    result = await normalize_and_validate(state)
    assert any("normalize" in e.node or "validate" in e.node for e in result.audit_log)
