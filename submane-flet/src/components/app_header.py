"""main.pyが全画面に付ける共通ヘッダー．"""

import flet as ft
import theme


def app_header(page: ft.Page) -> ft.Control:
    """アプリ名，追加，アカウントボタンを返す．"""
    context = page.data

    async def add(_):
        """登録画面へ移動する．"""
        await context.navigate("/register")

    async def account(_):
        """アカウント画面へ移動する．"""
        await context.navigate("/account")

    return ft.Container(
        padding=ft.Padding.only(left=theme.GUTTER, right=theme.GUTTER, top=12, bottom=8),
        content=ft.Row([
            ft.Text("サブマネ", size=22, weight=ft.FontWeight.W_900, color=theme.INK),
            ft.Row([
                theme.primary_button("追加", add, icon=ft.Icons.ADD),
                ft.IconButton(
                    ft.Icons.PERSON_OUTLINE, on_click=account,
                    tooltip="アカウント", icon_color=theme.INK,
                    width=theme.TAP_SIZE, height=theme.TAP_SIZE,
                ),
            ], spacing=4),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
    )

