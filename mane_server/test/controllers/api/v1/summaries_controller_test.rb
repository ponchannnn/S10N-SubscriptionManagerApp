require "test_helper"

class Api::V1::SummariesControllerTest < ActionDispatch::IntegrationTest
  setup do
    sign_up!
  end

  test "lump vs prorated totals for a mix of monthly and yearly subscriptions (doc §4.4/§6.6)" do
    post api_v1_subscriptions_path, params: { custom_name: "月額", amount: 1000, cycle: "monthly",
                                               joined_at: "2026-04-12T10:00" }, as: :json
    post api_v1_subscriptions_path, params: { custom_name: "年額", amount: 12000, cycle: "yearly",
                                               joined_at: "2025-11-01T08:00" }, as: :json

    get api_v1_summary_path, params: { month: "2026-10", yearly: "lump" }
    body = JSON.parse(response.body)
    assert_equal 1000, body["total"]
    assert_equal ["月額"], body["items"].map { |i| i["name"] }

    get api_v1_summary_path, params: { month: "2026-10", yearly: "prorated" }
    body = JSON.parse(response.body)
    assert_equal 2000, body["total"]
    # 月額・年額とも1,000円で同額になるため、順序は問わずに比較する
    assert_equal ["年額", "月額"].sort, body["items"].map { |i| i["name"] }.sort
  end

  test "diff compares against the previous month (computed from today's subscription data)" do
    post api_v1_subscriptions_path, params: { custom_name: "年額", amount: 12000, cycle: "yearly",
                                               joined_at: "2025-11-01T08:00" }, as: :json

    get api_v1_summary_path, params: { month: "2026-11", yearly: "lump" }
    body = JSON.parse(response.body)
    assert_equal 12000, body["total"]
    assert_equal 0, body["previous_total"]
    assert_equal 12000, body["diff"]
  end

  test "defaults to the current month and lump when params are omitted" do
    travel_to Time.zone.parse("2026-10-05 12:00") do
      get api_v1_summary_path
      body = JSON.parse(response.body)
      assert_equal "2026-10", body["month"]
      assert_equal "lump", body["yearly"]
    end
  end

  test "requires authentication" do
    delete api_v1_session_path
    get api_v1_summary_path
    assert_response :unauthorized
  end
end
