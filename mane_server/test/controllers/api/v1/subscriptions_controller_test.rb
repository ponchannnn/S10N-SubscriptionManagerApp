require "test_helper"

class Api::V1::SubscriptionsControllerTest < ActionDispatch::IntegrationTest
  setup do
    sign_up!(email: "owner@example.com")
    @service = Service.create!(slug: "netflix", name: "Netflix")
    @plan = @service.service_plans.create!(name: "月額プラン", amount: 1500, cycle: "monthly", position: 0)
  end

  test "create with service_id/plan_id copies amount/cycle/plan_name from the plan" do
    post api_v1_subscriptions_path,
         params: { service_id: @service.id, plan_id: @plan.id, joined_at: "2026-01-20T12:00" }, as: :json

    assert_response :created
    body = JSON.parse(response.body)
    assert_equal "Netflix", body["name"]
    assert_equal 1500, body["amount"]
    assert_equal "monthly", body["cycle"]
    assert_equal "月額プラン", body["plan_name"]
    assert_equal false, body["is_custom"]
  end

  test "create a custom (service-less) subscription" do
    post api_v1_subscriptions_path,
         params: { custom_name: "オンラインサロン", amount: 980, cycle: "monthly", joined_at: "2026-02-01T10:00" },
         as: :json

    assert_response :created
    body = JSON.parse(response.body)
    assert_equal "オンラインサロン", body["name"]
    assert_equal true, body["is_custom"]
    assert_nil body["icon"]
  end

  test "create without a service_id or custom_name returns 422" do
    post api_v1_subscriptions_path, params: { amount: 500, cycle: "monthly", joined_at: "2026-01-01T10:00" }, as: :json

    assert_response 422
    body = JSON.parse(response.body)
    assert_includes body.dig("error", "details", "custom_name"), "を入力してください"
  end

  test "create with a plan_id that isn't a real plan returns 422, not a 500" do
    post api_v1_subscriptions_path,
         params: { custom_name: "x", service_id: @service.id, plan_id: 999_999,
                   amount: 500, cycle: "monthly", joined_at: "2026-01-01T10:00" },
         as: :json

    assert_response 422
    assert_includes JSON.parse(response.body).dig("error", "details", "plan_id"), "はこのサービスのプランではありません"
  end

  test "index only returns the current user's subscriptions, with server_time" do
    post api_v1_subscriptions_path, params: { custom_name: "自分の契約", amount: 100, cycle: "monthly",
                                               joined_at: "2026-01-01T10:00" }, as: :json

    other = User.create!(email_address: "other@example.com", password: "password123")
    other.subscriptions.create!(custom_name: "他人の契約", amount: 200, cycle: "monthly",
                                 joined_at: Time.zone.parse("2026-01-01T10:00"))

    get api_v1_subscriptions_path
    assert_response :success
    body = JSON.parse(response.body)
    assert_equal ["自分の契約"], body["subscriptions"].map { |s| s["name"] }
    assert body["server_time"].present?
  end

  test "show returns 404 for another user's subscription" do
    other = User.create!(email_address: "other2@example.com", password: "password123")
    other_sub = other.subscriptions.create!(custom_name: "他人の契約", amount: 200, cycle: "monthly",
                                             joined_at: Time.zone.parse("2026-01-01T10:00"))

    get api_v1_subscription_path(other_sub.id)
    assert_response :not_found
  end

  test "update changes only the sent fields" do
    post api_v1_subscriptions_path, params: { custom_name: "対象", amount: 100, cycle: "monthly",
                                               joined_at: "2026-01-01T10:00" }, as: :json
    id = JSON.parse(response.body)["id"]

    patch api_v1_subscription_path(id), params: { memo: "更新したメモ" }, as: :json

    assert_response :success
    body = JSON.parse(response.body)
    assert_equal "更新したメモ", body["memo"]
    assert_equal "対象", body["name"]
  end

  test "status: cancelled sets cancelled_at, status: active clears it and updates joined_at" do
    post api_v1_subscriptions_path, params: { custom_name: "対象", amount: 100, cycle: "monthly",
                                               joined_at: "2026-01-01T10:00" }, as: :json
    id = JSON.parse(response.body)["id"]

    patch api_v1_subscription_path(id), params: { status: "cancelled" }, as: :json
    assert_equal "cancelled", JSON.parse(response.body)["status"]

    patch api_v1_subscription_path(id), params: { status: "active", joined_at: "2026-03-01T09:00" }, as: :json
    body = JSON.parse(response.body)
    assert_equal "active", body["status"]
    assert_equal "2026-03-01T09:00+09:00", body["joined_at"]
    assert_nil body["cancelled_at"]
  end

  test "status: trial is rejected, since trial is set via trial_ends_at" do
    post api_v1_subscriptions_path, params: { custom_name: "対象", amount: 100, cycle: "monthly",
                                               joined_at: "2026-01-01T10:00" }, as: :json
    id = JSON.parse(response.body)["id"]

    patch api_v1_subscription_path(id), params: { status: "trial" }, as: :json
    assert_response 422
  end

  test "destroy removes the subscription" do
    post api_v1_subscriptions_path, params: { custom_name: "対象", amount: 100, cycle: "monthly",
                                               joined_at: "2026-01-01T10:00" }, as: :json
    id = JSON.parse(response.body)["id"]

    delete api_v1_subscription_path(id)
    assert_response :no_content

    get api_v1_subscription_path(id)
    assert_response :not_found
  end

  test "requires authentication" do
    delete api_v1_session_path
    get api_v1_subscriptions_path
    assert_response :unauthorized
  end
end
