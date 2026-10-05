"""日付計算ロジックモジュール。

次回支払日や残り日数の計算を一元管理します。
"""

from datetime import datetime, timedelta
import calendar


def calculate_next_payment_date(joined_at_str: str, cycle: str, status: str) -> str | None:
    """次回支払日時（ISOフォーマット文字列）を返します。
    
    - 解約済みの場合は None
    - トライアル中の場合は joined_at（またはトライアル終了日）を返します
    - 月末補正（例: 1/31 -> 2/28）を行います
    """
    if status == "cancelled":
        return None

    try:
        joined_at = datetime.fromisoformat(joined_at_str)
    except (ValueError, TypeError):
        return None

    now = datetime.now()

    # トライアル中の場合は、次回支払日 = トライアル終了日時（joined_at）として扱う
    if status == "trial":
        return joined_at.isoformat()

    # 月額プランの場合
    if cycle == "monthly":
        year = now.year
        month = now.month
        
        # 今月の支払日候補を作成（月末調整含む）
        max_days_this_month = calendar.monthrange(year, month)[1]
        target_day = min(joined_at.day, max_days_this_month)
        candidate = datetime(year, month, target_day, joined_at.hour, joined_at.minute)

        # 既に今月の支払日時を過ぎている場合は翌月へ
        if candidate <= now:
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
            max_days_next_month = calendar.monthrange(year, month)[1]
            target_day = min(joined_at.day, max_days_next_month)
            candidate = datetime(year, month, target_day, joined_at.hour, joined_at.minute)

        return candidate.isoformat()

    # 年額プランの場合
    elif cycle == "yearly":
        year = now.year
        max_days = calendar.monthrange(year, joined_at.month)[1]
        target_day = min(joined_at.day, max_days)
        candidate = datetime(year, joined_at.month, target_day, joined_at.hour, joined_at.minute)

        if candidate <= now:
            year += 1
            max_days = calendar.monthrange(year, joined_at.month)[1]
            target_day = min(joined_at.day, max_days)
            candidate = datetime(year, joined_at.month, target_day, joined_at.hour, joined_at.minute)

        return candidate.isoformat()

    return None


def get_days_until(target_date_str: str | None) -> int | None:
    """指定された日付までの残り日数（今日との差）を返します。"""
    if not target_date_str:
        return None

    try:
        target_date = datetime.fromisoformat(target_date_str).date()
        today = datetime.now().date()
        return (target_date - today).days
    except (ValueError, TypeError):
        return None
