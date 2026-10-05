"""設計書v0.2のサーバ応答・送信内容と通信断を外部通信なしで検証する．"""
import asyncio
import json
from datetime import datetime, timezone
import httpx
import pytest
from api_client import ApiClient, ApiError, OfflineError
from logic.subscriptions import cancellation_patch, reactivation_patch, sort_subscriptions


def draft(**changes):
    return {"name": "手入力", "plan_name": "月額", "amount": 1000, "cycle": "monthly",
            "joined_at": "2026-10-05T12:30", "status": "active", **changes}


def test_wrapped_services_and_subscriptions_keep_server_fields():
    async def scenario():
        record = {"id": 42, "next_payment_at": "2026-11-05T12:30+09:00", "created_at": "2026-10-05T12:30+09:00"}
        def handler(request):
            if request.url.path.endswith("services"):
                assert request.url.params["q"] == "動画"
                return httpx.Response(200, json={"services": [{"id": 3, "plans": [{"id": 30}]}]})
            return httpx.Response(200, json={"subscriptions": [record], "server_time": "2026-10-05T12:30+09:00"})
        async with httpx.AsyncClient(base_url="https://test.example/api/v1/", transport=httpx.MockTransport(handler)) as session:
            api = ApiClient(use_dummy=False, base_url="https://test.example/api/v1", http_session=session)
            assert (await api.search_services("動画"))[0]["plans"][0]["id"] == 30
            assert await api.list_subscriptions() == [record]
    asyncio.run(scenario())


@pytest.mark.parametrize("standard", [True, False])
def test_registration_sends_ids_or_custom_fields_and_japanese_time(standard):
    async def scenario():
        def handler(request):
            assert request.method == "POST" and request.url.path == "/api/v1/subscriptions"
            payload = json.loads(request.content)
            assert payload["joined_at"] == "2026-10-05T12:30+09:00"
            assert payload["trial_ends_at"] == "2026-10-10T12:30+09:00"
            assert not {"status", "name", "icon", "next_payment_at"} & payload.keys()
            if standard:
                assert payload["service_id"] == 3 and payload["plan_id"] == 30
                assert "custom_name" not in payload
            else:
                assert payload["custom_name"] == "手入力"
                assert payload["custom_cancel_url"] == "https://example.com/cancel"
                assert "service_id" not in payload
            return httpx.Response(201, json={"id": 42, "status": "trial", **payload})
        async with httpx.AsyncClient(base_url="https://test.example/api/v1/", transport=httpx.MockTransport(handler)) as session:
            api = ApiClient(use_dummy=False, base_url="https://test.example/api/v1", http_session=session)
            data = draft(status="trial", trial_ends_at="2026-10-10T12:30", cancel_url="https://example.com/cancel")
            if standard:
                data.update(service_id=3, plan_id=30)
            assert (await api.create_subscription(data))["id"] == 42
    asyncio.run(scenario())


def test_cancel_and_reactivate_accept_server_dates_without_sending_computed_fields():
    async def scenario():
        seen = []
        def handler(request):
            seen.append(json.loads(request.content))
            assert request.method == "PATCH" and request.url.path == "/api/v1/subscriptions/42"
            return httpx.Response(200, json={"id": 42, "next_payment_at": "2026-11-05T12:30+09:00", **seen[-1]})
        async with httpx.AsyncClient(base_url="https://test.example/api/v1/", transport=httpx.MockTransport(handler)) as session:
            api = ApiClient(use_dummy=False, base_url="https://test.example/api/v1", http_session=session)
            await api.update_subscription(42, cancellation_patch())
            result = await api.update_subscription(42, reactivation_patch(draft(joined_at="2026-01-01T12:30+09:00", status="cancelled"), "2026-10-05T12:30"))
            assert seen == [{"status": "cancelled"}, {"status": "active", "joined_at": "2026-10-05T12:30+09:00"}]
            assert result["next_payment_at"] == "2026-11-05T12:30+09:00"
    asyncio.run(scenario())


def test_validation_error_retains_field_details():
    async def scenario():
        body = {"error": {"code": "validation_error", "message": "入力内容に誤りがあります", "details": {"amount": ["金額を確認してください"]}}}
        async with httpx.AsyncClient(base_url="https://test.example/api/v1/", transport=httpx.MockTransport(lambda request: httpx.Response(422, json=body))) as session:
            api = ApiClient(use_dummy=False, base_url="https://test.example/api/v1", http_session=session)
            with pytest.raises(ApiError) as error:
                await api.create_subscription(draft())
            assert error.value.status_code == 422
            assert error.value.code == "validation_error"
            assert error.value.details == body["error"]["details"]
    asyncio.run(scenario())


def test_offline_registration_does_not_retry_or_write_dummy_storage(tmp_path):
    async def scenario():
        calls = []
        def handler(request):
            calls.append(request)
            raise httpx.ConnectError("offline", request=request)
        file = tmp_path / "must-not-exist.json"
        async with httpx.AsyncClient(base_url="https://test.example/api/v1/", transport=httpx.MockTransport(handler)) as session:
            api = ApiClient(file, use_dummy=False, base_url="https://test.example/api/v1", http_session=session)
            with pytest.raises(OfflineError):
                await api.create_subscription(draft())
            assert len(calls) == 1 and not file.exists()
    asyncio.run(scenario())


def test_registration_order_uses_created_at_and_datetime_objects():
    records = [{"id": "later", "created_at": "2026-10-05T12:30+09:00"},
               {"id": "earlier", "created_at": datetime(2026, 10, 5, 2, tzinfo=timezone.utc)},
               {"id": "cancelled", "status": "cancelled", "created_at": "2026-01-01T00:00"}]
    assert [item["id"] for item in sort_subscriptions(records, "registered")] == ["earlier", "later", "cancelled"]


def test_deadline_order_compares_naive_japanese_time_and_utc():
    records = [{"id": "later", "next_payment_at": "2026-10-05T04:00+00:00"},
               {"id": "earlier", "next_payment_at": "2026-10-05T12:30"}]
    assert [item["id"] for item in sort_subscriptions(records, "deadline")] == ["earlier", "later"]
