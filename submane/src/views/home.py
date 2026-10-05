"""ホーム画面(担当: 玉造)。契約中サブスクのアイコン一覧。

・4列 x 3行 = 1ページ12件。横スワイプ(ft.PageView)でページを送る
・無料トライアル中は時計バッジ、解約済みはグレーアウト(components/service_icon.py)
・並び順は「更新頻度順」「登録順」。どちらでも解約済みは末尾(logic/ordering.py)
・アイコンをタップすると詳細画面へ移る
"""

import math

import flet as ft

import api_client
import navigation
import theme
from components import feedback
from components.service_icon import footprint, service_icon, status_label
from logic import ordering

COLUMNS = 4
ROWS = 3
PER_PAGE = COLUMNS * ROWS
SIDE_PADDING = 16   # 一覧の左右余白(バッジのはみ出し分があるので GUTTER より少し狭い)
NAME_HEIGHT = 20    # サービス名の行の高さ
ROW_GAP = 18        # 行と行の間


def _icon_size(page: ft.Page) -> int:
    """画面幅に合わせたアイコンの大きさを返す(基準幅390pxで72px)。"""
    width = page.width or theme.BASE_WIDTH
    cell = (min(width, 430) - SIDE_PADDING * 2) / COLUMNS
    return int(max(48, min(72, cell - 17)))


def _tile(page: ft.Page, sub: dict, size: int, color_index: int) -> ft.Control:
    """アイコン + サービス名の1マスを返す。タップで詳細画面へ。"""
    cancelled = sub.get("status") == "cancelled"
    state = status_label(sub)
    label = f"{sub['name']}({state})の詳細を開く" if state else f"{sub['name']}の詳細を開く"
    return ft.Container(
        expand=1,
        on_click=lambda e: navigation.go_detail(page, sub["id"]),
        content=ft.Semantics(
            label=label,
            button=True,
            content=ft.Column(
                spacing=6,
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    service_icon(sub, size=size, color_index=color_index),
                    ft.Container(
                        height=NAME_HEIGHT,
                        padding=ft.Padding.symmetric(horizontal=2),
                        alignment=ft.Alignment.CENTER,
                        content=theme.text(
                            sub["name"],
                            size=12,
                            color=theme.OFF_INK if cancelled else theme.INK,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ),
                ],
            ),
        ),
    )


def _row_height(size: int) -> int:
    """一覧1行分の高さを返す。"""
    return int(footprint(size)[1]) + 6 + NAME_HEIGHT


def _build_pages(page: ft.Page, subs: list[dict], size: int, color_index: dict) -> list[ft.Control]:
    """並び替え済みのサブスクを、12件ずつのページに分けて返す。"""
    pages = []
    for start in range(0, len(subs), PER_PAGE):
        chunk = subs[start:start + PER_PAGE]
        rows = []
        for row_start in range(0, len(chunk), COLUMNS):
            cells = [_tile(page, sub, size, color_index[sub["id"]]) for sub in chunk[row_start:row_start + COLUMNS]]
            cells += [ft.Container(expand=1) for _ in range(COLUMNS - len(cells))]  # 端数の行を左詰めにする
            rows.append(ft.Row(controls=cells, spacing=0, vertical_alignment=ft.CrossAxisAlignment.START))
        pages.append(
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=SIDE_PADDING),
                content=ft.Column(controls=rows, spacing=ROW_GAP),
            )
        )
    return pages


def _legend() -> ft.Control:
    """バッジとグレー表示の意味を示す凡例を返す。"""
    return ft.Row(
        spacing=12,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Row(
                spacing=5,
                controls=[
                    ft.Container(
                        width=16,
                        height=16,
                        border_radius=8,
                        bgcolor=theme.TRIAL,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.ACCESS_TIME, size=11, color=theme.ON_ACCENT),
                    ),
                    theme.text("トライアル中", size=11, color=theme.INK_SUB),
                ],
            ),
            ft.Row(
                spacing=5,
                controls=[
                    ft.Container(width=14, height=14, border_radius=4, bgcolor=theme.OFF_FILL),
                    theme.text("解約済み", size=11, color=theme.INK_SUB),
                ],
            ),
        ],
    )


