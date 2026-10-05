"""ローカル保存の永続化とデータ破損時の保護を確認する．"""
import asyncio
import pytest
from api_client import ApiClient, ApiError
from logic.subscriptions import cancellation_patch, reactivation_patch


def test_save_cancel_reactivate_and_reload(tmp_path):
    async def scenario():
        client = ApiClient(tmp_path / "data.json", use_dummy=True)
        item = await client.create_subscription({"name": "手入力", "plan_name": "年間", "cycle": "yearly",
                    "amount": "1200", "joined_at": "2026-01-31T12:00", "status": "active",
                    "join_url": "https://example.com/join", "cancel_url": "https://example.com/cancel"})
        cancelled = await client.update_subscription(item["id"], cancellation_patch())
        assert cancelled["status"] == "cancelled"
        assert cancelled["join_url"] == item["join_url"]
        active = await client.update_subscription(item["id"], reactivation_patch(cancelled, "2026-10-05T12:00"))
        assert active["id"] == item["id"]
        reloaded = await ApiClient(tmp_path / "data.json", use_dummy=True).list_subscriptions()
        assert len(reloaded) == 1 and reloaded[0]["joined_at"] == "2026-10-05T12:00"
    asyncio.run(scenario())


def test_corrupt_file_is_not_overwritten(tmp_path):
    file = tmp_path / "data.json"
    file.write_text("broken", encoding="utf-8")
    with pytest.raises(ApiError):
        asyncio.run(ApiClient(file, use_dummy=True).list_subscriptions())
    assert file.read_text(encoding="utf-8") == "broken"


def test_search_normalizes_full_width_and_does_not_mutate_master(tmp_path):
    async def scenario():
        client = ApiClient(tmp_path / "data.json", use_dummy=True)
        values = await client.search_services("ＶＩＤＥＯ")
        assert len(values) == 1
        values[0]["name"] = "書き換え"
        assert (await client.search_services("video"))[0]["name"] != "書き換え"
    asyncio.run(scenario())
