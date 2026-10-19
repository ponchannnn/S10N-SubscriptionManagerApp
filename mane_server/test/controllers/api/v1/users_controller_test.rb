require "test_helper"

class Api::V1::UsersControllerTest < ActionDispatch::IntegrationTest
  test "GET /me returns the signed-in user" do
    sign_up!(email: "me@example.com")

    get api_v1_me_path
    assert_response :success
    assert_equal "me@example.com", JSON.parse(response.body).dig("user", "email")
  end

  test "GET /me without a session returns 401" do
    get api_v1_me_path
    assert_response :unauthorized
  end
end
