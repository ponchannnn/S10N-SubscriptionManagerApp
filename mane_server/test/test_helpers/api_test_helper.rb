# integration test から signup/login を1行で済ませるためのヘルパー。
# 以降の同じテスト内のリクエストには、integration test が自動で保持する
# Cookie(session_id)がそのまま乗る。
module ApiTestHelper
  def sign_up!(email: "user#{rand(1_000_000)}@example.com", password: "password123")
    post api_v1_signup_path, params: { email: email, password: password }, as: :json
    JSON.parse(response.body)
  end
end

ActiveSupport.on_load(:action_dispatch_integration_test) do
  include ApiTestHelper
end
