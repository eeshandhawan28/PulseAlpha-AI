from __future__ import annotations

from datetime import date, timedelta
from typing import Literal


def _next_monday(d: date) -> date:
    """Return d if d is Monday, else the next Monday."""
    days_ahead = (7 - d.weekday()) % 7  # Monday = 0
    return d + timedelta(days=days_ahead)


def generate_sample_dates(
    start: date,
    end: date,
    frequency: Literal["monthly", "weekly"],
) -> list[date]:
    """Generate sample dates for backtesting.

    monthly: first Monday on or after the 1st of each calendar month in [start, end]
    weekly: every Monday in [start, end]
    """
    if start > end:
        return []

    results: list[date] = []

    if frequency == "monthly":
        year, month = start.year, start.month
        while True:
            first_of_month = date(year, month, 1)
            sample = _next_monday(first_of_month)
            if sample > end:
                break
            if sample >= start:
                results.append(sample)
            # Advance to next month
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
            if date(year, month, 1) > end:
                break
    else:  # weekly
        current = _next_monday(start)
        while current <= end:
            results.append(current)
            current += timedelta(weeks=1)

    return results
