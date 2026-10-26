"""サーバ設計書v0.2の登録・状態変更リクエストへの変換．"""
from logic.subscriptions import parse_time


def registration_payload(data):
    """画面表示用の項目とAPIが計算する項目を送信しない．"""
    result = {key: data[key] for key in ("plan_name", "amount", "cycle")}
    result["joined_at"] = parse_time(data["joined_at"]).isoformat(timespec="minutes")
    if data.get("service_id"):
        result["service_id"] = int(data["service_id"])
        if data.get("plan_id"):
            result["plan_id"] = int(data["plan_id"])
    else:
        result.update({"custom_name": data["name"],
                       "custom_join_url": data.get("join_url") or None,
                       "custom_cancel_url": data.get("cancel_url") or None,
                       "custom_cancel_memo": data.get("cancel_memo") or None})
    if data.get("status") == "trial":
        result["trial_ends_at"] = parse_time(data["trial_ends_at"]).isoformat(timespec="minutes")
    return result


def update_payload(data):
    """状態変更時もnext_payment_atなどの読み取り専用値を除外する．"""
    allowed = {"service_id", "plan_id", "custom_name", "custom_join_url", "custom_cancel_url",
               "custom_cancel_memo", "plan_name", "amount", "cycle", "joined_at",
               "trial_ends_at", "memo", "status"}
    result = {key: value for key, value in data.items() if key in allowed}
    for key in ("joined_at", "trial_ends_at"):
        if result.get(key):
            result[key] = parse_time(result[key]).isoformat(timespec="minutes")
    return result
