"""詳細画面(担当: 小湊)。

登録済みサブスク1件の詳細表示、入会・退会ページへの遷移、解約・再契約、削除を行う。
解約・再契約の確認フローは components.status_actions に委ねる(登録画面とは独立して作られた部品)。
"""

import flet as ft

import api_client
import navigation
import theme
from api_client import ApiError
from components import feedback
from components.service_icon import service_icon
from components.status_actions import status_actions
from logic.dates import next_payment_at


def _next_payment_text(item: dict) -> str:
    """次回更新日の表示文言を返す(解約済みはなし)。"""
    dt = next_payment_at(item)
    return dt.strftime("%Y年%m月%d日") if dt else "なし（解約済み）"


def detail_view(page: ft.Page) -> ft.Control:
    """詳細画面の中身を返す。"""
    sub_id = navigation.get_sub_id(page)
    try:
        item = api_client.get_subscription(sub_id)
    except ApiError as error:
        return feedback.message_panel(str(error), icon=ft.Icons.ERROR_OUTLINE)

    def open_delete_dialog(event):
        def confirm_delete(event):
            api_client.delete_subscription(sub_id)
            page.close(dialog)
            page.open(ft.SnackBar(ft.Text("削除しました．")))
            navigation.go_back(page)

        dialog = ft.AlertDialog(
            title=ft.Text("サブスクの削除"),
            content=ft.Text(f"「{item.get('name')}」を一覧から削除してもよろしいですか．"),
            actions=[
                ft.TextButton("キャンセル", on_click=lambda e: page.close(dialog)),
                ft.TextButton("削除", on_click=confirm_delete),
            ],
        )
        page.open(dialog)

    def status_changed(updated: dict):
        page.open(ft.SnackBar(ft.Text("契約状態を更新しました．")))
        navigation.reload(page)

    return ft.Column(
        scroll=ft.ScrollMode.AUTO,
        spacing=20,
        controls=[
            ft.Container(
                bgcolor=theme.SURFACE,
                border_radius=12,
                padding=20,
                border=ft.Border.all(1, theme.LINE),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                    controls=[
                        service_icon(item, size=64),
                        theme.text(item.get("name", ""), size=22, weight="bold"),
                        theme.text(item.get("plan_name", ""), size=14, color=theme.INK_SUB),
                        ft.Divider(color=theme.LINE, height=1),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                theme.text("利用料金", size=14, color=theme.INK_SUB),
                                theme.text(
                                    f"{theme.yen(item.get('amount', 0))} / "
                                    + ("月" if item.get("cycle") == "monthly" else "年"),
                                    size=18, weight="bold",
                                ),
                            ],
                        ),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                theme.text("次回更新日", size=14, color=theme.INK_SUB),
                                theme.text(
                                    _next_payment_text(item), size=16, weight="bold",
                                    color=theme.TRIAL if item.get("status") == "trial" else theme.INK,
                                ),
                            ],
                        ),
                    ],
                ),
            ),
            ft.Container(
                bgcolor=theme.SURFACE,
                border_radius=12,
                padding=16,
                border=ft.Border.all(1, theme.LINE),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.START,
                    spacing=8,
                    controls=[
                        ft.Row(controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINED, size=18, color=theme.INK_SUB),
                            theme.text("手続き時の確認事項", size=14, weight="bold"),
                        ]),
                        theme.text(item.get("cancel_memo") or "メモはありません．", size=13, color=theme.INK_SUB),
                    ],
                ),
            ),
            status_actions(page, item, api_client, status_changed),
            ft.OutlinedButton(
                content=ft.Row([ft.Icon(ft.Icons.DELETE_OUTLINE), ft.Text("削除する")],
                    alignment=ft.MainAxisAlignment.CENTER),
                style=ft.ButtonStyle(color=theme.DANGER),
                height=48,
                on_click=open_delete_dialog,
            ),
        ],
    )
