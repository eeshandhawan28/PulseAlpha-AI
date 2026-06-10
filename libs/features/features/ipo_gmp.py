from __future__ import annotations

import math

from schemas.connectors import ConnectorResult
from schemas.features import IPOGMPResult

# Upper bounds used when no historical data is provided for normalization.
_QIB_UPPER_BOUND = 100.0  # 100x QIB subscription treated as maximum
_RETAIL_UPPER_BOUND = 20.0  # 20x retail subscription treated as maximum


def compute_gmp_disagreement(
    connector_result: ConnectorResult,
    qib_history: list[float] | None = None,
) -> IPOGMPResult | None:
    """Compute GMP vs institutional demand disagreement score.

    Args:
        connector_result: Output from IPOGMPConnector.fetch(). Returns None
                          immediately if result.ok is False.
        qib_history: Historical QIB subscription multiples for percentile
                     normalization. Falls back to log-scale with a fixed upper
                     bound when None.

    Returns:
        IPOGMPResult with disagreement_score, or None if data unavailable.
    """
    if not connector_result.ok:
        return None

    data = connector_result.data
    issue_price = float(data["issue_price"])
    gmp = float(data["gmp"])
    qib = float(data["qib_subscription"])
    retail = float(data.get("retail_subscription", 1.0))

    gmp_implied_return = gmp / issue_price if issue_price > 0.0 else 0.0

    if qib_history and len(qib_history) > 0:
        max_qib = max(qib_history)
        institutional_signal = math.log1p(qib) / math.log1p(max_qib) if max_qib > 0.0 else 0.0
        # Retail uses its own fixed bound — QIB history is not applicable to retail multiples
        retail_signal = min(math.log1p(retail) / math.log1p(_RETAIL_UPPER_BOUND), 1.0)
    else:
        institutional_signal = min(math.log1p(qib) / math.log1p(_QIB_UPPER_BOUND), 1.0)
        retail_signal = min(math.log1p(retail) / math.log1p(_RETAIL_UPPER_BOUND), 1.0)

    return IPOGMPResult(
        company_name=str(data.get("company_name", "")),
        issue_price=issue_price,
        gmp=gmp,
        gmp_implied_return=gmp_implied_return,
        institutional_signal=institutional_signal,
        retail_signal=retail_signal,
        disagreement_score=gmp_implied_return * (1.0 - institutional_signal),
        data_available=True,
    )
