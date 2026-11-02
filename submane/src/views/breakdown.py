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
    """サービス別の支出割合の円グラフを返す。割合はグラフに出す items の合計に対して計算する。"""
    title_style = ft.TextStyle(size=12, color=theme.ON_ACCENT, font_family=theme.FONT_BOLD)
    chart_total = sum(item["amount"] for item in items)

    def share(amount: int) -> float:
        return amount / chart_total if chart_total else 0.0

    sections = [
        fch.PieChartSection(
            value=item["amount"],
            color=colors[index],
            radius=48,
            title=f"{round(share(item['amount']) * 100)}%" if share(item["amount"]) >= 0.08 else "",
            title_style=title_style,
        )
        for index, item in enumerate(items)
    ]
    return ft.Container(
        height=220,
        content=fch.PieChart(sections=sections, sections_space=2, center_space_radius=54, expand=True),
    )


def _item_row(page: ft.Page, item: dict, color: str, mode: str, last: bool,
              hidden: bool, on_toggle) -> ft.Control:
    """金額一覧の1行を返す。チェックで円グラフへの表示を切り替え、それ以外のタップで詳細画面へ。"""
    sub = item["sub"]
    text_color = theme.INK_SUB if hidden else theme.INK
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        border=None if last else ft.Border.only(bottom=ft.BorderSide(1, theme.LINE)),
        on_click=lambda e: navigation.go_detail(page, sub["id"]),
        content=ft.Row(
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Checkbox(
                    value=not hidden,
                    fill_color=color,
                    tooltip="円グラフに表示",
                    on_change=lambda e: on_toggle(sub["id"]),
                ),
                ft.Column(
                    expand=True,
                    spacing=0,
                    controls=[
                        theme.text(sub["name"], size=14, weight="bold", color=text_color, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        theme.text(_cycle_text(sub, mode), size=11, color=theme.INK_SUB, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ],
                ),
                ft.Column(
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.END,
                    controls=[
                        theme.text(theme.yen(item["amount"]), size=14, weight="bold", color=text_color),
                        theme.text("グラフ非表示" if hidden else f"{round(item['ratio'] * 100)}%", size=11, color=theme.INK_SUB),
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
        "hidden": api_client.get_chart_hidden(),  # 円グラフから外したサブスクのID
    }
    body = ft.Column(spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    def render() -> None:
        """今の年月と計上方法で、中身を組み立て直す。"""
        year, month, mode = state["year"], state["month"], state["mode"]
        summary = payments.summarize(subs, year, month, mode)
        items = summary["items"]
        hidden = state["hidden"]
        visible = [item for item in items if str(item["sub"]["id"]) not in hidden]
        # 色はグラフに出す順で割り当て、グラフと一覧の色をそろえる
        visible_colors = [theme.tile_color(index) for index in range(len(visible))]
        color_by_id = {str(item["sub"]["id"]): color for item, color in zip(visible, visible_colors)}
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
            if visible:
                chart = _pie(visible, visible_colors)
            else:
                chart = ft.Container(
                    height=220,
                    alignment=ft.Alignment.CENTER,
                    content=theme.text("グラフに表示するサブスクを選んでください。", size=13, color=theme.INK_SUB),
                )
            controls.append(ft.Container(padding=ft.Padding.only(top=20, bottom=20), content=chart))
            # グラフに出す件数と「すべて表示」
            hidden_count = len(items) - len(visible)
            controls.append(
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    height=40,
                    controls=[
                        theme.text(
                            f"グラフに表示：{len(visible)} / {len(items)}件" if hidden_count else "チェックを外すとグラフから除けます",
                            size=12,
                            color=theme.INK_SUB,
                        ),
                        ft.TextButton("すべて表示", on_click=lambda e: show_all()) if hidden_count else ft.Container(),
                    ],
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
                            _item_row(
                                page, item,
                                color_by_id.get(str(item["sub"]["id"]), theme.LINE),
                                mode,
                                last=index == len(items) - 1,
                                hidden=str(item["sub"]["id"]) in hidden,
                                on_toggle=toggle,
                            )
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

    def toggle(sub_id) -> None:
        """1件の円グラフへの表示・非表示を切り替える。"""
        key = str(sub_id)
        state["hidden"] ^= {key}
        api_client.set_chart_hidden(state["hidden"])  # 端末に保存し、次回起動後も覚えておく
        render()
        page.update()

    def show_all() -> None:
        state["hidden"] = set()
        api_client.set_chart_hidden(state["hidden"])
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
