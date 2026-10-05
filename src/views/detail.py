"""詳細画面モジュール。

サブスクリプションの詳細表示、入会・退会Webページ遷移、ステータス（解約・再契約）の切り替え、削除を行います。
"""

from datetime import datetime
import flet as ft
import theme
import api_client
from components.service_icon import ServiceIcon
from logic.dates import calculate_next_payment_date


def detail_view(page: ft.Page, sub_id: int, on_back: callable = None) -> ft.Control:
    """詳細画面の中身を返します。"""
    # データの取得
    item = api_client.get_subscription(sub_id)

    if not item:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("対象のサブスクリプションが見つかりません。", size=16, color=theme.INK),
                    ft.ElevatedButton("戻る", on_click=lambda _: on_back() if on_back else None)
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=24,
            expand=True
        )

    # 次回支払日の算出（APIに含まれていない場合計算）
    next_payment_at = item.get("next_payment_at") or calculate_next_payment_date(
        item.get("joined_at", ""), item.get("cycle", "monthly"), item.get("status", "active")
    )

    # 日時フォーマット整え
    next_payment_str = "なし（解約済み）"
    if next_payment_at:
        try:
            dt = datetime.fromisoformat(next_payment_at)
            next_payment_str = dt.strftime("%Y年%m月%d日")
        except Exception:
            next_payment_str = next_payment_at

    # 退会時の確認ダイアログ
    def open_url(url: str):
        if url:
            page.launch_url(url)

    def on_toggle_status(e):
        current_status = item.get("status")
        new_status = "cancelled" if current_status != "cancelled" else "active"
        api_client.update_subscription(sub_id, {"status": new_status})
        page.snack_bar = ft.SnackBar(ft.Text(f"ステータスを更新しました: {new_status}"))
        page.snack_bar.open = True
        if on_back:
            on_back()

    def on_delete_confirm(e):
        api_client.delete_subscription(sub_id)
        page.snack_bar = ft.SnackBar(ft.Text("削除しました"))
        page.snack_bar.open = True
        if on_back:
            on_back()

    def open_delete_dialog(e):
        dlg = ft.AlertDialog(
            title=ft.Text("サブスクの削除"),
            content=ft.Text(f"「{item.get('name')}」を一覧から削除してもよろしいですか？"),
            actions=[
                ft.TextButton("キャンセル", on_click=lambda _: page.close(dlg)),
                ft.TextButton("削除", on_click=lambda e: (page.close(dlg), on_delete_confirm(e))),
            ],
        )
        page.open(dlg)

    return ft.Container(
        bgcolor=theme.GROUND,
        expand=True,
        padding=ft.padding.symmetric(horizontal=24, vertical=16),
        content=ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=20,
            controls=[
                # 戻るボタン
                ft.Row(
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.ARROW_BACK,
                            icon_color=theme.INK,
                            on_click=lambda _: on_back() if on_back else None,
                        ),
                        ft.Text("詳細", size=20, weight=ft.FontWeight.BOLD, color=theme.INK),
                    ]
                ),

                # メインカード（アイコン・基本情報）
                ft.Container(
                    bgcolor=theme.SURFACE,
                    border_radius=12,
                    padding=20,
                    border=ft.border.all(1, theme.LINE),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                        controls=[
                            ServiceIcon(
                                name=item.get("name", ""),
                                icon_url=item.get("icon"),
                                status=item.get("status", "active"),
                                size=64
                            ),
                            ft.Text(item.get("name", ""), size=22, weight=ft.FontWeight.BOLD, color=theme.INK),
                            ft.Text(item.get("plan_name", "標準プラン"), size=14, color=theme.INK_SUB),
                            ft.Divider(color=theme.LINE, height=1),
                            
                            # 金額 & 支払周期
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text("利用料金", size=14, color=theme.INK_SUB),
                                    ft.Text(
                                        f"￥{item.get('amount', 0):,} / {'月' if item.get('cycle') == 'monthly' else '年'}",
                                        size=18, weight=ft.FontWeight.BOLD, color=theme.INK
                                    ),
                                ]
                            ),
                            # 次回支払日
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text("次回更新日", size=14, color=theme.INK_SUB),
                                    ft.Text(
                                        next_payment_str,
                                        size=16,
                                        weight=ft.FontWeight.BOLD,
                                        color=theme.TRIAL if item.get("status") == "trial" else theme.INK
                                    ),
                                ]
                            ),
                        ]
                    )
                ),

                # 解約時の注意事項・メモ案内（パスワード準備の案内など）
                ft.Container(
                    bgcolor=theme.SURFACE,
                    border_radius=12,
                    padding=16,
                    border=ft.border.all(1, theme.LINE),
                    content=ft.Column(
                        cross_alignment=ft.CrossAxisAlignment.START,
                        spacing=8,
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.INFO_OUTLINED, size=18, color=theme.INK_SUB),
                                    ft.Text("手続き時の確認事項", size=14, weight=ft.FontWeight.BOLD, color=theme.INK),
                                ]
                            ),
                            ft.Text("※ 解約・変更の手続きにはログイン用パスワードの入力が必要になる場合があります。", size=12, color=theme.INK_SUB),
                            ft.Text(item.get("cancel_memo") or "メモなし", size=13, color=theme.INK),
                        ]
                    )
                ),

                # アクションボタン（公式サイト・退会ページ遷移）
                ft.Column(
                    spacing=12,
                    controls=[
                        ft.ElevatedButton(
                            content=ft.Row([ft.Icon(ft.Icons.OPEN_IN_NEW), ft.Text("解約・退会ページを開く")], alignment=ft.MainAxisAlignment.CENTER),
                            style=ft.ButtonStyle(
                                bgcolor=theme.SURFACE,
                                color=theme.INK,
                                shape=ft.RoundedRectangleBorder(radius=8),
                                side=ft.BorderSide(1, theme.LINE),
                            ),
                            height=48,
                            on_click=lambda _: open_url(item.get("cancel_url")),
                        ) if item.get("cancel_url") else ft.Container(),
                        
                        ft.ElevatedButton(
                            content=ft.Row([
                                ft.Icon(ft.Icons.REFRESH if item.get("status") == "cancelled" else ft.Icons.CANCEL_OUTLINED),
                                ft.Text("解約済みにする" if item.get("status") != "cancelled" else "再契約（有効にする）")
                            ], alignment=ft.MainAxisAlignment.CENTER),
                            style=ft.ButtonStyle(
                                bgcolor=theme.ACCENT if item.get("status") == "cancelled" else theme.OFF_FILL,
                                color=theme.SURFACE if item.get("status") == "cancelled" else theme.INK,
                                shape=ft.RoundedRectangleBorder(radius=8),
                            ),
                            height=48,
                            on_click=on_toggle_status,
                        ),

                        ft.OutlinedButton(
                            content=ft.Row([ft.Icon(ft.Icons.DELETE_OUTLINE), ft.Text("削除する")], alignment=ft.MainAxisAlignment.CENTER),
                            style=ft.ButtonStyle(
                                color=ft.Colors.RED_600,
                                side=ft.BorderSide(1, ft.Colors.RED_200),
                                shape=ft.RoundedRectangleBorder(radius=8),
                            ),
                            height=48,
                            on_click=open_delete_dialog,
                        ),
                    ]
                )
            ]
        )
    )
