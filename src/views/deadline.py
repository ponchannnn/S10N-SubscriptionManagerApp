"""期限画面モジュール。

支払期限が近いサブスクリプションを順に並べ、注意喚起（ハイライト・カウントダウン）を行います。
"""

from datetime import datetime
import flet as ft
import theme
import api_client
from components.service_icon import ServiceIcon
from logic.dates import calculate_next_payment_date, get_days_until


def deadline_view(page: ft.Page, on_select_item: callable = None) -> ft.Control:
    """期限画面の中身を返します。"""
    subscriptions = api_client.list_subscriptions() or []

    # 支払日が近い順にソート（解約済みは除外または末尾）
    active_items = []
    for sub in subscriptions:
        if sub.get("status") == "cancelled":
            continue

        next_date = sub.get("next_payment_at") or calculate_next_payment_date(
            sub.get("joined_at", ""), sub.get("cycle", "monthly"), sub.get("status", "active")
        )
        
        days_left = get_days_until(next_date)
        if days_left is not None:
            active_items.append({
                "data": sub,
                "next_date": next_date,
                "days_left": days_left
            })

    # 残り日数が少ない順（昇順）にソート
    active_items.sort(key=lambda x: x["days_left"])

    # カード要素の構築
    card_controls = []
    for item in active_items:
        sub = item["data"]
        days_left = item["days_left"]
        next_date_str = item["next_date"]

        # 残り日数ラベル表現
        if days_left == 0:
            badge_text = "本日更新"
            badge_bg = ft.Colors.RED_100
            badge_fg = ft.Colors.RED_800
        elif days_left < 0:
            badge_text = f"{abs(days_left)}日前"
            badge_bg = theme.LINE
            badge_fg = theme.INK_SUB
        elif days_left <= 3:
            badge_text = f"あと {days_left} 日"
            badge_bg = ft.Colors.ORANGE_100
            badge_fg = theme.TRIAL
        else:
            badge_text = f"あと {days_left} 日"
            badge_bg = theme.GROUND
            badge_fg = theme.INK_SUB

        try:
            formatted_date = datetime.fromisoformat(next_date_str).strftime("%m/%d")
        except Exception:
            formatted_date = next_date_str

        # 単一カード
        card = ft.Container(
            bgcolor=theme.SURFACE,
            border_radius=12,
            padding=16,
            border=ft.border.all(1, theme.LINE),
            on_click=lambda e, sid=sub.get("id"): on_select_item(sid) if on_select_item else None,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    # 左側：アイコンとサービス名
                    ft.Row(
                        spacing=12,
                        controls=[
                            ServiceIcon(
                                name=sub.get("name", ""),
                                icon_url=sub.get("icon"),
                                status=sub.get("status", "active"),
                                size=44
                            ),
                            ft.Column(
                                alignment=ft.MainAxisAlignment.CENTER,
                                cross_alignment=ft.CrossAxisAlignment.START,
                                spacing=2,
                                controls=[
                                    ft.Text(sub.get("name", ""), size=16, weight=ft.FontWeight.BOLD, color=theme.INK),
                                    ft.Text(f"￥{sub.get('amount', 0):,} ({formatted_date})", size=13, color=theme.INK_SUB),
                                ]
                            )
                        ]
                    ),
                    # 右側：残り日数バッジ
                    ft.Container(
                        bgcolor=badge_bg,
                        padding=ft.padding.symmetric(horizontal=10, vertical=6),
                        border_radius=16,
                        content=ft.Text(badge_text, size=12, weight=ft.FontWeight.BOLD, color=badge_fg)
                    )
                ]
            )
        )
        card_controls.append(card)

    if not card_controls:
        card_controls.append(
            ft.Container(
                padding=32,
                alignment=ft.alignment.center,
                content=ft.Text("直近で更新予定のサブスクはありません。", size=14, color=theme.INK_SUB)
            )
        )

    return ft.Container(
        bgcolor=theme.GROUND,
        expand=True,
        padding=ft.padding.symmetric(horizontal=24, vertical=16),
        content=ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=16,
            controls=[
                ft.Text("支払期日が近いサブスク", size=22, weight=ft.FontWeight.BOLD, color=theme.INK),
                ft.Text("解約の検討やチャージ確認にお役立てください。", size=13, color=theme.INK_SUB),
                ft.Column(spacing=10, controls=card_controls)
            ]
        )
    )
