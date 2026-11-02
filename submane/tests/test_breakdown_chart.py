"""内訳画面の円グラフで、チェックを外したサブスクを非表示にできることを検証する．"""
import flet as ft
import flet_charts as fch

import api_client
import theme
from ui_helpers import walk
from views.breakdown import breakdown_view


class PageStub:
    def update(self):
        pass


def _pie(view):
    return next((c for c in walk(view) if isinstance(c, fch.PieChart)), None)


def _total(view):
    return next(c.value for c in walk(view) if isinstance(c, ft.Text) and c.size == 40)


def _checkboxes(view):
    return [c for c in walk(view) if isinstance(c, ft.Checkbox)]


def _show_all(view):
    return next((c for c in walk(view) if isinstance(c, ft.TextButton) and c.content == "すべて表示"), None)


def _chart_sum(view):
    return sum(section.value for section in _pie(view).sections)


def test_unchecking_removes_amount_from_chart_but_keeps_total():
    view = breakdown_view(PageStub())
    before_sum = _chart_sum(view)
    before_total = _total(view)
    largest = _pie(view).sections[0].value
    assert _show_all(view) is None

    _checkboxes(view)[0].on_change(None)  # いちばん高いサブスクを外す

    assert _chart_sum(view) == before_sum - largest
    assert _total(view) == before_total
    assert _checkboxes(view)[0].value is False
    assert len(api_client.get_chart_hidden()) == 1

    _show_all(view).on_click(None)
    assert _chart_sum(view) == before_sum
    assert api_client.get_chart_hidden() == set()


def test_every_visible_subscription_gets_its_own_colored_section():
    view = breakdown_view(PageStub())
    sections = _pie(view).sections
    assert len(sections) == len(_checkboxes(view))
    assert len({section.color for section in sections}) == min(len(sections), 12)


def test_hiding_everything_shows_message_instead_of_chart():
    view = breakdown_view(PageStub())
    for index in range(len(_checkboxes(view))):
        _checkboxes(view)[index].on_change(None)
    assert _pie(view) is None
    assert any(isinstance(c, ft.Text) and c.value == "グラフに表示するサブスクを選んでください。" for c in walk(view))


def test_hidden_ids_are_saved_and_restored():
    api_client.set_chart_hidden({1, "abc"})
    assert api_client.get_chart_hidden() == {"1", "abc"}
    api_client.set_chart_hidden(set())
    assert api_client.get_chart_hidden() == set()


def _tooltip(view):
    return next(c for c in walk(view) if isinstance(c, ft.Container) and c.bgcolor == theme.INK)


def test_touching_a_slice_shows_its_name_price_and_share():
    view = breakdown_view(PageStub())
    pie = _pie(view)
    tooltip = _tooltip(view)
    assert tooltip.visible is False

    pie.on_event(fch.PieChartEvent("event", pie, type=fch.ChartEventType.PAN_DOWN,
        section_index=0, local_x=40, local_y=60))

    title, detail = tooltip.content.controls
    assert tooltip.visible is True
    assert title.value  # サービス名が入っている
    assert theme.yen(pie.sections[0].value) in detail.value
    assert detail.value.endswith("%")


def test_releasing_the_touch_hides_the_tooltip():
    view = breakdown_view(PageStub())
    pie = _pie(view)
    tooltip = _tooltip(view)

    pie.on_event(fch.PieChartEvent("event", pie, type=fch.ChartEventType.PAN_DOWN,
        section_index=0, local_x=40, local_y=60))
    assert tooltip.visible is True

    pie.on_event(fch.PieChartEvent("event", pie, type=fch.ChartEventType.PAN_END,
        section_index=0, local_x=40, local_y=60))
    assert tooltip.visible is False
