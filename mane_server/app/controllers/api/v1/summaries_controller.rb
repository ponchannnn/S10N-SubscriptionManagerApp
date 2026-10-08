module Api
  module V1
    # 月の支払い見込み・内訳・前月差分(doc §6.6 GET /summary)。
    class SummariesController < ApplicationController
      def show
        month = params[:month].present? ? Date.strptime(params[:month], "%Y-%m") : Date.current
        yearly = params[:yearly] == "prorated" ? "prorated" : "lump"

        subscriptions = Current.user.subscriptions.to_a
        total, items = summarize(subscriptions, month, yearly)
        previous_total, = summarize(subscriptions, month.prev_month, yearly)

        render json: {
          month: month.strftime("%Y-%m"),
          yearly: yearly,
          total: total,
          previous_total: previous_total,
          diff: total - previous_total,
          items: items,
        }
      end

      private

      def summarize(subscriptions, month, yearly)
        items = subscriptions.filter_map do |sub|
          amount, dates = Billing.monthly_amount(sub, month, yearly: yearly)
          next if amount.zero?
          {
            subscription_id: sub.id,
            name: sub.display_name,
            icon: sub.custom? ? nil : absolute_url(sub.service&.icon_path),
            color: sub.custom? ? nil : sub.service&.color,
            cycle: sub.cycle,
            amount: amount,
            payment_dates: dates.map { |date| date.strftime("%Y-%m-%dT%H:%M%:z") },
          }
        end
        items.sort_by! { |item| -item[:amount] }
        [items.sum { |item| item[:amount] }, items]
      end

      def absolute_url(path)
        return nil if path.blank?
        request.base_url + path
      end
    end
  end
end
