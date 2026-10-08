require "test_helper"

class UserTest < ActiveSupport::TestCase
  test "downcases and strips email_address" do
    user = User.new(email_address: " DOWNCASED@EXAMPLE.COM ")
    assert_equal("downcased@example.com", user.email_address)
  end

  test "email_address must be unique" do
    User.create!(email_address: "dup@example.com", password: "password123")
    duplicate = User.new(email_address: "dup@example.com", password: "password123")
    assert_not duplicate.valid?
    assert_includes duplicate.errors[:email_address], "は既に使用されています"
  end

  test "password must be at least 8 characters" do
    user = User.new(email_address: "short@example.com", password: "short")
    assert_not user.valid?
    assert_includes user.errors[:password], "は8文字以上で入力してください"
  end

  test "app_plan_status defaults to trial" do
    user = User.create!(email_address: "trial@example.com", password: "password123")
    assert_equal "trial", user.app_plan_status
  end
end
