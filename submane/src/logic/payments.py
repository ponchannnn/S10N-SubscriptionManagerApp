"""支払い見込みの計算。README 7章のルールをここ1か所にまとめる。

年額プランの扱いは2通りから選べる:
  MODE_BILLING : 更新月に全額を計上する(実際に引き落とされる月)
  MODE_AVERAGE : 12で割って毎月に計上する(月あたりの負担)
"""

from logic import dates

MODE_BILLING = "billing"
MODE_AVERAGE = "average"


def amount_in_month(sub: dict, year: int, month: int, mode: str = MODE_BILLING) -> int:
    """そのサブスクが指定した年月に支払う見込み額(円)を返す。"""
    if sub.get("status") == "cancelled":
        return 0
    amount = int(sub.get("amount") or 0)
    if mode == MODE_AVERAGE and sub.get("cycle") == "yearly":
        anchor = dates.payment_anchor(sub)
        if anchor is None or (year, month) < (anchor.year, anchor.month):
            return 0
        return round(amount / 12)
    return amount if dates.payment_in_month(sub, year, month) else 0


def month_total(subs: list[dict], year: int, month: int, mode: str = MODE_BILLING) -> int:
    """指定した年月の支払い見込み総額を返す。"""
    return sum(amount_in_month(sub, year, month, mode) for sub in subs)


def previous_month(year: int, month: int) -> tuple[int, int]:
    """前月の (年, 月) を返す。"""
    return (year - 1, 12) if month == 1 else (year, month - 1)


def next_month(year: int, month: int) -> tuple[int, int]:
    """翌月の (年, 月) を返す。"""
    return (year + 1, 1) if month == 12 else (year, month + 1)


def summarize(subs: list[dict], year: int, month: int, mode: str = MODE_BILLING) -> dict:
    """内訳画面に必要な値をまとめて返す。

    戻り値:
      total          : 当月の支払い見込み総額
      previous_total : 前月の支払い見込み総額
      diff           : 当月 − 前月
      items          : 金額が多い順の [{"sub": サブスク, "amount": 金額, "ratio": 割合(0〜1)}]
    """
    items = []
    for sub in subs:
        amount = amount_in_month(sub, year, month, mode)
        if amount > 0:
            items.append({"sub": sub, "amount": amount})
    items.sort(key=lambda item: item["amount"], reverse=True)
    total = sum(item["amount"] for item in items)
    for item in items:
        item["ratio"] = item["amount"] / total if total else 0.0
    previous_total = month_total(subs, *previous_month(year, month), mode)
    return {
        "total": total,
        "previous_total": previous_total,
        "diff": total - previous_total,
        "items": items,
    }
