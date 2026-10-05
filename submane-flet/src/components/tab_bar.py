"""ホーム・内訳・期限の共通タブ．"""

import flet as ft
import theme


def tab_bar(page: ft.Page) -> ft.Control:
    """現在の画面に合わせた下部タブを返す．"""
    context = page.data
    controls = []
    for route, label, icon in (
        ("/home", "ホーム", ft.Icons.GRID_VIEW_ROUNDED),
        ("/breakdown", "内訳", ft.Icons.PIE_CHART_OUTLINE),
        ("/deadline", "期限", ft.Icons.CALENDAR_MONTH_OUTLINED),
    ):
        selected = context.route == route

        async def navigate(_, target=route):
            """選択したタブへ移動する．"""
            await context.navigate(target)

        controls.append(ft.TextButton(
            content=ft.Column([
                ft.Icon(icon, size=22, color=theme.ACCENT if selected else theme.INK_SUB),
                ft.Text(label, size=14, color=theme.ACCENT if selected else theme.INK_SUB),
            ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER),
            on_click=navigate, expand=True, height=64,
            style=ft.ButtonStyle(
                bgcolor=theme.ACCENT_SOFT if selected else theme.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=14), padding=8,
            ),
        ))
    return ft.Container(
        content=ft.Row(controls, spacing=8), bgcolor=theme.SURFACE,
        border=ft.Border(top=ft.BorderSide(1, theme.LINE)),
        padding=ft.Padding.symmetric(horizontal=theme.GUTTER, vertical=8),
    )

