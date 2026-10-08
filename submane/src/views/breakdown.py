"""内訳画面(担当: 玉造)。月ごとの支払い見込み総額、円グラフ、サービス別の金額一覧。

・金額の計算は logic/payments.py だけで行う(この画面では計算しない)
・年額プランを「更新月に全額計上」するか「月割り」にするかを画面上で切り替えられる
・円グラフは flet-charts の PieChart
"""

from datetime import datetime

import flet as ft
import flet_charts as fch

import api_client
import navigation
import theme
from components import feedback
from logic import payments

MAX_SECTIONS = 6          # 円グラフで個別に出す件数。残りは「その他」にまとめる
OTHERS_COLOR = theme.OFF_INK
_MODE_LABELS = {
    payments.MODE_BILLING: "年額は更新月に計上",
    payments.MODE_AVERAGE: "年額を月割り",
}


def _diff_text(diff: int) -> str:
    """前月差分の文言を返す。"""
    if diff > 0:
        return f"先月より {theme.yen(diff)} 多い"
    if diff < 0:
        return f"先月より {theme.yen(-diff)} 少ない"
    return "先月と同じ"


def _cycle_text(sub: dict, mode: str) -> str:
    """一覧の補足(プラン名と計上のしかた)を返す。"""
    if sub.get("cycle") == "yearly":
        cycle = "年額を月割り" if mode == payments.MODE_AVERAGE else "年額(今月が更新月)"
    else:
        cycle = "月額"
    if sub.get("status") == "trial":
        cycle += " / トライアル終了後"
    plan = sub.get("plan_name")
    return f"{plan} / {cycle}" if plan and plan not in ("月額プラン", "年額プラン") else cycle


def _pie(items: list[dict], colors: list[str]) -> ft.Control:
    """サービス別の支出割合の円グラフを返す。"""
    title_style = ft.TextStyle(size=12, color=theme.ON_ACCENT, font_family=theme.FONT_BOLD)
    shown = items[:MAX_SECTIONS]
    sections = [
        fch.PieChartSection(
            value=item["amount"],
            color=colors[index],
            radius=48,
            title=f"{round(item['ratio'] * 100)}%" if item["ratio"] >= 0.08 else "",
            title_style=title_style,
        )
        for index, item in enumerate(shown)
    ]
    rest = items[MAX_SECTIONS:]
    if rest:
        ratio = sum(item["ratio"] for item in rest)
        sections.append(
            fch.PieChartSection(
                value=sum(item["amount"] for item in rest),
                color=OTHERS_COLOR,
                radius=48,
                title=f"{round(ratio * 100)}%" if ratio >= 0.08 else "",
                title_style=title_style,
            )
        )
    return ft.Container(
        height=220,
        content=fch.PieChart(sections=sections, sections_space=2, center_space_radius=54, expand=True),
    )


def _item_row(page: ft.Page, item: dict, color: str, mode: str, last: bool) -> ft.Control:
    """金額一覧の1行を返す。タップで詳細画面へ。"""
    sub = item["sub"]
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        border=None if last else ft.Border.only(bottom=ft.BorderSide(1, theme.LINE)),
        on_click=lambda e: navigation.go_detail(page, sub["id"]),
        content=ft.Row(
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(width=12, height=12, border_radius=3, bgcolor=color),
                ft.Column(
                    expand=True,
                    spacing=0,
                    controls=[
                        theme.text(sub["name"], size=14, weight="bold", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        theme.text(_cycle_text(sub, mode), size=11, color=theme.INK_SUB, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ],
                ),
                ft.Column(
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.END,
                    controls=[
                        theme.text(theme.yen(item["amount"]), size=14, weight="bold"),
                        theme.text(f"{round(item['ratio'] * 100)}%", size=11, color=theme.INK_SUB),
                    ],
                ),
            ],
        ),
    )


