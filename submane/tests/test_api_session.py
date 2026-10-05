"""Cookie認証を保持し，取得エラーを画面用の例外に変換する．"""
import asyncio
import httpx
import pytest
from api_client import ApiClient, ApiError


def test_cookie_session_is_shared_across_requests():
    async def scenario():
        seen = []
        def handler(request):
            seen.append(request)
            if request.url.path == "/api/login":
                return httpx.Response(200, json={"ok": True}, headers={"set-cookie": "session=test; Path=/; HttpOnly; Secure"})
            return httpx.Response(200, json=[])
        async with httpx.AsyncClient(base_url="https://test.example/api/", transport=httpx.MockTransport(handler)) as session:
            api = ApiClient(use_dummy=False, base_url="https://test.example/api", http_session=session)
            await api.http_session().post("login", json={"email": "demo@example.com"})
            await api.search_services("動画")
            await api.list_subscriptions()
            assert seen[1].headers["cookie"] == "session=test"
            assert seen[2].headers["cookie"] == "session=test"
            assert "authorization" not in seen[2].headers
            await api.aclose()
            assert not session.is_closed
    asyncio.run(scenario())


@pytest.mark.parametrize("status", [401, 403, 500])
def test_http_errors_become_api_errors(status):
    async def scenario():
        async with httpx.AsyncClient(base_url="https://test.example/", transport=httpx.MockTransport(
                lambda request: httpx.Response(status, json={"error": "details"}))) as session:
            api = ApiClient(use_dummy=False, base_url="https://test.example", http_session=session)
            with pytest.raises(ApiError):
                await api.list_subscriptions()
    asyncio.run(scenario())
