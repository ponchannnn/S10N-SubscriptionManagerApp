class CreateServices < ActiveRecord::Migration[8.1]
  def change
    create_table :services do |t|
      t.string :slug, null: false, index: { unique: true }
      t.string :name, null: false
      t.string :name_kana
      t.string :keywords
      t.string :category
      t.string :icon_path
      t.string :color
      t.string :join_url
      t.string :cancel_url
      t.text :cancel_memo
      t.boolean :has_free_trial, null: false, default: false
      t.integer :default_trial_days
      t.date :url_checked_on
      t.boolean :active, null: false, default: true

      t.timestamps
    end
  end
end