def breakdown_view(page: ft.Page) -> ft.Control:
    """内訳画面の中身を返す。"""
    try:
        subs = api_client.list_subscriptions()
    except api_client.ApiError as err:
        return feedback.error_panel(page, str(err))

    now = datetime.now()
    state = {
        "year": now.year,
        "month": now.month,
        "mode": api_client.get_yearly_mode(),
    }
    body = ft.Column(spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    def render() -> None:
        """今の年月と計上方法で、中身を組み立て直す。"""
        year, month, mode = state["year"], state["month"], state["mode"]
        summary = payments.summarize(subs, year, month, mode)
        items = summary["items"]
        colors = [theme.tile_color(index) if index < MAX_SECTIONS else OTHERS_COLOR for index in range(len(items))]
        is_this_month = (year, month) == (now.year, now.month)

        controls = [
            # 月の切り替え
            ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
                controls=[
                    ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, icon_color=theme.INK, tooltip="前の月", on_click=lambda e: move_month(-1)),
                    ft.Container(
                        width=150,
                        alignment=ft.Alignment.CENTER,
                        content=theme.text(f"{year}年{month}月" + ("(今月)" if is_this_month else ""), size=16, weight="bold"),
                    ),
                    ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, icon_color=theme.INK, tooltip="次の月", on_click=lambda e: move_month(1)),
                ],
            ),
            # 総額と前月差分
            ft.Container(
                padding=ft.Padding.only(top=4, bottom=16),
                content=ft.Column(
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        theme.text(theme.yen(summary["total"]), size=40, weight="black"),
                        theme.text(_diff_text(summary["diff"]), size=13, color=theme.INK_SUB),
                    ],
                ),
            ),
            # 年額プランの計上方法
            ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.SegmentedButton(
                        selected=[mode],
                        show_selected_icon=False,
                        segments=[
                            ft.Segment(value=value, label=theme.text(label, size=12))
                            for value, label in _MODE_LABELS.items()
                        ],
                        on_change=change_mode,
                    )
                ],
            ),
        ]

        if not items:
            controls.append(feedback.message_panel("この月に支払い予定のサブスクはありません。"))
        else:
            controls.append(ft.Container(padding=ft.Padding.only(top=20, bottom=20), content=_pie(items, colors)))
            if len(items) > MAX_SECTIONS:
                controls.append(
                    ft.Container(
                        padding=ft.Padding.only(bottom=8),
                        content=theme.text(
                            f"円グラフは上位{MAX_SECTIONS}件を表示し、残りは「その他」(灰色)にまとめています。",
                            size=11,
                            color=theme.INK_SUB,
                        ),
                    )
                )
            controls.append(
                ft.Container(
                    bgcolor=theme.SURFACE,
                    border=ft.Border.all(1, theme.LINE),
                    border_radius=16,
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    content=ft.Column(
                        spacing=0,
                        controls=[
                            _item_row(page, item, colors[index], mode, last=index == len(items) - 1)
                            for index, item in enumerate(items)
                        ],
                    ),
                )
            )
        body.controls = controls

    def move_month(step: int) -> None:
        mover = payments.next_month if step > 0 else payments.previous_month
        state["year"], state["month"] = mover(state["year"], state["month"])
        render()
        page.update()

    def change_mode(e) -> None:
        selected = e.control.selected
        if not selected:
            return
        state["mode"] = selected[0]
        api_client.set_yearly_mode(state["mode"])  # 端末に保存し、次回起動後も覚えておく
        render()
        page.update()

    render()

    return ft.Column(
        expand=True,
        spacing=0,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            ft.Container(
                padding=ft.Padding.only(left=theme.GUTTER, right=theme.GUTTER, top=24, bottom=8),
                content=theme.text("支払い見込み", size=26, weight="bold"),
            ),
            ft.Container(
                padding=ft.Padding.only(left=theme.GUTTER, right=theme.GUTTER, bottom=32),
                content=body,
            ),
        ],
    )
