module Api
  module V1
    # 会員登録(doc §6.1 POST /signup)。登録に成功したらそのままログイン状態にする。
    class RegistrationsController < ApplicationController
      allow_unauthenticated_access only: :create

      def create
        user = User.new(email_address: params.require(:email), password: params[:password])
        if user.save
          start_new_session_for(user)
          render json: UserSerializer.new(user), status: :created
        else
          render json: { error: { code: "validation_error", message: "入力内容に誤りがあります",
                                   details: api_error_details(user) } },
                 status: :unprocessable_entity
        end
      end

      private

      # バリデーションはDBの列名(email_address)基準だが、JSONのキーはemailにそろえる
      def api_error_details(record)
        record.errors.to_hash.transform_keys { |key| key == :email_address ? :email : key }
      end
    end
  end
end
