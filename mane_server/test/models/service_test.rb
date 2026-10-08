require "test_helper"

class ServiceTest < ActiveSupport::TestCase
  test "valid with a slug and name" do
    assert Service.new(slug: "example", name: "Example").valid?
  end

  test "invalid without a slug or name" do
    service = Service.new
    assert_not service.valid?
    assert_includes service.errors[:slug], "を入力してください"
    assert_includes service.errors[:name], "を入力してください"
  end

  test "slug must be unique" do
    Service.create!(slug: "netflix", name: "Netflix")
    duplicate = Service.new(slug: "netflix", name: "別名")
    assert_not duplicate.valid?
    assert_includes duplicate.errors[:slug], "は既に使用されています"
  end

  test "active scope only returns active: true" do
    active = Service.create!(slug: "active-one", name: "Active", active: true)
    Service.create!(slug: "inactive-one", name: "Inactive", active: false)
    assert_equal [active], Service.active.to_a
  end
end
