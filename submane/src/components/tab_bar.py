"""下部タブ(ホーム / 内訳 / 期限)。"""

import flet as ft

import navigation
import theme

TABS = [
    (navigation.HOME, "ホーム", ft.Icons.GRID_VIEW_ROUNDED),
    (navigation.BREAKDOWN, "内訳", ft.Icons.PIE_CHART_OUTLINE),
    (navigation.DEADLINE, "期限", ft.Icons.EVENT_OUTLINED),
]


def _tab(page: ft.Page, route: str, label: str, icon, selected: bool) -> ft.Control:
    """タブ1つ分を返す。"""
    color = theme.ACCENT if selected else theme.INK_SUB
    return ft.Container(
        expand=True,
        height=56,
        on_click=lambda e: navigation.go(page, route),
        content=ft.Column(
            spacing=2,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=56,
                    height=30,
                    border_radius=15,
                    bgcolor=theme.ACCENT_SOFT if selected else None,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icon, size=20, color=color),
                ),
                theme.text(label, size=11, weight="bold" if selected else "regular", color=color),
            ],
        ),
    )


def tab_bar(page: ft.Page, current_route: str | None) -> ft.Control:
    """下部タブを返す(main.py が全画面に付ける)。current_route のタブを選択中にする。"""
    return ft.Container(
        bgcolor=theme.SURFACE,
        border=ft.Border.only(top=ft.BorderSide(1, theme.LINE)),
        padding=ft.Padding.only(left=theme.GUTTER, right=theme.GUTTER, top=8, bottom=8),
        content=ft.Row(
            spacing=8,
            controls=[_tab(page, route, label, icon, route == current_route) for route, label, icon in TABS],
        ),
    )
