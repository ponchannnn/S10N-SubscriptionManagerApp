class CreateServicePlans < ActiveRecord::Migration[8.1]
  def change
    create_table :service_plans do |t|
      t.references :service, null: false, foreign_key: true
      t.string :name, null: false
      t.integer :amount, null: false
      t.string :cycle, null: false
      t.integer :position, null: false, default: 0
      t.boolean :active, null: false, default: true

      t.timestamps
    end
  end
end
