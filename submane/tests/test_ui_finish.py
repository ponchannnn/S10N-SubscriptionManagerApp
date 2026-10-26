"""日時の確定・キャンセルと，タブ遷移中の操作を確認する．"""
import asyncio
from datetime import datetime, time
from types import SimpleNamespace

import flet as ft
import pytest

import api_client
import navigation
import main as app
from components.datetime_input import attach_datetime_picker
from components.tab_slider import TabSlider
from views.home import home_view
from views.deadline import deadline_view
from views.register import register_view
from ui_helpers import walk


class Store(dict):
    def set(self, key, value):
        self[key] = value


class PageStub:
    width = 390
    window = None
    route = '/'
    def __init__(self):
        self.dialogs = []
        self.tasks = []
        self.views = []
        self.session = SimpleNamespace(store=Store())
    def update(self):
        pass
    def show_dialog(self, dialog):
        self.dialogs.append(dialog)
    def run_task(self, handler, *args):
        self.tasks.append((handler, args))


def test_legend_is_outside_scroll_and_uses_same_status_icons():
    view = home_view(PageStub())
    body, legend = view.controls
    assert body.expand and body.scroll == ft.ScrollMode.AUTO
    assert legend.key == 'home-fixed-legend' and legend not in list(walk(body))
    icons = [c.icon for c in walk(legend) if isinstance(c, ft.Icon)]
    assert icons == [ft.Icons.ACCESS_TIME, ft.Icons.CHECK]
    texts = [c.value for c in walk(view) if isinstance(c, ft.Text)]
    assert not any('ひと目で確認' in text or '✓' in text or '時計：' in text for text in texts)
    assert not any('解約の検討やチャージ' in c.value for c in walk(deadline_view(PageStub())) if isinstance(c, ft.Text))


def test_empty_home_also_keeps_legend_at_bottom(monkeypatch):
    monkeypatch.setattr(api_client, '_dummy_subs', [])
    assert home_view(PageStub()).controls[-1].key == 'home-fixed-legend'


@pytest.mark.parametrize('label', ['入会日時 *', 'トライアル終了日時 *'])
def test_registration_date_and_time_are_committed_together(label):
    page = PageStub()
    view = register_view(page)
    field = next(c for c in walk(view) if isinstance(c, ft.TextField) and c.label == label)
    assert field.read_only and field.suffix_icon.width >= 44
    before = field.value
    field.on_click(None)
    date_picker = page.dialogs[-1]
    assert isinstance(date_picker, ft.DatePicker)
    assert date_picker.locale.language_code == 'ja'
    # 日付だけ確定した段階や，時刻選択をキャンセルした段階では入力値を変えない．
    date_picker.value = datetime(2026, 11, 6)
    date_picker.on_change(SimpleNamespace(control=date_picker))
    clock = page.dialogs[-1]
    assert isinstance(clock, ft.TimePicker) and clock.hour_format == ft.TimePickerHourFormat.H24
    assert field.value == before
    clock.value = time(16, 45)
    clock.on_change(SimpleNamespace(control=clock))
    assert field.value == '2026-11-06T16:45'


def test_trial_calendar_cannot_choose_day_before_join_and_ignores_disabled_field():
    page = PageStub()
    field = ft.TextField(label='終了日時', value='')
    attach_datetime_picker(page, field, minimum=lambda: '2026-11-01T18:20')
    field.on_click(None)
    picker = page.dialogs[-1]
    assert picker.first_date == datetime(2026, 11, 1).date()
    assert picker.value >= datetime(2026, 11, 1, 18, 20)
    field.disabled = True
    field.on_click(None)
    assert len(page.dialogs) == 1


def test_tab_slides_in_both_directions_and_discards_old_tasks():
    async def scenario():
        page = PageStub()
        slider = TabSlider(page, navigation.HOME, ft.Text('home'))
        slider.show(navigation.BREAKDOWN, ft.Text('breakdown'))
        assert slider.root.controls[-1].offset.x == 1
        slider.show(navigation.HOME, ft.Text('latest home'))
        assert slider.root.controls[-1].offset.x == -1
        # 前の遷移が後から終了しても，最新の画面を消さない．
        await asyncio.gather(*(handler(*args) for handler, args in page.tasks))
        assert len(slider.root.controls) == 1
        assert slider.root.controls[0].content.value == 'latest home'
        assert slider.root.controls[0].offset.x == 0
    asyncio.run(scenario())


def test_route_changes_reuse_tab_view_and_return_from_registration(monkeypatch):
    monkeypatch.setattr(app.local_db, 'init_db', lambda: None)
    for route in navigation.TAB_ROUTES:
        monkeypatch.setitem(app.SCREENS, route, app.Screen(lambda p, route=route: ft.Text(route)))
    page = PageStub()
    app.main(page)
    original = page.views[0]
    for route in [navigation.BREAKDOWN, navigation.DEADLINE, navigation.HOME]:
        page.route = route
        page.on_route_change(SimpleNamespace(route=route))
        assert page.views[0] is original and original.route == route
        assert navigation.last_tab(page) == route
    page.route = navigation.REGISTER
    page.on_route_change(SimpleNamespace(route=page.route))
    assert len(page.views) == 2
    page.route = navigation.HOME
    page.on_route_change(SimpleNamespace(route=page.route))
    assert len(page.views) == 1 and page.views[0] is not original
