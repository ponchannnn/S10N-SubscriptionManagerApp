"""スマホでサービス名と状態が読める，3列・12件のホーム画面．"""
import math
import flet as ft
import api_client
import navigation
import theme
from components import feedback
from components.service_icon import service_icon, status_label, status_badge
from logic import ordering

COLUMNS = 3
ROWS = 4
PER_PAGE = COLUMNS * ROWS


def _stat(label, value, color):
    return ft.Container(expand=True, bgcolor=theme.SURFACE, padding=12, border_radius=14,
        border=ft.Border.all(1, theme.LINE), content=ft.Column(spacing=3, controls=[
            theme.text(str(value), size=23, weight='bold', color=color),
            theme.text(label, size=11, color=theme.INK_SUB)]))


def _tile(page, sub, size=64):
    cancelled = sub.get('status') == 'cancelled'
    state = status_label(sub)
    return ft.Container(expand=1, padding=ft.Padding.symmetric(vertical=10, horizontal=3),
        border_radius=16, bgcolor=theme.SURFACE, border=ft.Border.all(1, theme.LINE),
        # 解約済みは画像・文字・バッジを含むカード全体を無彩色にして薄くする．
        color_filter=ft.ColorFilter(color=ft.Colors.WHITE, blend_mode=ft.BlendMode.SATURATION)
            if cancelled else None,
        opacity=0.5 if cancelled else 1.0,
        on_click=lambda e: navigation.go_detail(page, sub['id']),
        content=ft.Semantics(button=True, label=f"{sub['name']} {state} 詳細を開く",
            content=ft.Column(spacing=5, horizontal_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                service_icon(sub, size=size, ring_color=theme.SURFACE),
                ft.Container(height=38, alignment=ft.Alignment.CENTER,
                    content=theme.text(sub['name'], size=12, weight='bold', max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS, text_align=ft.TextAlign.CENTER,
                        color=theme.OFF_INK if cancelled else theme.INK)),
                theme.text('解約済み' if cancelled else ('トライアル中' if sub.get('status') == 'trial'
                           else f"{theme.yen(int(sub.get('amount') or 0))} / {'月' if sub.get('cycle') == 'monthly' else '年'}"),
                    size=10, color=theme.TRIAL if sub.get('status') == 'trial' else theme.INK_SUB,
                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ])))


def _build_pages(page, subscriptions, size):
    pages = []
    for start in range(0, len(subscriptions), PER_PAGE):
        chunk = subscriptions[start:start + PER_PAGE]
        rows = []
        for index in range(0, len(chunk), COLUMNS):
            tiles = [_tile(page, sub, size) for sub in chunk[index:index + COLUMNS]]
            tiles.extend(ft.Container(expand=1) for _ in range(COLUMNS - len(tiles)))
            rows.append(ft.Row(controls=tiles, spacing=8, vertical_alignment=ft.CrossAxisAlignment.START))
        pages.append(ft.Column(controls=rows, spacing=8))
    return pages


def _legend():
    return ft.Container(key='home-fixed-legend', padding=ft.Padding.only(top=8),
        content=ft.Column(spacing=3, horizontal_alignment=ft.CrossAxisAlignment.CENTER, controls=[
            ft.Row(spacing=16, alignment=ft.MainAxisAlignment.CENTER, controls=[
                ft.Row(spacing=4, controls=[status_badge('trial'), theme.text('トライアル中', size=11, color=theme.INK_SUB)]),
                ft.Row(spacing=4, controls=[status_badge('cancelled'), theme.text('解約済み', size=11, color=theme.INK_SUB)])]),
            theme.text('左右にスワイプして，次のページへ．', size=11, color=theme.INK_SUB)]))


def _home_layout(controls):
    return ft.Column(expand=True, spacing=0, controls=[
        ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=18, controls=controls), _legend()])


def home_view(page):
    try:
        subs = api_client.list_subscriptions()
    except api_client.ApiError as error:
        return _home_layout([feedback.error_panel(page, str(error))])
    counts = ordering.count_by_status(subs)
    state = {'order': ordering.ORDER_FREQUENCY, 'current': 0}
    size = min(72, max(52, int(((page.width or theme.BASE_WIDTH) - 48) / 3 - 30)))
    heading = ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
        ft.Column(spacing=3, expand=True, controls=[theme.text('マイサブスク', size=25, weight='bold')]),
        ft.IconButton(icon=ft.Icons.ADD_ROUNDED, bgcolor=theme.ACCENT, icon_color=theme.ON_ACCENT,
            width=46, height=46, tooltip='サブスクを追加',
            on_click=lambda e: navigation.go(page, navigation.REGISTER))])
    stats = ft.Row(spacing=8, controls=[_stat('契約中', counts['active'], theme.ACCENT),
        _stat('トライアル', counts['trial'], theme.TRIAL), _stat('解約済み', counts['cancelled'], theme.OFF_INK)])
    if not subs:
        return _home_layout([heading, stats,
            feedback.message_panel('最初のサブスクを登録しましょう．\n契約内容をまとめて確認できます．',
                button_label='サブスクを追加', on_click=lambda e: navigation.go(page, navigation.REGISTER))])
    count = math.ceil(len(subs) / PER_PAGE)
    pager = ft.PageView(controls=_build_pages(page, ordering.sort_subscriptions(subs), size),
                       height=min(ROWS, math.ceil(len(subs) / COLUMNS)) * (size + 100))
    position = theme.text('', size=12, color=theme.INK_SUB)
    dots = ft.Row(spacing=5, alignment=ft.MainAxisAlignment.CENTER)
    previous = ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, tooltip='前のページ', width=44, height=44)
    following = ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, tooltip='次のページ', width=44, height=44)

    def refresh_position():
        index = state['current']
        position.value = f'{index + 1} / {count}'
        dots.controls = [ft.Container(width=18 if i == index else 6, height=6, border_radius=3,
            bgcolor=theme.ACCENT if i == index else theme.DOT) for i in range(count)]
        previous.disabled = index == 0
        following.disabled = index == count - 1

    def go_to(index):
        page.run_task(pager.go_to_page, index, 250)

    previous.on_click = lambda e: go_to(max(0, state['current'] - 1))
    following.on_click = lambda e: go_to(min(count - 1, state['current'] + 1))

    def page_changed(event):
        state['current'] = int(event.control.selected_index or 0)
        refresh_position()
        page.update()
    pager.on_change = page_changed

    def order_changed(event):
        state['order'] = event.control.value
        state['current'] = 0
        pager.controls = _build_pages(page, ordering.sort_subscriptions(subs, state['order']), size)
        pager.selected_index = 0
        refresh_position()
        page.update()

    sort = ft.Dropdown(label='並び順', value=state['order'], expand=True,
        options=[ft.DropdownOption(key=key, text=value) for key, value in ordering.ORDER_LABELS.items()],
        on_select=order_changed)
    refresh_position()
    return _home_layout([heading, stats,
        ft.Row(controls=[sort, ft.Container(padding=8, content=theme.text(f'{len(subs)}件', size=13, color=theme.INK_SUB))]),
        pager, ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, visible=count > 1,
            controls=[previous, ft.Column(spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[dots, position]), following])])
