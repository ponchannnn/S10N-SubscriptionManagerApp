# This file is auto-generated from the current state of the database. Instead
# of editing this file, please use the migrations feature of Active Record to
# incrementally modify your database, and then regenerate this schema definition.
#
# This file is the source Rails uses to define your schema when running `bin/rails
# db:schema:load`. When creating a new database, `bin/rails db:schema:load` tends to
# be faster and is potentially less error prone than running all of your
# migrations from scratch. Old migrations may fail to apply correctly if those
# migrations use external dependencies or application code.
#
# It's strongly recommended that you check this file into your version control system.

ActiveRecord::Schema[8.1].define(version: 2026_10_08_164901) do
  # These are extensions that must be enabled in order to support this database
  enable_extension "pg_catalog.plpgsql"

  create_table "service_plans", force: :cascade do |t|
    t.bigint "service_id", null: false
    t.string "name", null: false
    t.integer "amount", null: false
    t.string "cycle", null: false
    t.integer "position", default: 0, null: false
    t.boolean "active", default: true, null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["service_id"], name: "index_service_plans_on_service_id"
  end

  create_table "services", force: :cascade do |t|
    t.string "slug", null: false
    t.string "name", null: false
    t.string "name_kana"
    t.string "keywords"
    t.string "category"
    t.string "icon_path"
    t.string "color"
    t.string "join_url"
    t.string "cancel_url"
    t.text "cancel_memo"
    t.boolean "has_free_trial", default: false, null: false
    t.integer "default_trial_days"
    t.date "url_checked_on"
    t.boolean "active", default: true, null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["slug"], name: "index_services_on_slug", unique: true
  end

  create_table "sessions", force: :cascade do |t|
    t.bigint "user_id", null: false
    t.string "ip_address"
    t.string "user_agent"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["user_id"], name: "index_sessions_on_user_id"
  end

  create_table "subscriptions", force: :cascade do |t|
    t.bigint "user_id", null: false
    t.bigint "service_id"
    t.bigint "service_plan_id"
    t.string "custom_name"
    t.string "custom_join_url"
    t.string "custom_cancel_url"
    t.text "custom_cancel_memo"
    t.string "plan_name"
    t.integer "amount", null: false
    t.string "cycle", null: false
    t.datetime "joined_at", null: false
    t.datetime "trial_ends_at"
    t.datetime "cancelled_at"
    t.text "memo"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["service_id"], name: "index_subscriptions_on_service_id"
    t.index ["service_plan_id"], name: "index_subscriptions_on_service_plan_id"
    t.index ["user_id"], name: "index_subscriptions_on_user_id"
    t.check_constraint "amount >= 0", name: "amount_non_negative"
    t.check_constraint "service_id IS NOT NULL OR custom_name IS NOT NULL", name: "service_or_custom_name"
  end

  create_table "users", force: :cascade do |t|
    t.string "email_address", null: false
    t.string "password_digest", null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.string "app_plan_status", default: "trial", null: false
    t.datetime "app_trial_ends_at"
    t.index ["email_address"], name: "index_users_on_email_address", unique: true
  end

  add_foreign_key "service_plans", "services"
  add_foreign_key "sessions", "users"
  add_foreign_key "subscriptions", "service_plans"
  add_foreign_key "subscriptions", "services"
  add_foreign_key "subscriptions", "users", on_delete: :cascade
end
