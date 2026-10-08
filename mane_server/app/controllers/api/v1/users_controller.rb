module Api
  module V1
    # 自分の情報(doc §6.1 GET /me)。起動時のログイン確認にも使う。
    class UsersController < ApplicationController
      def show
        render json: UserSerializer.new(Current.user)
      end
    end
  end
end
