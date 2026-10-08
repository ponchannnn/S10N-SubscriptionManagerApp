class CreateSubscriptions < ActiveRecord::Migration[8.1]
  def change
    create_table :subscriptions do |t|
      t.references :user, null: false, foreign_key: { on_delete: :cascade }
      t.references :service, foreign_key: true
      t.references :service_plan, foreign_key: true
      t.string :custom_name
      t.string :custom_join_url
      t.string :custom_cancel_url
      t.text :custom_cancel_memo
      t.string :plan_name
      t.integer :amount, null: false
      t.string :cycle, null: false
      t.datetime :joined_at, null: false
      t.datetime :trial_ends_at
      t.datetime :cancelled_at
      t.text :memo

      t.timestamps
    end
    add_check_constraint :subscriptions, "amount >= 0", name: "amount_non_negative"
    add_check_constraint :subscriptions, "service_id IS NOT NULL OR custom_name IS NOT NULL", name: "service_or_custom_name"
  end
end
