"""UIから独立した登録・解約・再契約の規則．"""
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
from urllib.parse import urlsplit
import unicodedata

STATUS_LABELS = {"active": "契約中", "trial": "無料トライアル中", "cancelled": "解約済み"}
CYCLE_LABELS = {"monthly": "月額", "yearly": "年額"}
SORT_LABELS = {"frequency": "更新頻度順", "registered": "登録順", "deadline": "期限が近い順"}


class ValidationError(ValueError):
    """入力欄ごとのエラーを保持する．"""

    def __init__(self, errors):
        self.errors = errors
        super().__init__("入力内容を確認してください．")


def normalize_keyword(value):
    """全角英数字と大文字・小文字の違いを吸収する．"""
    return unicodedata.normalize("NFKC", value).casefold().strip()


def valid_url(value):
    """HTTP(S)の絶対URLのみ受け付ける．空欄は任意項目として許可する．"""
    if not value:
        return True
    try:
        parsed = urlsplit(value)
        return (parsed.scheme in {"http", "https"} and bool(parsed.hostname)
                and not parsed.username and not parsed.password
                and not any(char.isspace() for char in value)
                and parsed.port != 0)
    except ValueError:
        return False


def parse_time(value):
    """画面とAPIで共通の分単位の日時形式を読み取る．"""
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    return parsed.replace(tzinfo=JST) if parsed.tzinfo is None else parsed


def validate_subscription(data):
    """登録内容を検証し，APIへ渡す辞書を返す．"""
    result = {key: str(data.get(key, "") or "").strip() for key in (
        "name", "plan_name", "cycle", "joined_at", "join_url", "cancel_url",
        "cancel_memo", "status", "trial_ends_at", "icon", "service_id", "plan_id",
    )}
    if not result["trial_ends_at"]:
        result["trial_ends_at"] = str(data.get("trial_end_at") or "").strip()
    errors = {}
    for key, maximum in (("name", 100), ("plan_name", 100), ("cancel_memo", 1000)):
        if key != "cancel_memo" and not result[key]:
            errors[key] = "入力してください．"
        elif len(result[key]) > maximum:
            errors[key] = f"{maximum}文字以内で入力してください．"
    amount = unicodedata.normalize("NFKC", str(data.get("amount", ""))).strip()
    if not amount or not amount.isascii() or not amount.isdecimal():
        errors["amount"] = "0以上の整数を円単位で入力してください．"
    elif int(amount) > 999999999:
        errors["amount"] = "金額が大きすぎます．"
    else:
        result["amount"] = int(amount)
    if result["cycle"] not in CYCLE_LABELS:
        errors["cycle"] = "月額または年額を選択してください．"
    if result["status"] not in STATUS_LABELS:
        errors["status"] = "契約状態を選択してください．"
    for key in ("join_url", "cancel_url", "icon"):
        if len(result[key]) > 2048 or not valid_url(result[key]):
            errors[key] = "http://またはhttps://で始まるURLを入力してください．"
    joined = None
    try:
        joined = parse_time(result["joined_at"])
    except ValueError:
        errors["joined_at"] = "実在する日時を YYYY-MM-DDTHH:MM で入力してください．"
    if result["status"] == "trial":
        try:
            ending = parse_time(result["trial_ends_at"])
            if joined is not None and ending < joined:
                errors["trial_ends_at"] = "入会日時以降の日時を入力してください．"
        except ValueError:
            errors["trial_ends_at"] = "トライアル終了日時を YYYY-MM-DDTHH:MM で入力してください．"
    else:
        result["trial_ends_at"] = ""
    if errors:
        raise ValidationError(errors)
    return result


def sort_subscriptions(items, order="frequency"):
    """解約済みを末尾に集め，元データを変更せず安定した順序で返す．"""
    if order not in SORT_LABELS:
        raise ValueError("不明な並び順です．")
    def key(pair):
        index, item = pair
        cancelled = item.get("status") == "cancelled"
        value = item.get("created_at") or item.get("registered_at")
        try:
            registered = (parse_time(value).timestamp() if value else float("inf"), index)
        except (ValueError, TypeError, OSError):
            registered = (float("inf"), index)
        if order == "frequency":
            secondary = ({"weekly": 0, "monthly": 1, "yearly": 2}.get(item.get("cycle"), 9), registered)
        elif order == "deadline":
            value = item.get("next_payment_at") or item.get("trial_ends_at")
            try:
                time = parse_time(value).timestamp() if value else float("inf")
            except (ValueError, TypeError, OSError):
                time = float("inf")
            secondary = (time, registered)
        else:
            secondary = registered
        return (cancelled, secondary)
    return [item for _, item in sorted(enumerate(items), key=key)]


def cancellation_patch():
    """解約済みとして記録する更新内容を返す．公式手続きは利用者が行う．"""
    return {"status": "cancelled"}


def reactivation_patch(subscription, joined_at):
    """再契約の入会日時を検証し，サーバが再計算するための入会日時だけを送る．"""
    data = validate_subscription({**subscription, "status": "active", "joined_at": joined_at})
    return {"status": "active", "joined_at": data["joined_at"]}
