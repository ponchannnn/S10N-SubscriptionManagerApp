"""アプリ内のお知らせ。更新日・トライアル終了日が近いサブスクを拾う。"""

from datetime import datetime

from logic.dates import next_payment_at

NOTICE_DAYS = 7  # 何日前からお知らせするか
KIND_RENEWAL = "更新"
KIND_TRIAL_END = "トライアル終了"


def upcoming_notices(subs: list[dict], now: datetime | None = None, days: int = NOTICE_DAYS) -> list[dict]:
    """残り0〜days日のものを、日付の近い順に返す。解約済みは対象外。

    各要素は {"sub", "due", "days_left", "kind"}。
    """
    now = now or datetime.now()
    notices = []
    for sub in subs:
        due = next_payment_at(sub, now)
        if due is None:
            continue
        days_left = (due.date() - now.date()).days
        if 0 <= days_left <= days:
            kind = KIND_TRIAL_END if sub.get("status") == "trial" else KIND_RENEWAL
            notices.append({"sub": sub, "due": due, "days_left": days_left, "kind": kind})
    notices.sort(key=lambda notice: notice["due"])
    return notices
