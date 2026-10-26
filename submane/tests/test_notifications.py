"""logic/notifications.py のテスト。"""

from datetime import datetime

from logic.notifications import KIND_RENEWAL, KIND_TRIAL_END, upcoming_notices

NOW = datetime(2026, 10, 26, 12, 0)


def _monthly(sub_id, joined_at, status="active", **extra):
    return {"id": sub_id, "name": f"S{sub_id}", "cycle": "monthly", "amount": 1000,
            "joined_at": joined_at, "status": status, **extra}


def test_within_seven_days_is_included_and_eighth_day_is_not():
    subs = [_monthly(1, "2026-01-02T10:00"), _monthly(2, "2026-01-03T10:00")]
    notices = upcoming_notices(subs, NOW)
    assert [(n["sub"]["id"], n["days_left"]) for n in notices] == [(1, 7)]


def test_same_day_later_time_counts_as_zero_days():
    notices = upcoming_notices([_monthly(1, "2026-01-26T18:00")], NOW)
    assert [(n["days_left"], n["kind"]) for n in notices] == [(0, KIND_RENEWAL)]


def test_cancelled_is_excluded():
    assert upcoming_notices([_monthly(1, "2026-01-28T10:00", status="cancelled")], NOW) == []


def test_trial_uses_trial_end_and_its_own_kind():
    trial = _monthly(1, "2026-10-01T10:00", status="trial", trial_end_at="2026-10-30T10:00")
    notices = upcoming_notices([trial], NOW)
    assert [(n["days_left"], n["kind"]) for n in notices] == [(4, KIND_TRIAL_END)]


def test_sorted_by_nearest_date():
    subs = [_monthly(1, "2026-01-31T10:00"), _monthly(2, "2026-01-27T10:00"), _monthly(3, "2026-01-29T10:00")]
    assert [n["sub"]["id"] for n in upcoming_notices(subs, NOW)] == [2, 3, 1]
