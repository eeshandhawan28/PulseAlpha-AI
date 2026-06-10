import pytest
from schemas.state import CouncilOutput
from worker.council.variance import compute_disagreement, majority_stance


def _out(persona: str, stance: str) -> CouncilOutput:
    return CouncilOutput(persona=persona, stance=stance, rationale="test", confidence=0.8)


def test_unanimous_disagreement_is_zero():
    outputs = [_out(f"P{i}", "bullish") for i in range(5)]
    assert compute_disagreement(outputs) == 0.0


def test_three_two_split_is_point_four():
    outputs = [
        _out("P1", "bullish"),
        _out("P2", "bullish"),
        _out("P3", "bullish"),
        _out("P4", "bearish"),
        _out("P5", "bearish"),
    ]
    assert compute_disagreement(outputs) == pytest.approx(0.4)


def test_two_two_one_split_is_point_six():
    outputs = [
        _out("P1", "bullish"),
        _out("P2", "bullish"),
        _out("P3", "bearish"),
        _out("P4", "bearish"),
        _out("P5", "neutral"),
    ]
    assert compute_disagreement(outputs) == pytest.approx(0.6)


def test_empty_outputs_is_zero():
    assert compute_disagreement([]) == 0.0


def test_majority_stance_returns_most_common():
    outputs = [_out("P1", "bullish"), _out("P2", "bullish"), _out("P3", "bearish")]
    assert majority_stance(outputs) == "bullish"


def test_majority_stance_empty_returns_neutral():
    assert majority_stance([]) == "neutral"
