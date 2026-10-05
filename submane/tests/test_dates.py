"""logic/dates.py のテスト。"""

from datetime import datetime

from logic import dates


def sub(joined_at, cycle="monthly", status="active", trial_end_at=None):
    return {"joined_at": joined_at, "cycle": cycle, "status": status, "trial_end_at": trial_end_at, "amount": 1000}


def test_monthly_next_payment():
    s = sub("2026-09-20T21:00")
    assert dates.next_payment_at(s, datetime(2026, 10, 5, 9, 0)) == datetime(2026, 10, 20, 21, 0)


def test_same_day_before_and_after_time():
    s = sub("2026-09-20T21:00")
    assert dates.next_payment_at(s, datetime(2026, 10, 20, 20, 59)) == datetime(2026, 10, 20, 21, 0)
    assert dates.next_payment_at(s, datetime(2026, 10, 20, 21, 0)) == datetime(2026, 11, 20, 21, 0)


def test_month_end_is_clamped_without_drift():
    s = sub("2026-01-31T10:00")
    assert dates.next_payment_at(s, datetime(2026, 2, 1)) == datetime(2026, 2, 28, 10, 0)
    assert dates.next_payment_at(s, datetime(2026, 3, 1)) == datetime(2026, 3, 31, 10, 0)
    assert dates.next_payment_at(s, datetime(2026, 4, 1)) == datetime(2026, 4, 30, 10, 0)


def test_august_31():
    s = sub("2026-08-31T10:00")
    assert dates.next_payment_at(s, datetime(2026, 9, 1)) == datetime(2026, 9, 30, 10, 0)
    assert dates.next_payment_at(s, datetime(2026, 10, 1)) == datetime(2026, 10, 31, 10, 0)


def test_leap_day_yearly():
    s = sub("2024-02-29T12:00", cycle="yearly")
    assert dates.next_payment_at(s, datetime(2024, 3, 1)) == datetime(2025, 2, 28, 12, 0)
    assert dates.next_payment_at(s, datetime(2027, 3, 1)) == datetime(2028, 2, 29, 12, 0)


def test_yearly_across_new_year():
    s = sub("2025-12-15T08:00", cycle="yearly")
    assert dates.next_payment_at(s, datetime(2026, 1, 3)) == datetime(2026, 12, 15, 8, 0)


def test_monthly_across_new_year():
    s = sub("2025-11-25T08:00")
    assert dates.next_payment_at(s, datetime(2025, 12, 26)) == datetime(2026, 1, 25, 8, 0)


def test_cancelled_has_no_payment():
    s = sub("2026-01-10T10:00", status="cancelled")
    assert dates.next_payment_at(s, datetime(2026, 5, 1)) is None
    assert dates.payment_in_month(s, 2026, 5) is None


def test_trial_uses_trial_end():
    s = sub("2026-09-20T21:00", status="trial", trial_end_at="2026-10-20T21:00")
    assert dates.next_payment_at(s, datetime(2026, 10, 5)) == datetime(2026, 10, 20, 21, 0)
    assert dates.payment_in_month(s, 2026, 9) is None
    assert dates.payment_in_month(s, 2026, 10) == datetime(2026, 10, 20, 21, 0)
    assert dates.payment_in_month(s, 2026, 11) == datetime(2026, 11, 20, 21, 0)


def test_payment_in_month_before_join_and_yearly():
    monthly = sub("2026-03-10T10:00")
    assert dates.payment_in_month(monthly, 2026, 2) is None
    assert dates.payment_in_month(monthly, 2026, 3) == datetime(2026, 3, 10, 10, 0)
    yearly = sub("2025-11-05T14:00", cycle="yearly")
    assert dates.payment_in_month(yearly, 2026, 10) is None
    assert dates.payment_in_month(yearly, 2026, 11) == datetime(2026, 11, 5, 14, 0)
