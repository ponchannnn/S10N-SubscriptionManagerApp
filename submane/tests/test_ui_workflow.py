"""Fletコントロールの生成と，画面イベントから保存までの流れを確認する．"""
import asyncio
import flet as ft
from api_client import ApiClient
from components.service_icon import service_icon
from components.status_actions import status_actions
from views.register import register_view
from views.preview import preview_list, preview_status


class PageStub:
    """画面イベントの検証に必要な更新・遷移を記録する．"""

    def update(self):
        """描画通信は行わない．"""

    def navigate(self, route):
        """検証中の遷移先を記録する．"""
        self.route = route


def test_registration_search_plan_and_save(tmp_path):
    async def scenario():
        page = PageStub()
        client = ApiClient(tmp_path / "records.json", use_dummy=True)
        saved = []
        view = register_view(page, client, on_saved=saved.append)
        fields = {control.label: control for control in view.controls if isinstance(control, (ft.TextField, ft.Dropdown))}
        search_button = next(control for control in view.controls if isinstance(control, ft.Button) and control.content == "定番サービスを表示・検索")
        await search_button.on_click(None)
        results = next(control for control in view.controls if isinstance(control, ft.Column))
        results.controls[0].on_click(None)
        assert fields["サービス名 *"].value == "動画サービス（デモ）"
        assert fields["1回の支払額（円） *"].value == "1000"
        fields["定番サービスのプラン"].value = "1"
        fields["定番サービスのプラン"].on_select(None)
        assert fields["更新周期 *"].value == "yearly"
        save = next(control for control in view.controls if isinstance(control, ft.Button) and control.content == "この内容で登録する")
        fields["1回の支払額（円） *"].value = "-1"
        await save.on_click(None)
        assert fields["1回の支払額（円） *"].error and not saved
        fields["1回の支払額（円） *"].value = "10000"
        await save.on_click(None)
        assert len(saved) == 1 and saved[0]["amount"] == 10000
        assert save.disabled and not fields["サービス名 *"].disabled
        await save.on_click(None)
        assert len(saved) == 1
    asyncio.run(scenario())


def test_status_requires_confirmation_and_preserves_id(tmp_path):
    async def scenario():
        page = PageStub()
        client = ApiClient(tmp_path / "records.json", use_dummy=True)
        item = await client.create_subscription({"name": "試作", "plan_name": "月額", "amount": "1000",
                    "cycle": "monthly", "status": "active", "joined_at": "2026-01-01T12:00"})
        changed = []
        view = status_actions(page, item, client, changed.append)
        save = view.controls[-1]
        await save.on_click(None)
        assert not changed
        check = next(control for control in view.controls if isinstance(control, ft.Checkbox))
        check.value = True
        await save.on_click(None)
        assert changed[0]["status"] == "cancelled"
        view = status_actions(page, changed[0], client, changed.append)
        joined = next(control for control in view.controls if isinstance(control, ft.TextField))
        joined.value = "invalid"
        next(control for control in view.controls if isinstance(control, ft.Checkbox)).value = True
        await view.controls[-1].on_click(None)
        assert joined.error and len(changed) == 1
        joined.value = "2026-10-05T12:00"
        await view.controls[-1].on_click(None)
        assert changed[-1]["status"] == "active" and changed[-1]["id"] == item["id"]
    asyncio.run(scenario())


def test_preview_and_icons_construct_with_pinned_flet(tmp_path):
    page = PageStub()
    item = {"id": "demo", "name": "試作", "plan_name": "月額", "amount": 1000,
            "cycle": "monthly", "status": "active", "joined_at": "2026-01-01T12:00"}
    assert isinstance(service_icon(item), ft.Container)
    assert isinstance(service_icon({**item, "status": "trial"}), ft.Stack)
    assert isinstance(service_icon({**item, "status": "cancelled", "icon": "https://example.com/icon.png"}), ft.Container)
    assert preview_list(page, [item], "frequency", lambda e: None, lambda: None, lambda i: None)
    assert preview_status(page, item, ApiClient(tmp_path / "records.json"), lambda: None, lambda i: None)


def test_api_field_error_is_shown_and_input_is_preserved():
    from api_client import ApiError
    class FailingApi:
        async def create_subscription(self, data):
            raise ApiError("入力内容に誤りがあります", status_code=422,
                           details={"custom_name": ["名称を確認してください"]})
    async def scenario():
        view = register_view(PageStub(), FailingApi())
        fields = {control.label: control for control in view.controls if isinstance(control, ft.TextField)}
        fields["サービス名 *"].value = "試作"
        fields["料金プラン名 *"].value = "月額"
        fields["1回の支払額（円） *"].value = "1000"
        save = view.controls[-1]
        await save.on_click(None)
        assert fields["サービス名 *"].error == "名称を確認してください"
        assert fields["サービス名 *"].value == "試作" and not save.disabled
    asyncio.run(scenario())


def test_delayed_search_does_not_replace_manual_entry():
    class DelayedApi:
        def __init__(self):
            self.started = asyncio.Event()
            self.finish = asyncio.Event()
        async def search_services(self, keyword):
            self.started.set()
            await self.finish.wait()
            return [{"id": 3, "name": "古い結果"}]
    async def scenario():
        api = DelayedApi()
        view = register_view(PageStub(), api)
        search = next(c for c in view.controls if isinstance(c, ft.Button) and c.content == "定番サービスを表示・検索")
        pending = asyncio.create_task(search.on_click(None))
        await api.started.wait()
        next(c for c in view.controls if isinstance(c, ft.TextButton) and c.content == "定番にないサービスを手入力する").on_click(None)
        api.finish.set()
        await pending
        results = next(c for c in view.controls if isinstance(c, ft.Column))
        assert results.controls == []
    asyncio.run(scenario())


def test_preview_accepts_null_trial_end_and_datetime_joined(tmp_path):
    from datetime import datetime
    item = {"id": 42, "name": "試作", "plan_name": "月額", "amount": 1000,
            "cycle": "monthly", "status": "active", "joined_at": datetime(2026, 10, 5, 12),
            "trial_ends_at": None, "cancel_url": None}
    assert preview_status(PageStub(), item, ApiClient(tmp_path / "records.json"), lambda: None, lambda i: None)



def test_icon_color_stays_with_subscription_when_order_changes():
    item = {"id": 42, "name": "試作", "status": "active"}
    other = {"id": 50, "name": "別契約", "status": "active"}
    initial = {value["id"]: service_icon(value).bgcolor for value in [item, other]}
    reordered = {value["id"]: service_icon(value).bgcolor for value in [other, item]}
    assert initial == reordered
