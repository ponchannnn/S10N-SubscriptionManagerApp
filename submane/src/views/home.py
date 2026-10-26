"""スマホでサービス名と状態が読める，3列・12件のホーム画面．"""
import math
import flet as ft
import api_client
import navigation
import theme
from components import feedback
from components.service_icon import service_icon, status_label
from logic import notifications, ordering

COLUMNS = 3
ROWS = 4
PER_PAGE = COLUMNS * ROWS


STATUS_LABELS = {'active': '契約中', 'trial': 'トライアル', 'cancelled': '解約済み'}
_NOTICE_SHOWN_KEY = 'home.notice_shown'


def _stat(label, value, color, selected=False, on_click=None):
    """件数カード．押すとその状態で絞り込む(選択中は枠と背景で示す)．"""
    return ft.Container(expand=True, padding=12, border_radius=14, on_click=on_click,
        bgcolor=theme.ACCENT_SOFT if selected else theme.SURFACE,
        border=ft.Border.all(2 if selected else 1, theme.ACCENT if selected else theme.LINE),
        content=ft.Semantics(button=True, selected=selected, label=f'{label} {value}件で絞り込む',
            content=ft.Column(spacing=3, controls=[
                theme.text(str(value), size=23, weight='bold', color=color),
                theme.text(label, size=11, color=theme.INK_SUB)])))


def _show_notice_once(page, subs):
    """そのセッションで最初にホームを開いたときだけ，近いお知らせの件数を出す．"""
    store = getattr(getattr(page, 'session', None), 'store', None)
    show_dialog = getattr(page, 'show_dialog', None)
    if store is None or show_dialog is None or store.get(_NOTICE_SHOWN_KEY):
        return
    store.set(_NOTICE_SHOWN_KEY, True)
    count = len(notifications.upcoming_notices(subs))
    if count:
        show_dialog(ft.SnackBar(ft.Text(
            f'{notifications.NOTICE_DAYS}日以内に更新・トライアル終了が{count}件あります．右上のベルから確認できます．')))


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


def home_view(page):
    try:
        subs = api_client.list_subscriptions()
    except api_client.ApiError as error:
        return feedback.error_panel(page, str(error))
    counts = ordering.count_by_status(subs)
    state = {'order': ordering.ORDER_FREQUENCY, 'current': 0, 'filter': None, 'pages': 0}
    _show_notice_once(page, subs)
    size = min(72, max(52, int(((page.width or theme.BASE_WIDTH) - 48) / 3 - 30)))
    heading = ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
        ft.Column(spacing=3, expand=True, controls=[theme.text('マイサブスク', size=25, weight='bold'),
            theme.text('契約と更新を，ひと目で確認．', size=12, color=theme.INK_SUB)]),
        ft.IconButton(icon=ft.Icons.ADD_ROUNDED, bgcolor=theme.ACCENT, icon_color=theme.ON_ACCENT,
            width=46, height=46, tooltip='サブスクを追加',
            on_click=lambda e: navigation.go(page, navigation.REGISTER))])
    stat_colors = {'active': theme.ACCENT, 'trial': theme.TRIAL, 'cancelled': theme.OFF_INK}
    stats = ft.Row(spacing=8)
    if not subs:
        stats.controls = [_stat(STATUS_LABELS[key], counts[key], color) for key, color in stat_colors.items()]
        return ft.Column(scroll=ft.ScrollMode.AUTO, spacing=18, controls=[heading, stats,
            feedback.message_panel('最初のサブスクを登録しましょう．\n契約内容をまとめて確認できます．',
                button_label='サブスクを追加', on_click=lambda e: navigation.go(page, navigation.REGISTER))])
    pager = ft.PageView()
    empty = ft.Container(visible=False, padding=24, alignment=ft.Alignment.CENTER,
        content=theme.text('該当するサブスクはありません．', size=14, color=theme.INK_SUB))
    total = theme.text('', size=13, color=theme.INK_SUB)
    clear_filter = ft.TextButton(icon=ft.Icons.CLOSE, on_click=lambda e: set_filter(None))
    filter_row = ft.Row(alignment=ft.MainAxisAlignment.END, visible=False, controls=[clear_filter])
    position = theme.text('', size=12, color=theme.INK_SUB)
    dots = ft.Row(spacing=5, alignment=ft.MainAxisAlignment.CENTER)
    previous = ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, tooltip='前のページ', width=44, height=44)
    following = ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, tooltip='次のページ', width=44, height=44)
    navigator = ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[previous, ft.Column(spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[dots, position]), following])

    def refresh_position():
        index, count = state['current'], state['pages']
        position.value = f'{index + 1} / {count}'
        dots.controls = [ft.Container(width=18 if i == index else 6, height=6, border_radius=3,
            bgcolor=theme.ACCENT if i == index else theme.DOT) for i in range(count)]
        previous.disabled = index == 0
        following.disabled = index >= count - 1
        navigator.visible = count > 1

    def rebuild():
        """絞り込み・並び順に合わせて，件数カードと一覧を作り直す．"""
        shown = ordering.sort_subscriptions(ordering.filter_by_status(subs, state['filter']), state['order'])
        stats.controls = [_stat(STATUS_LABELS[key], counts[key], color, selected=state['filter'] == key,
            on_click=lambda e, key=key: set_filter(None if state['filter'] == key else key))
            for key, color in stat_colors.items()]
        state['pages'] = math.ceil(len(shown) / PER_PAGE)
        state['current'] = 0
        pager.controls = _build_pages(page, shown, size)
        pager.selected_index = 0
        pager.height = max(1, min(ROWS, math.ceil(len(shown) / COLUMNS))) * (size + 100)
        pager.visible = bool(shown)
        empty.visible = not shown
        total.value = f'{len(shown)}件'
        filter_row.visible = state['filter'] is not None
        clear_filter.content = f"絞り込み中：{STATUS_LABELS.get(state['filter'], '')}"
        refresh_position()

    def set_filter(status):
        state['filter'] = status
        rebuild()
        page.update()

    def go_to(index):
        page.run_task(pager.go_to_page, index, 250)

    previous.on_click = lambda e: go_to(max(0, state['current'] - 1))
    following.on_click = lambda e: go_to(min(state['pages'] - 1, state['current'] + 1))

    def page_changed(event):
        state['current'] = int(event.control.selected_index or 0)
        refresh_position()
        page.update()
    pager.on_change = page_changed

    def order_changed(event):
        state['order'] = event.control.value
        rebuild()
        page.update()

    sort = ft.Dropdown(label='並び順', value=state['order'], expand=True,
        options=[ft.DropdownOption(key=key, text=value) for key, value in ordering.ORDER_LABELS.items()],
        on_select=order_changed)
    rebuild()
    return ft.Column(spacing=18, scroll=ft.ScrollMode.AUTO, controls=[heading, stats,
        ft.Row(controls=[sort, ft.Container(padding=8, content=total)]),
        filter_row, pager, empty, navigator,
        theme.text('時計：トライアル中　✓：解約済み\n左右にスワイプして，次のページへ．',
            size=11, color=theme.INK_SUB, text_align=ft.TextAlign.CENTER)])
