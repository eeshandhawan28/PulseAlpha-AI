from __future__ import annotations

import pytest

from features.ipo_gmp import compute_gmp_disagreement
from schemas.connectors import ConnectorError, ConnectorResult
from schemas.features import IPOGMPResult


def make_ok_result(
    issue_price: float,
    gmp: float,
    qib: float,
    hni: float,
    retail: float,
) -> ConnectorResult:
    return ConnectorResult(
        source="ipo_gmp_ipowatch",
        ticker="TestIPO",
        data={
            "company_name": "Test IPO Ltd",
            "issue_price": issue_price,
            "gmp": gmp,
            "qib_subscription": qib,
            "hni_subscription": hni,
            "retail_subscription": retail,
        },
        confidence=0.9,
    )


def make_error_result() -> ConnectorResult:
    return ConnectorResult(
        source="ipo_gmp_ipowatch",
        ticker="FAIL",
        data={},
        confidence=0.0,
        error=ConnectorError(code="PARSE_ERROR", message="no table", retryable=False),
    )


def test_gmp_returns_none_when_connector_failed() -> None:
    assert compute_gmp_disagreement(make_error_result()) is None


def test_gmp_implied_return_correct() -> None:
    """gmp=100, issue_price=500 → implied_return=0.20"""
    result = compute_gmp_disagreement(
        make_ok_result(issue_price=500.0, gmp=100.0, qib=50.0, hni=30.0, retail=5.0)
    )
    assert result is not None
    assert result.gmp_implied_return == pytest.approx(0.20)


def test_gmp_disagreement_score_is_nonnegative_float() -> None:
    result = compute_gmp_disagreement(
        make_ok_result(issue_price=500.0, gmp=75.0, qib=40.0, hni=20.0, retail=5.0)
    )
    assert result is not None
    assert isinstance(result.disagreement_score, float)
    assert result.disagreement_score >= 0.0


def test_gmp_data_available_true_on_success() -> None:
    result = compute_gmp_disagreement(
        make_ok_result(issue_price=400.0, gmp=50.0, qib=10.0, hni=5.0, retail=2.0)
    )
    assert result is not None
    assert result.data_available is True


def test_gmp_high_disagreement_when_gmp_high_qib_low() -> None:
    """High GMP + minimal QIB → high disagreement vs low GMP + strong QIB."""
    high_conflict = compute_gmp_disagreement(
        make_ok_result(issue_price=500.0, gmp=250.0, qib=1.0, hni=1.0, retail=1.0)
    )
    low_conflict = compute_gmp_disagreement(
        make_ok_result(issue_price=500.0, gmp=25.0, qib=80.0, hni=50.0, retail=10.0)
    )
    assert high_conflict is not None and low_conflict is not None
    assert high_conflict.disagreement_score > low_conflict.disagreement_score


def test_gmp_with_qib_history_uses_percentile_normalization() -> None:
    """Passing qib_history changes the institutional_signal — result must not crash."""
    result = compute_gmp_disagreement(
        make_ok_result(issue_price=500.0, gmp=100.0, qib=30.0, hni=20.0, retail=5.0),
        qib_history=[10.0, 50.0, 100.0, 30.0, 20.0],
    )
    assert result is not None
    assert 0.0 <= result.institutional_signal <= 1.0
