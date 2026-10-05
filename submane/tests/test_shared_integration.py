"""develop共通APIと石井担当画面の接続を検証する．"""
import asyncio
import json
import flet as ft
import httpx
import api_client
import config
from components.status_actions import status_actions
from views.register import register_view
from logic.subscriptions import cancellation_patch


class PageStub:
    def update(self):
        pass


def test_registration_and_status_use_same_shared_store():
    async def scenario():
        saved = []
        page = PageStub()
        initial = len(api_client.list_subscriptions())
        view = register_view(page, on_saved=saved.append, on_back=lambda: None)
        fields = {c.label: c for c in view.controls if isinstance(c, ft.TextField)}
        fields["サービス名 *"].value = "共通APIへの登録"
        fields["料金プラン名 *"].value = "月額"
        fields["1回の支払額（円） *"].value = "1000"
        await view.controls[-1].on_click(None)
        assert len(api_client.list_subscriptions()) == initial + 1
        item = api_client.get_subscription(saved[0]["id"])
        changed = []
        actions = status_actions(page, item, api_client, changed.append)
        next(c for c in actions.controls if isinstance(c, ft.Checkbox)).value = True
        await actions.controls[-1].on_click(None)
        assert api_client.get_subscription(item["id"])["status"] == "cancelled"
        assert changed[0]["id"] == item["id"]
    asyncio.run(scenario())


def test_shared_api_uses_v02_paths_payload_and_cookie(monkeypatch):
    seen = []
    def handler(request):
        seen.append(request)
        if request.url.path == "/api/v1/session":
            return httpx.Response(200, json={"user": {"id": 1}}, headers={"set-cookie": "session_id=test; Path=/; Secure"})
        assert request.headers["cookie"] == "session_id=test"
        if request.method == "GET":
            return httpx.Response(200, json={"subscriptions": [{"id": 42, "name": "試作", "joined_at": "2026-10-05T12:30+09:00", "trial_ends_at": None, "next_payment_at": "2026-11-05T12:30+09:00"}]})
        if request.method == "POST":
            payload = json.loads(request.content)
            assert payload["service_id"] == 3 and payload["plan_id"] == 30
            assert "status" not in payload and "name" not in payload
            return httpx.Response(201, json={"id": 42, "name": "試作", **payload})
        assert request.method == "PATCH"
        assert json.loads(request.content) == {"status": "cancelled"}
        return httpx.Response(200, json={"id": 42, "status": "cancelled"})
    monkeypatch.setattr(config, "USE_DUMMY_DATA", False)
    with httpx.Client(base_url="https://test.example/api/v1/", transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(api_client, "_client", client)
        api_client.log_in("demo@example.com", "secret")
        item = api_client.list_subscriptions()[0]
        assert item["joined_at"] == "2026-10-05T12:30"
        assert item["next_payment_at"] == "2026-11-05T12:30+09:00"
        api_client.create_subscription({"name": "試作", "plan_name": "月額", "amount": 1000, "cycle": "monthly", "status": "active", "joined_at": "2026-10-05T12:30", "service_id": 3, "plan_id": 30})
        api_client.update_subscription(42, cancellation_patch())
    assert [r.url.path for r in seen] == ["/api/v1/session", "/api/v1/subscriptions", "/api/v1/subscriptions", "/api/v1/subscriptions/42"]



def test_shared_views_construct_without_flet_api_errors():
    from types import SimpleNamespace
    from views.home import home_view
    from views.detail import detail_view
    from views.deadline import deadline_view
    from views.breakdown import breakdown_view
    class Store(dict):
        def set(self, key, value):
            self[key] = value
    page = PageStub()
    page.width = 390
    page.route = "/detail/1"
    page.session = SimpleNamespace(store=Store())
    for builder in (home_view, detail_view, deadline_view, breakdown_view):
        assert isinstance(builder(page), ft.Control)


def test_detail_uses_server_payment_date_instead_of_recalculation():
    from views.detail import _next_payment_text
    value = _next_payment_text({"status": "active", "joined_at": "2026-01-01T12:00", "cycle": "monthly", "next_payment_at": "2026-11-05T12:30+09:00"})
    assert value == "2026年11月05日"



def test_deadline_handles_mixed_server_dates_and_dummy_fallback():
    from views.deadline import deadline_view
    api_client._dummy_subs[0]["next_payment_at"] = "2026-11-05T03:30+00:00"
    assert isinstance(deadline_view(PageStub()), ft.Control)
