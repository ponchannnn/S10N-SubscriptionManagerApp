require "test_helper"

class ServicePlanTest < ActiveSupport::TestCase
  setup do
    @service = Service.create!(slug: "plan-test-service", name: "テストサービス")
  end

  test "valid with name, amount, and a monthly or yearly cycle" do
    plan = @service.service_plans.new(name: "月額プラン", amount: 1000, cycle: "monthly")
    assert plan.valid?
  end

  test "invalid with a cycle other than monthly/yearly" do
    plan = @service.service_plans.new(name: "週額プラン", amount: 1000, cycle: "weekly")
    assert_not plan.valid?
    assert_includes plan.errors[:cycle], "は一覧にありません"
  end

  test "invalid with a negative amount" do
    plan = @service.service_plans.new(name: "プラン", amount: -1, cycle: "monthly")
    assert_not plan.valid?
    assert_not_empty plan.errors[:amount]
  end
end
