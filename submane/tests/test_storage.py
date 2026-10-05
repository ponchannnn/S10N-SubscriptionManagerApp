"""ダミーデータに対する保存・解約・再契約の整合性と，検索結果の独立性を確認する．"""
import api_client
from logic.subscriptions import cancellation_patch, reactivation_patch


def test_save_cancel_reactivate_and_reload():
    item = api_client.create_subscription({
        "name": "手入力", "plan_name": "年間", "cycle": "yearly",
        "amount": "1200", "joined_at": "2026-01-31T12:00", "status": "active",
        "join_url": "https://example.com/join", "cancel_url": "https://example.com/cancel",
    })
    cancelled = api_client.update_subscription(item["id"], cancellation_patch())
    assert cancelled["status"] == "cancelled"
    assert cancelled["join_url"] == item["join_url"]
    active = api_client.update_subscription(item["id"], reactivation_patch(cancelled, "2026-10-05T12:00"))
    assert active["id"] == item["id"]
    reloaded = api_client.list_subscriptions()
    match = next(sub for sub in reloaded if sub["id"] == item["id"])
    assert match["joined_at"] == "2026-10-05T12:00"


def test_search_is_case_insensitive_and_does_not_mutate_master():
    values = api_client.search_services("NETFLIX")
    assert len(values) == 1
    values[0]["name"] = "書き換え"
    assert api_client.search_services("netflix")[0]["name"] != "書き換え"
