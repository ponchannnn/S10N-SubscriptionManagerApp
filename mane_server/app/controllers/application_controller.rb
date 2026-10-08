class ApplicationController < ActionController::API
  include ActionController::Cookies
  include Authentication

  rescue_from ActiveRecord::RecordNotFound do
    render json: { error: { code: "not_found", message: "見つかりません" } }, status: :not_found
  end

  rescue_from ActionController::ParameterMissing do |e|
    render json: { error: { code: "bad_request", message: e.message } }, status: :bad_request
  end

  private

  # ジェネレータの既定(ログイン画面へリダイレクト)を上書き
  def request_authentication
    render json: { error: { code: "unauthorized", message: "ログインしてください" } }, status: :unauthorized
  end

  def render_validation_error(record)
    render json: {
      error: { code: "validation_error", message: "入力内容に誤りがあります", details: record.errors.to_hash }
    }, status: :unprocessable_entity
  end
end
