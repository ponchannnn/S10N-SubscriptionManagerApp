"""Cookie認証を保持し，取得エラーを画面用の例外に変換する．"""
import httpx
import pytest

import api_client
import config
from api_client import ApiError


def test_cookie_session_is_shared_across_requests(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path == "/api/v1/session":
            return httpx.Response(200, json={"ok": True},
                                   headers={"set-cookie": "session=test; Path=/; HttpOnly; Secure"})
        return httpx.Response(200, json={"services": [], "subscriptions": []})

    monkeypatch.setattr(config, "USE_DUMMY_DATA", False)
    monkeypatch.setattr(api_client, "_client", httpx.Client(
        base_url="https://test.example", transport=httpx.MockTransport(handler)))

    api_client.log_in("demo@example.com", "secret")
    api_client.search_services("動画")
    api_client.list_subscriptions()

    assert seen[1].headers["cookie"] == "session=test"
    assert seen[2].headers["cookie"] == "session=test"
    assert "authorization" not in seen[2].headers


@pytest.mark.parametrize("status", [401, 403, 500])
def test_http_errors_become_api_errors(monkeypatch, status):
    monkeypatch.setattr(config, "USE_DUMMY_DATA", False)
    monkeypatch.setattr(api_client, "_client", httpx.Client(
        base_url="https://test.example",
        transport=httpx.MockTransport(lambda request: httpx.Response(status, json={"error": "details"})),
    ))
    with pytest.raises(ApiError):
        api_client.list_subscriptions()


def test_delete_account_calls_the_api_and_clears_local_state(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(204)

    monkeypatch.setattr(config, "USE_DUMMY_DATA", False)
    monkeypatch.setattr(api_client, "_client", httpx.Client(
        base_url="https://test.example", transport=httpx.MockTransport(handler)))
    api_client._logged_in = True

    api_client.delete_account()

    assert len(seen) == 1
    assert seen[0].method == "DELETE"
    assert seen[0].url.path == "/api/v1/me"
    assert api_client.is_logged_in() is False


def test_delete_account_in_dummy_mode_just_logs_out():
    api_client._logged_in = True

    api_client.delete_account()

    assert api_client.is_logged_in() is False
