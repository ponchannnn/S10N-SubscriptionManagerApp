"""お知らせ画面。7日以内に更新・トライアル終了が来るサブスクを近い順に並べる。"""

import flet as ft

import api_client
import navigation
import theme
from components import feedback
from components.service_icon import service_icon
from logic.notifications import KIND_TRIAL_END, NOTICE_DAYS, upcoming_notices
from views.deadline import _badge


def _card(page: ft.Page, notice: dict) -> ft.Control:
    """お知らせ1件分のカード。タップで詳細画面へ。"""
    sub, due = notice["sub"], notice["due"]
    trial = notice["kind"] == KIND_TRIAL_END
    message = (f"{due.strftime('%m/%d')} に無料トライアルが終わります" if trial
               else f"{due.strftime('%m/%d')} に {theme.yen(int(sub.get('amount') or 0))} の更新があります")
    return ft.Container(
        bgcolor=theme.SURFACE,
        border_radius=12,
        padding=16,
        border=ft.Border.all(1, theme.LINE),
        on_click=lambda e: navigation.go_detail(page, sub.get("id")),
        content=ft.Row(
            spacing=12,
            controls=[
                service_icon(sub, size=44),
                ft.Column(
                    expand=True,
                    spacing=2,
                    controls=[
                        theme.text(notice["kind"], size=12, weight="bold",
                                   color=theme.TRIAL if trial else theme.ACCENT),
                        theme.text(sub.get("name", ""), size=16, weight="bold",
                                   max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        theme.text(message, size=13, color=theme.INK_SUB),
                    ],
                ),
                _badge(notice["days_left"]),
            ],
        ),
    )


def notifications_view(page: ft.Page) -> ft.Control:
    """お知らせ画面の中身を返す。"""
    try:
        notices = upcoming_notices(api_client.list_subscriptions() or [])
    except api_client.ApiError as error:
        return feedback.error_panel(page, str(error))

    cards = [_card(page, notice) for notice in notices]
    if not cards:
        cards = [ft.Container(
            padding=32,
            alignment=ft.Alignment.CENTER,
            content=theme.text(f"{NOTICE_DAYS}日以内のお知らせはありません。", size=14, color=theme.INK_SUB),
        )]

    return ft.Column(
        scroll=ft.ScrollMode.AUTO,
        spacing=16,
        controls=[
            theme.text(f"{NOTICE_DAYS}日以内に更新・トライアル終了があるサブスクです。解約するなら今のうちに。",
                       size=13, color=theme.INK_SUB),
            ft.Column(spacing=10, controls=cards),
        ],
    )
