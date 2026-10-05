"""担当機能を単独で確認する一覧と状態変更画面．チームのhome/detailとは別．"""
import flet as ft
import theme
from components.service_icon import service_icon
from components.sort_selector import sort_selector
from components.status_actions import status_actions
from logic.subscriptions import CYCLE_LABELS, STATUS_LABELS, sort_subscriptions


def preview_list(page, items, order, on_order, on_add, on_detail, notice=""):
    """登録結果・グレーアウト・並び順の動作確認用一覧を返す．"""
    active = sum(item["status"] != "cancelled" for item in items)
    trial = sum(item["status"] == "trial" for item in items)
    rows = []
    for item in sort_subscriptions(items, order):
        cancelled = item["status"] == "cancelled"
        rows.append(ft.Container(
            bgcolor=theme.SURFACE, border_radius=16, padding=14,
            on_click=lambda e, sub_id=item["id"]: on_detail(sub_id),
            content=ft.Row(spacing=14, controls=[
                service_icon(item),
                ft.Column(expand=True, spacing=4, controls=[
                    ft.Text(item["name"], weight=ft.FontWeight.BOLD,
                            color=theme.OFF_INK if cancelled else theme.INK),
                    ft.Text(f"{CYCLE_LABELS.get(item['cycle'], item['cycle'])} · {item['amount']:,}円", color=theme.INK_SUB),
                    ft.Text(STATUS_LABELS[item["status"]], size=12,
                            color=theme.TRIAL if item["status"] == "trial" else theme.INK_SUB),
                ]), ft.Icon(ft.Icons.CHEVRON_RIGHT, color=theme.INK_SUB),
            ])))
    return ft.Column(spacing=16, controls=[
        ft.Text("石井担当の動作確認", size=26, weight=ft.FontWeight.BOLD),
        ft.Text("登録・契約状態・アイコン表示・並び替えを確認できます．", color=theme.INK_SUB),
        ft.Text(notice, color=theme.ACCENT, visible=bool(notice)),
        ft.Button("サブスクを追加", icon=ft.Icons.ADD, height=48, bgcolor=theme.ACCENT,
                  color=theme.SURFACE, on_click=lambda e: on_add()),
        ft.Text(f"契約中 {active}件 / うちトライアル {trial}件 / 解約済み {len(items)-active}件"),
        sort_selector(on_order, value=order),
        ft.Text("期限順はAPIの次回支払日時またはトライアル終了日時を使用します．日時未取得の契約は後ろに表示します．",
                color=theme.INK_SUB, size=12, visible=order == "deadline"),
        *rows,
        ft.Text("まだ登録がありません．「サブスクを追加」から登録してください．", visible=not bool(items), color=theme.INK_SUB),
    ])


def preview_status(page, item, api, on_back, on_changed):
    """詳細担当への組み込み前に状態変更部品を確認する．"""
    return ft.Column(spacing=16, controls=[
        ft.TextButton("一覧に戻る", on_click=lambda e: on_back()),
        service_icon(item, size=72),
        ft.Text(item["name"], size=26, weight=ft.FontWeight.BOLD),
        ft.Text(STATUS_LABELS[item["status"]], color=theme.INK_SUB),
        ft.Text(f"{item['plan_name']} / {CYCLE_LABELS[item['cycle']]} / {item['amount']:,}円"),
        ft.Text("入会日時：" + str(item.get("joined_at") or "未取得")),
        ft.Text("トライアル終了：" + str(item.get("trial_ends_at") or "未取得"), visible=item["status"] == "trial"),
        ft.Text("退会に必要な情報", size=16, weight=ft.FontWeight.BOLD),
        ft.Text(item.get("cancel_memo") or "未登録", color=theme.INK_SUB),
        ft.Divider(color=theme.LINE), status_actions(page, item, api, on_changed),
    ])
