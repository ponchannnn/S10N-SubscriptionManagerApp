# このファイルは `bin/rails db:seed` で実行される(doc §7.7)。
# 何度実行しても重複しないよう、サービス・プランは slug / (service, cycle) で
# find_or_initialize_by してから属性を上書きする。

require "yaml"

# ---------------------------------------------------------------
# 定番サービスのマスタ
# ---------------------------------------------------------------
services_data = YAML.load_file(Rails.root.join("db/seeds/services.yml"))

services_data.each do |data|
  plans_data = data.fetch("plans")
  service = Service.find_or_initialize_by(slug: data.fetch("slug"))
  service.assign_attributes(data.except("plans"))
  service.save!

  plans_data.each_with_index do |plan_data, index|
    plan = service.service_plans.find_or_initialize_by(cycle: plan_data.fetch("cycle"))
    plan.assign_attributes(plan_data)
    plan.position = index
    plan.save!
  end

  puts "service: #{service.slug} (#{service.service_plans.count} plan(s))"
end

# ---------------------------------------------------------------
# 開発用デモユーザーと契約
# (submane/src/dummy_data.py と同じ内容。ダミーデータから本物のAPIに
#  切り替えたときに見た目が変わらず比較しやすいようにしている)
# ---------------------------------------------------------------
user = User.find_or_initialize_by(email_address: "demo@example.com")
user.password = "password123" if user.new_record?
user.save!
puts "user: #{user.email_address}"

DemoSubscription = Struct.new(:slug, :joined_at, :trial_ends_at, :cancelled, keyword_init: true)

demo_subscriptions = [
  DemoSubscription.new(slug: "netflix", joined_at: "2025-04-12T20:15"),
  DemoSubscription.new(slug: "spotify", joined_at: "2024-11-03T08:40"),
  DemoSubscription.new(slug: "audible", joined_at: "2025-01-20T22:05", cancelled: true),
  DemoSubscription.new(slug: "unext", joined_at: "2026-09-20T21:00", trial_ends_at: "2026-10-20T21:00"),
  DemoSubscription.new(slug: "amazon-prime", joined_at: "2023-10-18T12:30"),
  DemoSubscription.new(slug: "youtube-premium", joined_at: "2025-07-01T19:00"),
  DemoSubscription.new(slug: "disney-plus", joined_at: "2025-12-24T10:00"),
  DemoSubscription.new(slug: "fod-premium", joined_at: "2025-03-08T23:10", cancelled: true),
  DemoSubscription.new(slug: "dazn", joined_at: "2026-02-14T18:45"),
  DemoSubscription.new(slug: "apple-music", joined_at: "2024-06-30T09:20"),
  DemoSubscription.new(slug: "adobe-cc", joined_at: "2025-11-05T14:00"),
  DemoSubscription.new(slug: "hulu", joined_at: "2026-01-31T21:30"),
  DemoSubscription.new(slug: "kindle-unlimited", joined_at: "2026-09-28T07:50", trial_ends_at: "2026-10-28T07:50"),
  DemoSubscription.new(slug: "lemino", joined_at: "2025-05-17T16:25", cancelled: true),
  DemoSubscription.new(slug: "abema-premium", joined_at: "2026-03-22T22:00"),
  DemoSubscription.new(slug: "icloud-plus", joined_at: "2023-08-09T11:11"),
  DemoSubscription.new(slug: "d-anime-store", joined_at: "2026-04-06T00:30"),
  DemoSubscription.new(slug: "nhk-on-demand", joined_at: "2025-08-15T13:00", cancelled: true),
]

demo_subscriptions.each do |demo|
  service = Service.find_by!(slug: demo.slug)
  plan = service.service_plans.first
  joined_at = Time.zone.parse(demo.joined_at)

  subscription = user.subscriptions.find_or_initialize_by(service: service)
  subscription.service_plan = plan
  subscription.joined_at = joined_at
  subscription.trial_ends_at = demo.trial_ends_at ? Time.zone.parse(demo.trial_ends_at) : nil
  subscription.cancelled_at = demo.cancelled ? joined_at + 90.days : nil
  subscription.save!
end

puts "subscriptions: #{user.subscriptions.count}"
