class Subscription < ApplicationRecord
  CYCLES = %w[monthly yearly].freeze

  belongs_to :user
  belongs_to :service, optional: true
  belongs_to :service_plan, optional: true

  before_validation :copy_from_plan

  validates :amount, numericality: { only_integer: true, greater_than_or_equal_to: 0 }
  validates :cycle, inclusion: { in: CYCLES }
  validates :joined_at, presence: true
  validates :custom_name, presence: true, if: -> { service_id.nil? }
  validates :custom_join_url, :custom_cancel_url,
            format: { with: %r{\Ahttps?://}, allow_blank: true }
  validate  :trial_after_join
  validate  :plan_belongs_to_service

  def display_name = custom_name.presence || service&.name
  def join_url     = custom_join_url.presence || service&.join_url
  def cancel_url   = custom_cancel_url.presence || service&.cancel_url
  def cancel_memo  = custom_cancel_memo.presence || service&.cancel_memo
  def custom?      = service_id.nil?

  private

  def copy_from_plan
    return unless service_plan
    self.amount    ||= service_plan.amount
    self.cycle     ||= service_plan.cycle
    self.plan_name ||= service_plan.name
  end

  def trial_after_join
    return if trial_ends_at.blank? || joined_at.blank?
    errors.add(:trial_ends_at, "は入会日時以降にしてください") if trial_ends_at < joined_at
  end

  def plan_belongs_to_service
    return if service_plan_id.blank?
    if service_plan.nil? || service_plan.service_id != service_id
      errors.add(:plan_id, "はこのサービスのプランではありません")
    end
  end
end
