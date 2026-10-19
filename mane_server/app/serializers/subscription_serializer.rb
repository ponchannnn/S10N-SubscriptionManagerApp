# 契約1件のJSON(doc §6.4)。status・next_payment_atはBillingの計算結果(保存しない)。
class SubscriptionSerializer
  def initialize(subscription, base_url:)
    @subscription = subscription
    @base_url = base_url
  end

  def as_json(*)
    sub = subscription
    {
      id: sub.id,
      service_id: sub.service_id,
      name: sub.display_name,
      icon: sub.custom? ? nil : absolute_url(sub.service&.icon_path),
      color: sub.custom? ? nil : sub.service&.color,
      plan_id: sub.service_plan_id,
      plan_name: sub.plan_name,
      cycle: sub.cycle,
      amount: sub.amount,
      joined_at: format_time(sub.joined_at),
      trial_ends_at: format_time(sub.trial_ends_at),
      cancelled_at: format_time(sub.cancelled_at),
      status: Billing.status(sub),
      next_payment_at: format_time(Billing.next_payment_at(sub)),
      join_url: sub.join_url,
      cancel_url: sub.cancel_url,
      cancel_memo: sub.cancel_memo,
      is_custom: sub.custom?,
      memo: sub.memo,
      created_at: format_time(sub.created_at),
      updated_at: format_time(sub.updated_at),
    }
  end

  private

  attr_reader :subscription

  def format_time(time) = time&.strftime("%Y-%m-%dT%H:%M%:z")

  def absolute_url(path)
    return nil if path.blank?
    @base_url + path
  end
end