def home_view(page: ft.Page) -> ft.Control:
    """ホーム画面の中身を返す。"""
    try:
        subs = api_client.list_subscriptions()
    except api_client.ApiError as err:
        return feedback.error_panel(page, str(err))

    heading = ft.Container(
        padding=ft.Padding.only(left=theme.GUTTER, right=theme.GUTTER, top=24),
        content=theme.text("契約中のサブスク", size=26, weight="bold"),
    )

    if not subs:
        return ft.Column(
            expand=True,
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                heading,
                feedback.message_panel(
                    "まだサブスクが登録されていません。\n契約中のサービスを追加すると、ここに一覧で表示されます。",
                    button_label="サブスクを追加",
                    on_click=lambda e: navigation.go(page, navigation.REGISTER),
                ),
            ],
        )

    counts = ordering.count_by_status(subs)
    size = _icon_size(page)
    # タイルの色は登録順で固定し、並び替えても同じサービスは同じ色にする
    color_index = {sub["id"]: index for index, sub in enumerate(subs)}
    page_count = math.ceil(len(subs) / PER_PAGE)
    rows_shown = min(ROWS, math.ceil(len(subs) / COLUMNS))
    state = {"order": ordering.ORDER_FREQUENCY, "current": 0}

    def sorted_pages() -> list[ft.Control]:
        return _build_pages(page, ordering.sort_subscriptions(subs, state["order"]), size, color_index)

    # ---- ページ位置(点と「1 / 2」) ----
    dots = ft.Row(spacing=0, alignment=ft.MainAxisAlignment.CENTER, visible=page_count > 1)
    page_label = theme.text("", size=12, color=theme.INK_SUB)

    def show_page(index: int) -> None:
        page.run_task(pager.go_to_page, index, 250)

    def refresh_position() -> None:
        current = state["current"]
        dots.controls = [
            ft.Container(
                width=28,
                height=theme.TAP_MIN,
                alignment=ft.Alignment.CENTER,
                tooltip=f"{index + 1}ページ目を表示",
                on_click=lambda e, index=index: show_page(index),
                content=ft.Container(
                    width=20 if index == current else 8,
                    height=8,
                    border_radius=4,
                    bgcolor=theme.ACCENT if index == current else theme.DOT,
                ),
            )
            for index in range(page_count)
        ]
        page_label.value = f"{current + 1} / {page_count}" if page_count > 1 else ""

    def on_page_change(e) -> None:
        state["current"] = int(e.control.selected_index or 0)
        refresh_position()
        page.update()

    # ---- アイコン一覧(横スワイプ) ----
    pager = ft.PageView(
        controls=sorted_pages(),
        height=rows_shown * _row_height(size) + (rows_shown - 1) * ROW_GAP + 4,
        on_change=on_page_change,
    )

    # ---- 並び替え ----
    order_label = theme.text(ordering.ORDER_LABELS[state["order"]], size=13, weight="bold")

    def change_order(order: str) -> None:
        if order == state["order"]:
            return
        state["order"] = order
        state["current"] = 0
        order_label.value = ordering.ORDER_LABELS[order]
        pager.controls = sorted_pages()
        pager.selected_index = 0
        refresh_position()
        page.update()

    sort_menu = ft.PopupMenuButton(
        tooltip="並び順を変える",
        content=ft.Container(
            height=theme.TAP_MIN,
            padding=ft.Padding.symmetric(horizontal=12),
            border_radius=12,
            bgcolor=theme.SURFACE,
            border=ft.Border.all(1, theme.LINE),
            content=ft.Row(
                spacing=6,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.SWAP_VERT, size=18, color=theme.INK),
                    order_label,
                    ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN, size=18, color=theme.INK),
                ],
            ),
        ),
        items=[
            ft.PopupMenuItem(content=theme.text(label, size=14), on_click=lambda e, order=order: change_order(order))
            for order, label in ordering.ORDER_LABELS.items()
        ],
    )

    refresh_position()

    return ft.Column(
        expand=True,
        spacing=0,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            heading,
            ft.Container(
                padding=ft.Padding.only(left=theme.GUTTER, right=theme.GUTTER, top=4),
                content=theme.text(
                    f"契約中 {counts['active']}件 / うちトライアル {counts['trial']}件 / 解約済み {counts['cancelled']}件",
                    size=13,
                    color=theme.INK_SUB,
                ),
            ),
            ft.Container(
                padding=ft.Padding.only(left=theme.GUTTER, right=theme.GUTTER, top=16, bottom=20),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    wrap=True,
                    run_spacing=8,
                    controls=[sort_menu, _legend()],
                ),
            ),
            pager,
            ft.Container(
                padding=ft.Padding.only(top=8, bottom=24),
                content=ft.Column(
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[dots, page_label],
                ),
            ),
        ],
    )
