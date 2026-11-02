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
    def pop_dialog(self):
        return self.dialogs.pop()
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
    dialog = page.dialogs[-1]
    clock = next(c for c in walk(dialog) if isinstance(c, ft.CupertinoDatePicker))
    assert clock.date_picker_mode == ft.CupertinoDatePickerMode.TIME and clock.use_24h_format
    assert clock.minute_interval == 1
    assert field.value == before
    clock.value = datetime(2026, 11, 6, 16, 45)
    clock.on_change(SimpleNamespace(control=clock))
    assert field.value == before
    next(c for c in dialog.actions if c.content == '確定').on_click(None)
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
    async def scenario():
        monkeypatch.setattr(app.local_db, 'init_db', lambda: None)
        for route in navigation.TAB_ROUTES:
            monkeypatch.setitem(app.SCREENS, route, app.Screen(lambda p, route=route: ft.Text(route)))
        page = PageStub()
        app.main(page)
        handler, args = page.tasks.pop(0)
        await handler(*args)
        original = page.views[0]
        for route in [navigation.BREAKDOWN, navigation.DEADLINE, navigation.HOME]:
            page.route = route
            await page.on_route_change(SimpleNamespace(route=route))
            assert page.views[0] is original and original.route == route
            assert navigation.last_tab(page) == route
        page.route = navigation.REGISTER
        await page.on_route_change(SimpleNamespace(route=page.route))
        assert len(page.views) == 2
        page.route = navigation.HOME
        await page.on_route_change(SimpleNamespace(route=page.route))
        assert len(page.views) == 1 and page.views[0] is not original
    asyncio.run(scenario())


def test_slow_screen_does_not_replace_a_newer_route(monkeypatch):
    import threading
    async def scenario():
        monkeypatch.setattr(app.local_db, 'init_db', lambda: None)
        started, release = threading.Event(), threading.Event()
        def slow_screen(page):
            started.set()
            release.wait(timeout=3)
            return ft.Text('old slow screen')
        for route in navigation.TAB_ROUTES:
            monkeypatch.setitem(app.SCREENS, route, app.Screen(lambda p, route=route: ft.Text(route)))
        monkeypatch.setitem(app.SCREENS, navigation.BREAKDOWN, app.Screen(slow_screen))
        page = PageStub()
        app.main(page)
        handler, args = page.tasks.pop(0)
        await handler(*args)
        page.route = navigation.BREAKDOWN
        pending = asyncio.create_task(page.on_route_change(SimpleNamespace(route=page.route)))
        assert await asyncio.to_thread(started.wait, 1)
        page.route = navigation.DEADLINE
        await page.on_route_change(SimpleNamespace(route=page.route))
        release.set()
        await pending
        stack = next(c for c in walk(page.views[0]) if isinstance(c, ft.Stack))
        assert stack.controls[-1].content.value == navigation.DEADLINE
    asyncio.run(scenario())


def test_swiping_then_cancelling_keeps_the_original_datetime():
    page = PageStub()
    field = ft.TextField(label='入会日時', value='2026-11-02T09:30')
    attach_datetime_picker(page, field)
    field.on_click(None)
    calendar = page.dialogs[-1]
    calendar.value = datetime(2026, 11, 8)
    calendar.on_change(SimpleNamespace(control=calendar))
    dialog = page.dialogs[-1]
    wheel = next(c for c in walk(dialog) if isinstance(c, ft.CupertinoDatePicker))
    wheel.value = datetime(2026, 11, 8, 21, 15)
    wheel.on_change(SimpleNamespace(control=wheel))
    next(c for c in dialog.actions if c.content == 'キャンセル').on_click(None)
    assert field.value == '2026-11-02T09:30'
    field.on_click(None)
    assert page.dialogs[-1].value == datetime(2026, 11, 2, 9, 30)


@pytest.mark.parametrize('hour, minute', [(0, 0), (23, 59)])
def test_wheel_accepts_start_and_end_of_day(hour, minute):
    page = PageStub()
    field = ft.TextField(label='入会日時', value='2026-11-02T09:30')
    attach_datetime_picker(page, field)
    field.on_click(None)
    calendar = page.dialogs[-1]
    calendar.value = datetime(2026, 11, 2)
    calendar.on_change(SimpleNamespace(control=calendar))
    dialog = page.dialogs[-1]
    wheel = next(c for c in walk(dialog) if isinstance(c, ft.CupertinoDatePicker))
    wheel.value = datetime(2026, 11, 2, hour, minute)
    wheel.on_change(SimpleNamespace(control=wheel))
    next(c for c in dialog.actions if c.content == '確定').on_click(None)
    assert field.value == f'2026-11-02T{hour:02}:{minute:02}'


def test_trial_time_wheel_starts_no_earlier_than_joining_on_the_same_day():
    page = PageStub()
    field = ft.TextField(label='終了日時', value='2026-11-02T10:00')
    attach_datetime_picker(page, field, minimum=lambda: '2026-11-01T18:20')
    field.on_click(None)
    calendar = page.dialogs[-1]
    calendar.value = datetime(2026, 11, 1)
    calendar.on_change(SimpleNamespace(control=calendar))
    wheel = next(c for c in walk(page.dialogs[-1]) if isinstance(c, ft.CupertinoDatePicker))
    assert wheel.first_date == datetime(2026, 11, 1, 18, 20)
    assert wheel.value == datetime(2026, 11, 1, 18, 20)
