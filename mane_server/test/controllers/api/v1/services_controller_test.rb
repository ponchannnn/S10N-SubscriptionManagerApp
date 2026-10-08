require "test_helper"

class Api::V1::ServicesControllerTest < ActionDispatch::IntegrationTest
  setup do
    sign_up!

    @netflix = Service.create!(slug: "netflix", name: "Netflix", name_kana: "ねっとふりっくす", active: true)
    @netflix.service_plans.create!(name: "月額プラン", amount: 1500, cycle: "monthly", position: 0)
    @inactive = Service.create!(slug: "closed-service", name: "終了サービス", active: false)
  end

  test "index returns only active services, ordered by name, with their plans" do
    get api_v1_services_path
    assert_response :success

    services = JSON.parse(response.body)["services"]
    names = services.map { |s| s["name"] }
    assert_includes names, "Netflix"
    assert_not_includes names, "終了サービス"

    netflix = services.find { |s| s["slug"] == "netflix" }
    assert_equal [{ "id" => @netflix.service_plans.first.id, "name" => "月額プラン", "amount" => 1500, "cycle" => "monthly" }],
                 netflix["plans"]
  end

  test "q searches name and name_kana, case-insensitively" do
    get api_v1_services_path, params: { q: "NETF" }
    assert_equal ["Netflix"], JSON.parse(response.body)["services"].map { |s| s["name"] }

    get api_v1_services_path, params: { q: "ねっと" }
    assert_equal ["Netflix"], JSON.parse(response.body)["services"].map { |s| s["name"] }

    get api_v1_services_path, params: { q: "該当なし" }
    assert_equal [], JSON.parse(response.body)["services"]
  end

  test "requires authentication" do
    delete api_v1_session_path
    get api_v1_services_path
    assert_response :unauthorized
  end
end
