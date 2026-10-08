# 状態・次回支払日時・月の支払い見込みを計算する(doc §4, §7.5)。
# 次回支払日時・支払い見込みはAPI側で計算してレスポンスに含め、DBには保存しない。
module Billing
  module_function

  def months_per_cycle(sub) = sub.cycle == "yearly" ? 12 : 1

  def anchor(sub) = sub.trial_ends_at || sub.joined_at

  def status(sub, now: Time.current)
    return "cancelled" if sub.cancelled_at
    return "trial" if sub.trial_ends_at && now < sub.trial_ends_at
    "active"
  end

  # 基準日時から n 周期後(月末は自動で月末に寄る)
  def payment_at(sub, n) = anchor(sub).advance(months: n * months_per_cycle(sub))

  def next_payment_at(sub, now: Time.current)
    return nil if sub.cancelled_at
    m = months_per_cycle(sub)
    elapsed = (now.year - anchor(sub).year) * 12 + (now.month - anchor(sub).month)
    n = [elapsed / m, 0].max
    n += 1 while payment_at(sub, n) <= now
    payment_at(sub, n)
  end

  # range(月初〜月末)に入る支払日時の一覧
  def payments_in(sub, range)
    return [] if sub.cancelled_at
    m = months_per_cycle(sub)
    elapsed = (range.begin.year - anchor(sub).year) * 12 + (range.begin.month - anchor(sub).month)
    n = [elapsed / m - 1, 0].max
    dates = []
    loop do
      t = payment_at(sub, n)
      break if t > range.end
      dates << t if t >= range.begin
      n += 1
    end
    dates
  end

  # month: Date(その月の1日扱い)、yearly: "lump"(更新月に全額) / "prorated"(月割り)
  def monthly_amount(sub, month, yearly: "lump")
    return [0, []] if sub.cancelled_at
    range = month.in_time_zone.beginning_of_month..month.in_time_zone.end_of_month
    if sub.cycle == "yearly" && yearly == "prorated"
      amount = anchor(sub) <= range.end ? (sub.amount / 12.0).round : 0
      return [amount, []]
    end
    dates = payments_in(sub, range)
    [dates.size * sub.amount, dates]
  end
end
