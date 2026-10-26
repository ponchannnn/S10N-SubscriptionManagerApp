"""登録の境界値，並び順，解約・再契約で失うべき情報を検証する．"""
import pytest
from logic.subscriptions import (
    ValidationError, cancellation_patch, reactivation_patch,
    sort_subscriptions, validate_subscription, valid_url,
)


def record(**changes):
    """登録可能な基本データを作る．"""
    return {"name": "テスト", "plan_name": "月額", "amount": "1000", "cycle": "monthly",
            "status": "active", "joined_at": "2026-01-31T12:00", **changes}


def test_registration_normalizes_amount_and_preserves_manual_urls():
    data = validate_subscription(record(amount="１０００", join_url="https://example.com/join"))
    assert data["amount"] == 1000
    assert data["join_url"] == "https://example.com/join"


@pytest.mark.parametrize("changes,field", [
    ({"amount": "-1"}, "amount"), ({"amount": "1.5"}, "amount"),
    ({"amount": ""}, "amount"), ({"amount": "1000000000"}, "amount"),
    ({"name": " "}, "name"), ({"plan_name": ""}, "plan_name"),
    ({"joined_at": "2026-02-29T12:00"}, "joined_at"),
    ({"join_url": "javascript:alert(1)"}, "join_url"),
    ({"cancel_url": "https://user:pass@example.com"}, "cancel_url"),
    ({"cycle": "weekly"}, "cycle"), ({"status": "unknown"}, "status"),
    ({"status": "trial", "trial_ends_at": ""}, "trial_ends_at"),
    ({"status": "trial", "trial_ends_at": "2026-01-30T12:00"}, "trial_ends_at"),
])
def test_invalid_registration(changes, field):
    with pytest.raises(ValidationError) as raised:
        validate_subscription(record(**changes))
    assert field in raised.value.errors


def test_zero_yen_and_leap_day_are_valid():
    assert validate_subscription(record(amount="0", joined_at="2028-02-29T12:00"))["amount"] == 0


def test_trial_records_ending_and_cancellation_discards_it():
    data = validate_subscription(record(status="trial", trial_ends_at="2026-02-28T12:00"))
    assert data["trial_ends_at"] == "2026-02-28T12:00"
    cancelled = validate_subscription({**data, **cancellation_patch()})
    assert cancelled["trial_ends_at"] == ""
    assert cancelled["cancel_url"] == data["cancel_url"]


def test_reactivation_replaces_joined_date_and_clears_old_payment():
    patch = reactivation_patch(record(status="cancelled", next_payment_at="2026-02-28T12:00"), "2026-10-05T12:00")
    assert patch == {"status": "active", "joined_at": "2026-10-05T12:00"}


def test_sort_keeps_cancelled_last_and_does_not_mutate_input():
    items = [record(id="cancelled", status="cancelled"), record(id="year", cycle="yearly"), record(id="month")]
    assert [item["id"] for item in sort_subscriptions(items)] == ["month", "year", "cancelled"]
    assert [item["id"] for item in sort_subscriptions(items, "registered")] == ["year", "month", "cancelled"]
    assert [item["id"] for item in items] == ["cancelled", "year", "month"]


def test_deadline_sort_handles_unknown_dates_and_cancelled():
    items = [record(id="unknown"), record(id="later", next_payment_at="2026-12-01T00:00+09:00"),
             record(id="trial", status="trial", trial_ends_at="2026-10-10T00:00"),
             record(id="cancelled", status="cancelled", next_payment_at="2026-01-01T00:00")]
    assert [item["id"] for item in sort_subscriptions(items, "deadline")] == ["trial", "later", "unknown", "cancelled"]


@pytest.mark.parametrize("url", ["https://example.com", "http://example.com/path", ""])
def test_valid_url(url):
    assert valid_url(url)
