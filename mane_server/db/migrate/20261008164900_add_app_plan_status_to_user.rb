class AddAppPlanStatusToUser < ActiveRecord::Migration[8.1]
  def change
    add_column :users, :app_plan_status, :string, null: false, default: "trial"
    add_column :users, :app_trial_ends_at, :datetime
  end
end
