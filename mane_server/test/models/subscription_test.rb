require "test_helper"

class SubscriptionTest < ActiveSupport::TestCase
  setup do
    @user = User.create!(email_address: "sub-test@example.com", password: "password123")
    @service = Service.create!(slug: "sub-test-service", name: "テストサービス")
    @plan = @service.service_plans.create!(name: "月額プラン", amount: 1000, cycle: "monthly", position: 0)
  end

  def build(**attrs)
    Subscription.new({ user: @user, joined_at: Time.zone.parse("2026-01-01 12:00"), amount: 1000, cycle: "monthly" }.merge(attrs))
  end

  test "valid with a master service and plan" do
    sub = build(service: @service, service_plan: @plan)
    assert sub.valid?
  end

  test "valid with a custom (service-less) entry" do
    sub = build(custom_name: "手入力サービス")
    assert sub.valid?
  end

  test "invalid without a service and without a custom_name" do
    sub = build
    assert_not sub.valid?
    assert_includes sub.errors[:custom_name], "を入力してください"
  end

  test "copy_from_plan fills amount/cycle/plan_name from the selected plan" do
    yearly_plan = @service.service_plans.create!(name: "年額プラン", amount: 12000, cycle: "yearly", position: 1)
    sub = Subscription.new(user: @user, service: @service, service_plan: yearly_plan, joined_at: Time.zone.parse("2026-01-01 12:00"))
    assert sub.valid?, sub.errors.full_messages.join(", ")
    assert_equal 12000, sub.amount
    assert_equal "yearly", sub.cycle
    assert_equal "年額プラン", sub.plan_name
  end

  test "copy_from_plan does not override an explicitly given amount" do
    sub = build(service: @service, service_plan: @plan, amount: 500)
    sub.valid?
    assert_equal 500, sub.amount
  end

  test "invalid when plan_id does not belong to the selected service" do
    other_service = Service.create!(slug: "other-service", name: "別サービス")
    other_plan = other_service.service_plans.create!(name: "プラン", amount: 500, cycle: "monthly", position: 0)
    sub = build(service: @service, service_plan: other_plan)
    assert_not sub.valid?
    assert_includes sub.errors[:plan_id], "はこのサービスのプランではありません"
  end

  test "invalid when plan_id does not exist at all (not just a 500 from the DB)" do
    sub = build(custom_name: "x", service_plan_id: 999_999)
    assert_not sub.valid?
    assert_includes sub.errors[:plan_id], "はこのサービスのプランではありません"
  end

  test "invalid when trial_ends_at is before joined_at" do
    sub = build(custom_name: "x", joined_at: Time.zone.parse("2026-02-01 00:00"),
                trial_ends_at: Time.zone.parse("2026-01-01 00:00"))
    assert_not sub.valid?
    assert_includes sub.errors[:trial_ends_at], "は入会日時以降にしてください"
  end

  test "invalid when a custom URL does not start with http(s)" do
    sub = build(custom_name: "x", custom_join_url: "javascript:alert(1)")
    assert_not sub.valid?
    assert_not_empty sub.errors[:custom_join_url]
  end

  test "custom? reflects whether a master service is attached" do
    assert build(service: @service, service_plan: @plan).custom? == false
    assert build(custom_name: "x").custom?
  end

  test "display_name/join_url/cancel_url fall back from custom fields to the service" do
    @service.update!(join_url: "https://example.com/join", cancel_url: "https://example.com/cancel")
    sub = build(service: @service)
    assert_equal @service.name, sub.display_name
    assert_equal "https://example.com/join", sub.join_url

    custom = build(custom_name: "手入力", custom_join_url: "https://custom.example.com/join")
    assert_equal "手入力", custom.display_name
    assert_equal "https://custom.example.com/join", custom.join_url
  end

  test "the DB rejects a negative amount even if a validation is bypassed" do
    sub = build(custom_name: "x")
    sub.save!
    assert_raises(ActiveRecord::StatementInvalid) do
      Subscription.connection.execute(
        "UPDATE subscriptions SET amount = -1 WHERE id = #{sub.id}"
      )
    end
  end
end
