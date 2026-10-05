"""ヘッダー。タブ画面ではアプリ名、それ以外の画面では戻るボタンと画面名を出す。"""

import flet as ft

import navigation
import theme


def app_header(page: ft.Page, title: str | None = None, show_back: bool = False, show_actions: bool = True) -> ft.Control:
    """ヘッダーを返す(main.py が全画面に付ける)。

    title        : 画面名。None ならアプリ名「サブマネ」を出す
    show_back    : 戻るボタンを出すか
    show_actions : 右側の「追加」とアカウントボタンを出すか
    """
    left = []
    if show_back:
        left.append(
            ft.IconButton(
                icon=ft.Icons.ARROW_BACK,
                icon_color=theme.INK,
                tooltip="戻る",
                width=theme.TAP_MIN,
                height=theme.TAP_MIN,
                on_click=lambda e: navigation.go_back(page),
            )
        )
    if title:
        left.append(theme.text(title, size=18, weight="bold"))
    else:
        left.append(theme.text("サブマネ", size=22, weight="black"))

    right = []
    if show_actions:
        right = [
            ft.FilledButton(
                content="追加",
                icon=ft.Icons.ADD,
                height=theme.TAP_MIN,
                bgcolor=theme.ACCENT,
                color=theme.ON_ACCENT,
                icon_color=theme.ON_ACCENT,
                style=ft.ButtonStyle(
                    text_style=ft.TextStyle(font_family=theme.FONT_BOLD, size=14),
                    padding=ft.Padding.only(left=12, right=16),
                ),
                on_click=lambda e: navigation.go(page, navigation.REGISTER),
            ),
            ft.Container(
                width=theme.TAP_MIN,
                height=theme.TAP_MIN,
                border_radius=theme.TAP_MIN / 2,
                bgcolor=theme.SURFACE,
                border=ft.Border.all(1, theme.LINE),
                alignment=ft.Alignment.CENTER,
                tooltip="アカウント",
                content=ft.Icon(ft.Icons.PERSON_OUTLINE, size=22, color=theme.INK),
                on_click=lambda e: navigation.go(page, navigation.ACCOUNT),
            ),
        ]

    return ft.Container(
        padding=ft.Padding.only(left=8 if show_back else theme.GUTTER, right=theme.GUTTER, top=12),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(controls=left, spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row(controls=right, spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ],
        ),
    )
