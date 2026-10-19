require "test_helper"

class Api::V1::SessionsControllerTest < ActionDispatch::IntegrationTest
  setup do
    @email = "login@example.com"
    @password = "password123"
    User.create!(email_address: @email, password: @password)
  end

  test "login with correct credentials returns 200 and sets a cookie" do
    post api_v1_session_path, params: { email: @email, password: @password }, as: :json

    assert_response :success
    assert cookies["session_id"].present?
    body = JSON.parse(response.body)
    assert_equal @email, body.dig("user", "email")
  end

  test "login with the wrong password returns 401 without revealing which field was wrong" do
    post api_v1_session_path, params: { email: @email, password: "wrongpassword" }, as: :json

    assert_response :unauthorized
    body = JSON.parse(response.body)
    assert_equal "invalid_credentials", body.dig("error", "code")
  end

  test "logout returns 204 and ends the session" do
    post api_v1_session_path, params: { email: @email, password: @password }, as: :json

    delete api_v1_session_path
    assert_response :no_content

    get api_v1_me_path
    assert_response :unauthorized
  end
end
