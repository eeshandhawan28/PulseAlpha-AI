from __future__ import annotations

from datetime import date

from worker.backtest.sampler import generate_sample_dates


def test_monthly_returns_first_monday_of_each_month() -> None:
    dates = generate_sample_dates(date(2022, 1, 1), date(2022, 3, 31), "monthly")
    # Jan 2022: first Monday on/after Jan 1 = Jan 3 (Jan 1 is Saturday → Jan 3 Monday)
    assert date(2022, 1, 3) in dates
    # Feb 2022: first Monday on/after Feb 1 = Feb 7
    assert date(2022, 2, 7) in dates
    # Mar 2022: first Monday on/after Mar 1 = Mar 7
    assert date(2022, 3, 7) in dates
    assert len(dates) == 3


def test_weekly_returns_every_monday() -> None:
    dates = generate_sample_dates(date(2022, 1, 3), date(2022, 1, 31), "weekly")
    assert date(2022, 1, 3) in dates
    assert date(2022, 1, 10) in dates
    assert date(2022, 1, 17) in dates
    assert date(2022, 1, 24) in dates
    assert date(2022, 1, 31) in dates
    assert len(dates) == 5


def test_start_equals_end_returns_one_date() -> None:
    # Jan 3, 2022 is a Monday
    dates = generate_sample_dates(date(2022, 1, 3), date(2022, 1, 3), "monthly")
    assert dates == [date(2022, 1, 3)]


def test_start_after_end_returns_empty() -> None:
    dates = generate_sample_dates(date(2022, 6, 1), date(2022, 1, 1), "monthly")
    assert dates == []


def test_monthly_end_before_first_monday_returns_empty() -> None:
    # Jan 2 2022 is a Sunday; first Monday is Jan 3; end is Jan 2 → no dates
    dates = generate_sample_dates(date(2022, 1, 1), date(2022, 1, 2), "monthly")
    assert dates == []
