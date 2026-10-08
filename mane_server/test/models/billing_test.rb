require "test_helper"

# doc §4.5のテストケースをそのまま確認する。Billingは属性を読むだけなので
# DBに保存する必要はなく、Subscription.newで組み立てた値で十分。
class BillingTest < ActiveSupport::TestCase
  CASES = [
    # [cycle, joined_at, trial_ends_at, cancelled_at, 期待status, 期待next_payment_at]
    ["monthly", "2026-04-12 10:00", nil, nil, "active", "2026-10-12 10:00"],
    ["monthly", "2026-10-05 09:00", nil, nil, "active", "2026-11-05 09:00"],
    ["monthly", "2026-08-31 20:00", nil, nil, "active", "2026-10-31 20:00"],
    ["monthly", "2026-01-31 20:00", nil, nil, "active", "2026-10-31 20:00"],
    ["yearly", "2025-11-01 08:00", nil, nil, "active", "2026-11-01 08:00"],
    ["yearly", "2024-02-29 10:00", nil, nil, "active", "2027-02-28 10:00"],
    ["monthly", "2026-10-01 10:00", "2026-10-31 23:59", nil, "trial", "2026-10-31 23:59"],
    ["monthly", "2026-09-01 10:00", "2026-09-30 10:00", nil, "active", "2026-10-30 10:00"],
    ["monthly", "2026-03-10 10:00", nil, "2026-09-20 15:00", "cancelled", nil],
  ].freeze

  def build_subscription(cycle:, joined_at:, trial_ends_at: nil, cancelled_at: nil, amount: 1000)
    Subscription.new(
      cycle: cycle,
      joined_at: Time.zone.parse(joined_at),
      trial_ends_at: trial_ends_at && Time.zone.parse(trial_ends_at),
      cancelled_at: cancelled_at && Time.zone.parse(cancelled_at),
      amount: amount,
    )
  end

  test "status and next_payment_at match doc §4.5's table (now = 2026-10-05 12:00)" do
    travel_to Time.zone.parse("2026-10-05 12:00") do
      CASES.each_with_index do |(cycle, joined_at, trial_ends_at, cancelled_at, expected_status, expected_next), index|
        sub = build_subscription(cycle: cycle, joined_at: joined_at, trial_ends_at: trial_ends_at, cancelled_at: cancelled_at)
        assert_equal expected_status, Billing.status(sub), "case ##{index + 1}: status"
        if expected_next
          assert_equal Time.zone.parse(expected_next), Billing.next_payment_at(sub), "case ##{index + 1}: next_payment_at"
        else
          assert_nil Billing.next_payment_at(sub), "case ##{index + 1}: next_payment_at"
        end
      end
    end
  end

  test "month-end anchor is re-derived each cycle instead of drifting (1/31 -> 2/28)" do
    travel_to Time.zone.parse("2026-02-10 00:00") do
      sub = build_subscription(cycle: "monthly", joined_at: "2026-01-31 00:00")
      assert_equal Time.zone.parse("2026-02-28 00:00"), Billing.next_payment_at(sub)
    end
  end

  test "next payment date correctly crosses a year boundary" do
    travel_to Time.zone.parse("2026-12-20 00:00") do
      sub = build_subscription(cycle: "monthly", joined_at: "2026-06-15 00:00")
      assert_equal Time.zone.parse("2027-01-15 00:00"), Billing.next_payment_at(sub)
    end
  end

  test "monthly_amount totals for October match doc §4.5 (lump vs prorated)" do
    travel_to Time.zone.parse("2026-10-05 12:00") do
      sub1 = build_subscription(cycle: "monthly", joined_at: "2026-04-12 10:00", amount: 1000)
      sub5 = build_subscription(cycle: "yearly", joined_at: "2025-11-01 08:00", amount: 12000)
      sub7 = build_subscription(cycle: "monthly", joined_at: "2026-10-01 10:00",
                                 trial_ends_at: "2026-10-31 23:59", amount: 1500)
      sub9 = build_subscription(cycle: "monthly", joined_at: "2026-03-10 10:00",
                                 cancelled_at: "2026-09-20 15:00", amount: 990)
      subscriptions = [sub1, sub5, sub7, sub9]
      month = Date.new(2026, 10, 1)

      lump_total = subscriptions.sum { |sub| Billing.monthly_amount(sub, month, yearly: "lump").first }
      assert_equal 2500, lump_total

      prorated_total = subscriptions.sum { |sub| Billing.monthly_amount(sub, month, yearly: "prorated").first }
      assert_equal 3500, prorated_total
    end
  end
end
