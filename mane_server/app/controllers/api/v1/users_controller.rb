module Api
  module V1
    # 自分の情報(doc §6.1 GET /me)。起動時のログイン確認にも使う。
    class UsersController < ApplicationController
      def show
        render json: UserSerializer.new(Current.user)
      end

      # アカウント削除(doc §6.1 DELETE /me)。sessions・subscriptions は
      # User の dependent: :destroy で一緒に消える。
      def destroy
        cookies.delete(:session_id)
        Current.user.destroy
        head :no_content
      end
    end
  end
end
