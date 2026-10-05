"""Fletコントロールの生成と，画面イベントから保存までの流れを確認する．"""
import flet as ft

import api_client
from components.status_actions import status_actions
from views.register import register_view


class PageStub:
    """画面イベントの検証に必要な更新を記録する．"""

    def update(self):
        """描画通信は行わない．"""


def test_registration_search_plan_and_save():
    page = PageStub()
    saved = []
    view = register_view(page, on_saved=saved.append)
    fields = {control.label: control for control in view.controls if isinstance(control, (ft.TextField, ft.Dropdown))}
    search_button = next(control for control in view.controls if isinstance(control, ft.Button) and control.content == "定番サービスを表示・検索")
    fields["定番サービスを名称で検索"].value = "動画サービス"
    search_button.on_click(None)
    results = next(control for control in view.controls if isinstance(control, ft.Column))
    results.controls[0].on_click(None)
    assert fields["サービス名 *"].value == "動画サービス（デモ）"
    assert fields["1回の支払額（円） *"].value == "1000"
    fields["定番サービスのプラン"].value = "1"
    fields["定番サービスのプラン"].on_select(None)
    assert fields["更新周期 *"].value == "yearly"
    save = next(control for control in view.controls if isinstance(control, ft.Button) and control.content == "この内容で登録する")
    fields["1回の支払額（円） *"].value = "-1"
    save.on_click(None)
    assert fields["1回の支払額（円） *"].error and not saved
    fields["1回の支払額（円） *"].value = "10000"
    save.on_click(None)
    assert len(saved) == 1 and saved[0]["amount"] == 10000
    assert not save.disabled and not fields["サービス名 *"].disabled


def test_status_requires_confirmation_and_preserves_id():
    page = PageStub()
    item = api_client.create_subscription({"name": "試作", "plan_name": "月額", "amount": "1000",
                "cycle": "monthly", "status": "active", "joined_at": "2026-01-01T12:00"})
    changed = []
    view = status_actions(page, item, api_client, changed.append)
    save = view.controls[-1]
    save.on_click(None)
    assert not changed
    check = next(control for control in view.controls if isinstance(control, ft.Checkbox))
    check.value = True
    save.on_click(None)
    assert changed[0]["status"] == "cancelled"
    view = status_actions(page, changed[0], api_client, changed.append)
    joined = next(control for control in view.controls if isinstance(control, ft.TextField))
    joined.value = "invalid"
    next(control for control in view.controls if isinstance(control, ft.Checkbox)).value = True
    view.controls[-1].on_click(None)
    assert joined.error and len(changed) == 1
    joined.value = "2026-10-05T12:00"
    view.controls[-1].on_click(None)
    assert changed[-1]["status"] == "active" and changed[-1]["id"] == item["id"]
