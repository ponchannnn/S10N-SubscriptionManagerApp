module Api
  module V1
    # 自分の契約の一覧・取得・登録・編集・削除(doc §6.5)。
    class SubscriptionsController < ApplicationController
      before_action :set_subscription, only: %i[show update destroy]

      def index
        subscriptions = Current.user.subscriptions.order(:created_at)
        render json: {
          subscriptions: subscriptions.map { |sub| SubscriptionSerializer.new(sub, base_url: request.base_url) },
          server_time: Time.current.strftime("%Y-%m-%dT%H:%M%:z"),
        }
      end

      def show
        render json: SubscriptionSerializer.new(@subscription, base_url: request.base_url)
      end

      def create
        subscription = Current.user.subscriptions.new(subscription_params)
        if subscription.save
          render json: SubscriptionSerializer.new(subscription, base_url: request.base_url), status: :created
        else
          render_validation_error(subscription)
        end
      end

      def update
        # statusでのtrial指定だけはここで弾く(trial_ends_atで設定するものなので)。(doc §6.5)
        if params[:status] == "trial"
          return render json: { error: { code: "validation_error", message: "入力内容に誤りがあります",
                                          details: { status: ["trialは指定できません。trial_ends_atで設定してください"] } } },
                        status: :unprocessable_entity
        end

        apply_status_change! if params[:status].present?

        if @subscription.update(subscription_params)
          render json: SubscriptionSerializer.new(@subscription, base_url: request.base_url)
        else
          render_validation_error(@subscription)
        end
      end

      def destroy
        @subscription.destroy
        head :no_content
      end

      private

      def set_subscription
        @subscription = Current.user.subscriptions.find(params[:id])
      end

      # JSONのキーは plan_id だが、DBの外部キー列は service_plan_id。
      def subscription_params
        attrs = params.permit(:service_id, :plan_id, :custom_name, :custom_join_url, :custom_cancel_url,
                               :custom_cancel_memo, :plan_name, :amount, :cycle, :joined_at, :trial_ends_at, :memo)
        attrs[:service_plan_id] = attrs.delete(:plan_id) if attrs.key?(:plan_id)
        attrs
      end

      def apply_status_change!
        case params[:status]
        when "cancelled"
          @subscription.cancelled_at = params[:cancelled_at].presence || Time.current
        when "active"
          @subscription.cancelled_at = nil
          @subscription.trial_ends_at = nil
          @subscription.joined_at = params[:joined_at].presence || Time.current
        end
      end
    end
  end
end
