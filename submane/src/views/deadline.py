"""期限画面(担当: 小湊)。支払期日が近い順にサブスクを並べ，残り日数を強調表示する。"""

from datetime import datetime

import flet as ft

import api_client
import navigation
import theme
from components.service_icon import service_icon
from logic.dates import next_payment_at


def _badge(days_left: int) -> ft.Control:
    """残り日数に応じたバッジを返す(当日は赤，3日以内は注意色)。"""
    if days_left <= 0:
        text, bg, fg = "本日更新", ft.Colors.RED_100, ft.Colors.RED_800
    elif days_left <= 3:
        text, bg, fg = f"あと {days_left} 日", ft.Colors.ORANGE_100, theme.TRIAL
    else:
        text, bg, fg = f"あと {days_left} 日", theme.GROUND, theme.INK_SUB
    return ft.Container(
        bgcolor=bg,
        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        border_radius=16,
        content=theme.text(text, size=12, weight="bold", color=fg),
    )


def _card(page: ft.Page, sub: dict, due: datetime) -> ft.Control:
    """一覧1件分のカードを返す。タップで詳細画面へ。"""
    days_left = (due.date() - datetime.now().date()).days
    return ft.Container(
        bgcolor=theme.SURFACE,
        border_radius=12,
        padding=16,
        border=ft.Border.all(1, theme.LINE),
        on_click=lambda e: navigation.go_detail(page, sub.get("id")),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    spacing=12,
                    controls=[
                        service_icon(sub, size=44),
                        ft.Column(
                            alignment=ft.MainAxisAlignment.CENTER,
                            horizontal_alignment=ft.CrossAxisAlignment.START,
                            spacing=2,
                            controls=[
                                theme.text(sub.get("name", ""), size=16, weight="bold"),
                                theme.text(f"{theme.yen(sub.get('amount', 0))}（{due.strftime('%m/%d')}）",
                                          size=13, color=theme.INK_SUB),
                            ],
                        ),
                    ],
                ),
                _badge(days_left),
            ],
        ),
    )


def deadline_view(page: ft.Page) -> ft.Control:
    """期限画面の中身を返す。"""
    items = []
    for sub in api_client.list_subscriptions() or []:
        due = next_payment_at(sub)
        if due is not None:
            items.append((sub, due))
    items.sort(key=lambda pair: pair[1])

    cards = [_card(page, sub, due) for sub, due in items]
    if not cards:
        cards = [ft.Container(
            padding=32,
            alignment=ft.Alignment.CENTER,
            content=theme.text("直近で更新予定のサブスクはありません。", size=14, color=theme.INK_SUB),
        )]

    return ft.Column(
        scroll=ft.ScrollMode.AUTO,
        spacing=16,
        controls=[
            theme.text("支払期日が近いサブスク", size=22, weight="bold"),
            theme.text("解約の検討やチャージ確認にお役立てください。", size=13, color=theme.INK_SUB),
            ft.Column(spacing=10, controls=cards),
        ],
    )
