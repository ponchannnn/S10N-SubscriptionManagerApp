require "test_helper"

class Api::V1::RegistrationsControllerTest < ActionDispatch::IntegrationTest
  test "signup succeeds, sets a cookie, and returns the user shape (doc §6.1)" do
    post api_v1_signup_path, params: { email: "new@example.com", password: "password123" }, as: :json

    assert_response :created
    assert cookies["session_id"].present?
    body = JSON.parse(response.body)
    assert_equal "new@example.com", body.dig("user", "email")
    assert_equal "trial", body.dig("user", "app_plan", "status")
  end

  test "signup with an already-registered email returns 422 with details.email" do
    sign_up!(email: "dup@example.com")
    post api_v1_signup_path, params: { email: "dup@example.com", password: "password123" }, as: :json

    assert_response 422
    body = JSON.parse(response.body)
    assert_equal "validation_error", body.dig("error", "code")
    assert_includes body.dig("error", "details", "email"), "は既に使用されています"
  end

  test "signup with a short password returns 422 with details.password" do
    post api_v1_signup_path, params: { email: "short@example.com", password: "short" }, as: :json

    assert_response 422
    body = JSON.parse(response.body)
    assert_includes body.dig("error", "details", "password"), "は8文字以上で入力してください"
  end
end
