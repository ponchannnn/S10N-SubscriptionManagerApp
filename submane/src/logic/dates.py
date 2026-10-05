"""次回更新日(次回支払日)の計算。README 7章のルールをここ1か所にまとめる。

支払日の考え方:
  ・起点は入会日時。無料トライアルの終了日時があればそちらを起点にする
    (トライアル中の次回支払日 = トライアル終了日時)
  ・起点から「月額なら1か月ごと、年額なら12か月ごと」に支払日が来る
  ・月末のずれは、その月の末日に寄せる(1/31入会の月額 → 2/28、3/31、4/30)
  ・解約済みには支払日がない
"""

import calendar
from datetime import datetime

CYCLE_MONTHS = {"monthly": 1, "yearly": 12}


def parse_datetime(value) -> datetime | None:
    """ "2026-09-20T21:00" のような文字列を datetime にする。空なら None。"""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def add_months(base: datetime, months: int) -> datetime:
    """base の months か月後を返す。その日がない月は末日に寄せる。"""
    total = base.year * 12 + (base.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    last_day = calendar.monthrange(year, month)[1]
    return base.replace(year=year, month=month, day=min(base.day, last_day))


def cycle_months(sub: dict) -> int:
    """更新周期を月数で返す(月額=1、年額=12)。"""
    return CYCLE_MONTHS.get(sub.get("cycle"), 1)


def payment_anchor(sub: dict) -> datetime | None:
    """支払日の起点(最初の支払日)を返す。"""
    return parse_datetime(sub.get("trial_end_at")) or parse_datetime(sub.get("joined_at"))


def payment_in_month(sub: dict, year: int, month: int) -> datetime | None:
    """指定した年月に来る支払日を返す。なければ None。"""
    if sub.get("status") == "cancelled":
        return None
    anchor = payment_anchor(sub)
    if anchor is None:
        return None
    diff = (year - anchor.year) * 12 + (month - anchor.month)
    if diff < 0 or diff % cycle_months(sub) != 0:
        return None
    return add_months(anchor, diff)


def next_payment_at(sub: dict, now: datetime | None = None) -> datetime | None:
    """現在より後で最も近い支払日を返す。解約済みは None。"""
    if sub.get("status") == "cancelled":
        return None
    anchor = payment_anchor(sub)
    if anchor is None:
        return None
    now = now or datetime.now()
    if anchor > now:
        return anchor
    step = cycle_months(sub)
    diff = (now.year - anchor.year) * 12 + (now.month - anchor.month)
    count = diff // step
    candidate = add_months(anchor, count * step)
    while candidate <= now:
        count += 1
        candidate = add_months(anchor, count * step)
    return candidate
