# 定番サービス1件のJSON(doc §6.2)。
class ServiceSerializer
  def initialize(service, base_url:)
    @service = service
    @base_url = base_url
  end

  def as_json(*)
    {
      id: service.id,
      slug: service.slug,
      name: service.name,
      name_kana: service.name_kana,
      category: service.category,
      icon: absolute_url(service.icon_path),
      color: service.color,
      join_url: service.join_url,
      cancel_url: service.cancel_url,
      cancel_memo: service.cancel_memo,
      has_free_trial: service.has_free_trial,
      default_trial_days: service.default_trial_days,
      plans: service.service_plans.active.order(:position).map do |plan|
        { id: plan.id, name: plan.name, amount: plan.amount, cycle: plan.cycle }
      end,
    }
  end

  private

  attr_reader :service

  def absolute_url(path)
    return nil if path.blank?
    @base_url + path
  end
end
