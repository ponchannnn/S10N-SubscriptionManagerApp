class ServicePlan < ApplicationRecord
  CYCLES = %w[monthly yearly].freeze

  belongs_to :service
  has_many :subscriptions, dependent: :nullify

  validates :name, presence: true
  validates :amount, presence: true, numericality: { only_integer: true, greater_than_or_equal_to: 0 }
  validates :cycle, inclusion: { in: CYCLES }

  scope :active, -> { where(active: true) }
end
