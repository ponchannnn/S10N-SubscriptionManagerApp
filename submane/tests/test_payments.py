"""logic/payments.py と logic/ordering.py のテスト。"""

from logic import ordering, payments

SUBS = [
    {"id": 1, "name": "月額A", "cycle": "monthly", "amount": 1000, "joined_at": "2025-01-10T10:00", "status": "active"},
    {"id": 2, "name": "年額B", "cycle": "yearly", "amount": 12000, "joined_at": "2025-11-05T10:00", "status": "active"},
    {"id": 3, "name": "解約C", "cycle": "monthly", "amount": 500, "joined_at": "2025-01-10T10:00", "status": "cancelled"},
    {"id": 4, "name": "試用D", "cycle": "monthly", "amount": 2000, "joined_at": "2026-09-20T10:00", "status": "trial",
     "trial_end_at": "2026-10-20T10:00"},
]


def test_billing_mode_counts_yearly_only_in_renewal_month():
    assert payments.month_total(SUBS, 2026, 10) == 1000 + 2000
    assert payments.month_total(SUBS, 2026, 11) == 1000 + 12000 + 2000


def test_average_mode_splits_yearly():
    assert payments.month_total(SUBS, 2026, 10, payments.MODE_AVERAGE) == 1000 + 1000 + 2000
    # 入会前の月には計上しない
    assert payments.amount_in_month(SUBS[1], 2025, 10, payments.MODE_AVERAGE) == 0


def test_cancelled_is_excluded_and_trial_starts_at_trial_end():
    assert payments.amount_in_month(SUBS[2], 2026, 10) == 0
    assert payments.amount_in_month(SUBS[3], 2026, 9) == 0
    assert payments.amount_in_month(SUBS[3], 2026, 10) == 2000


def test_summarize():
    result = payments.summarize(SUBS, 2026, 11)
    assert result["total"] == 15000
    assert result["previous_total"] == 3000
    assert result["diff"] == 12000
    assert [item["sub"]["id"] for item in result["items"]] == [2, 4, 1]
    assert abs(sum(item["ratio"] for item in result["items"]) - 1.0) < 1e-9


def test_summarize_empty_month():
    result = payments.summarize(SUBS, 2024, 1)
    assert result["total"] == 0 and result["items"] == [] and result["diff"] == 0


def test_month_helpers():
    assert payments.previous_month(2026, 1) == (2025, 12)
    assert payments.next_month(2026, 12) == (2027, 1)


def test_ordering_keeps_cancelled_last():
    by_frequency = [s["id"] for s in ordering.sort_subscriptions(SUBS, ordering.ORDER_FREQUENCY)]
    assert by_frequency == [1, 4, 2, 3]
    by_registered = [s["id"] for s in ordering.sort_subscriptions(SUBS, ordering.ORDER_REGISTERED)]
    assert by_registered == [1, 2, 4, 3]
    assert ordering.count_by_status(SUBS) == {"active": 3, "trial": 1, "cancelled": 1}
