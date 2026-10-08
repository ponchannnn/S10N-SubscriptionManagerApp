class Service < ApplicationRecord
  has_many :service_plans, dependent: :destroy
  has_many :subscriptions, dependent: :nullify

  validates :slug, presence: true, uniqueness: true
  validates :name, presence: true
end
