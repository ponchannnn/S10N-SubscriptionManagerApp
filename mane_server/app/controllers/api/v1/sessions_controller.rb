module Api
  module V1
    # ログイン・ログアウト(POST/DELETE /session)。
    class SessionsController < ApplicationController
      allow_unauthenticated_access only: :create
      rate_limit to: 10, within: 3.minutes, only: :create, with: -> {
        render json: { error: { code: "rate_limited", message: "しばらくしてから、もう一度お試しください。" } },
               status: :too_many_requests
      }

      def create
        user = User.authenticate_by(email_address: params[:email], password: params[:password])
        if user
          start_new_session_for(user)
          render json: UserSerializer.new(user), status: :ok
        else
          render json: { error: { code: "invalid_credentials", message: "メールアドレスまたはパスワードが違います。" } },
                 status: :unauthorized
        end
      end

      def destroy
        terminate_session
        head :no_content
      end
    end
  end
end
