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

  test "DELETE /me deletes the account, its subscriptions, and ends the session" do
    sign_up!(email: "delete-me@example.com")
    user = User.find_by!(email_address: "delete-me@example.com")
    user.subscriptions.create!(custom_name: "Test", amount: 100, cycle: "monthly",
                                joined_at: Time.current)

    delete api_v1_me_path
    assert_response :no_content

    assert_not User.exists?(user.id)
    assert_not Subscription.exists?(user_id: user.id)

    get api_v1_me_path
    assert_response :unauthorized
  end

  test "DELETE /me without a session returns 401" do
    delete api_v1_me_path
    assert_response :unauthorized
  end
end
