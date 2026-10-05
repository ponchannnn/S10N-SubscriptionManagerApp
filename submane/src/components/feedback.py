"""データが0件のとき、通信に失敗したときなどの案内表示。"""

import flet as ft

import navigation
import theme


def primary_button(label: str, on_click, icon=None) -> ft.Control:
    """主要な操作のボタン(緑の塗り)。"""
    return ft.FilledButton(
        content=label,
        icon=icon,
        height=theme.TAP_MIN,
        bgcolor=theme.ACCENT,
        color=theme.ON_ACCENT,
        icon_color=theme.ON_ACCENT,
        style=ft.ButtonStyle(text_style=ft.TextStyle(font_family=theme.FONT_BOLD, size=14)),
        on_click=on_click,
    )


def message_panel(message: str, icon=None, button_label: str | None = None, on_click=None, color: str = theme.INK_SUB) -> ft.Control:
    """中央寄せの案内文(+ ボタン)を返す。"""
    controls = []
    if icon:
        controls.append(ft.Icon(icon, size=40, color=color))
    controls.append(theme.text(message, size=14, color=theme.INK_SUB, text_align=ft.TextAlign.CENTER))
    if button_label and on_click:
        controls.append(primary_button(button_label, on_click))
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=theme.GUTTER, vertical=48),
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            controls=controls,
            spacing=20,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def error_panel(page: ft.Page, message: str) -> ft.Control:
    """通信エラーなどの案内と「もう一度読み込む」ボタンを返す。"""
    return message_panel(
        message,
        icon=ft.Icons.ERROR_OUTLINE,
        button_label="もう一度読み込む",
        on_click=lambda e: navigation.reload(page),
        color=theme.DANGER,
    )
