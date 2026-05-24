from __future__ import annotations

from datetime import date

import pandas as pd

from schemas.features import FlowStrengthResult


def _streak(series: pd.Series) -> int:  # type: ignore[type-arg]
    """Count consecutive same-sign values at tail. Positive = buying, negative = selling."""
    if series.empty:
        return 0
    last_positive = float(series.iloc[-1]) > 0
    count = 0
    for val in reversed(series.tolist()):
        if (float(val) > 0) == last_positive:
            count += 1
        else:
            break
    return count if last_positive else -count


def _zscore(series: pd.Series, window: int) -> float:  # type: ignore[type-arg]
    """Rolling z-score of the last value. Returns 0.0 when std is zero or NaN."""
    rolling = series.rolling(window)
    mean = float(rolling.mean().iloc[-1])
    std = float(rolling.std().iloc[-1])
    if pd.isna(std) or std == 0.0:
        return 0.0
    return (float(series.iloc[-1]) - mean) / std


def _ratio(net: float, buy: float, sell: float) -> float:
    """Directional conviction: net / total_flow. Range [-1, 1]."""
    total = abs(buy) + abs(sell)
    return net / total if total > 0.0 else 0.0


def compute_flow_strength(
    flow_history: pd.DataFrame,
    zscore_window: int = 20,
) -> FlowStrengthResult:
    """Compute FII/DII flow strength metrics from a historical flow DataFrame.

    Args:
        flow_history: DataFrame with columns fii_net, fii_buy, fii_sell,
                      dii_net, dii_buy, dii_sell. Sorted ascending by date.
        zscore_window: Rolling window size for z-score normalisation.

    Returns:
        FlowStrengthResult for the most recent row.

    Raises:
        ValueError: If fewer rows than zscore_window are provided.
    """
    if len(flow_history) < zscore_window:
        raise ValueError(
            f"flow_history must have at least {zscore_window} rows, got {len(flow_history)}"
        )

    last = flow_history.iloc[-1]

    return FlowStrengthResult(
        as_of=date.today(),
        fii_zscore=_zscore(flow_history["fii_net"], zscore_window),
        fii_ratio=_ratio(float(last["fii_net"]), float(last["fii_buy"]), float(last["fii_sell"])),
        fii_streak=_streak(flow_history["fii_net"]),
        dii_zscore=_zscore(flow_history["dii_net"], zscore_window),
        dii_ratio=_ratio(float(last["dii_net"]), float(last["dii_buy"]), float(last["dii_sell"])),
        dii_streak=_streak(flow_history["dii_net"]),
        net_institutional=float(last["fii_net"]) + float(last["dii_net"]),
    )
