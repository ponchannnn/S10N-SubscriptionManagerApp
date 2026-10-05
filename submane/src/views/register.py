"""サブスク登録画面(担当: 石井)。定番サービスの検索と手入力の両方に対応する。"""
from datetime import datetime

import flet as ft

import api_client
import navigation
import theme
from api_client import ApiError
from logic.subscriptions import CYCLE_LABELS, STATUS_LABELS, ValidationError, validate_subscription


def register_view(page: ft.Page, on_saved=None, on_back=None) -> ft.Control:
    """pageのみでも生成でき，一覧側から保存・戻る時の挙動を注入できる．"""

    def default_saved(item):
        page.open(ft.SnackBar(ft.Text(item["name"] + "を保存しました．")))
        navigation.go_back(page)

    on_back = on_back or (lambda: navigation.go_back(page))
    on_saved = on_saved or default_saved

    message = ft.Text("", color=theme.ERROR)
    results = ft.Column(spacing=8)
    plans = ft.Dropdown(label="定番サービスのプラン", visible=False)
    selected = {"service": None, "busy": False}
    fields = {
        "name": ft.TextField(label="サービス名 *", max_length=100),
        "plan_name": ft.TextField(label="料金プラン名 *", max_length=100),
        "cycle": ft.Dropdown(label="更新周期 *", value="monthly", options=[
            ft.DropdownOption(key=key, text=value) for key, value in CYCLE_LABELS.items()]),
        "amount": ft.TextField(label="1回の支払額（円） *", keyboard_type=ft.KeyboardType.NUMBER,
                               helper="無料トライアル中も，有料移行後の金額を入力してください．"),
        "joined_at": ft.TextField(label="入会日時 *", value=datetime.now().strftime("%Y-%m-%dT%H:%M"),
                                  helper="日本時間・分単位の例：2026-10-05T12:30"),
        "status": ft.Dropdown(label="契約状態 *", value="active", options=[
            ft.DropdownOption(key=key, text=value) for key, value in STATUS_LABELS.items()]),
        "trial_end_at": ft.TextField(label="トライアル終了日時 *", visible=False,
                                     hint_text="2026-11-05T12:30"),
        "join_url": ft.TextField(label="入会URL（任意）", hint_text="https://…"),
        "cancel_url": ft.TextField(label="退会URL（任意）", hint_text="https://…"),
        "cancel_memo": ft.TextField(label="退会に必要な情報（任意）", multiline=True,
                                    min_lines=2, max_lines=4, max_length=1000,
                                    helper="例：メールアドレスとパスワードの準備が必要．パスワード自体は入力しないでください．"),
    }

    def status_changed(event):
        """無料トライアルを選択したときだけ終了日時を表示する．"""
        fields["trial_end_at"].visible = fields["status"].value == "trial"
        page.update()

    fields["status"].on_select = status_changed

    def apply_plan(event=None):
        """選択したプランを自動入力し，その後の手修正を許可する．"""
        service = selected["service"]
        if service and plans.value is not None:
            plan = service["plans"][int(plans.value)]
            for key, source in (("plan_name", "name"), ("cycle", "cycle"), ("amount", "amount")):
                fields[key].value = str(plan[source])
        page.update()

    plans.on_select = apply_plan

    def choose_service(service):
        """名称，URL，メモとプラン候補を取り込む．"""
        if selected["busy"]:
            return
        selected["service"] = service
        for key in ("name", "join_url", "cancel_url", "cancel_memo"):
            fields[key].value = service.get(key, "")
        plans.options = [ft.DropdownOption(key=str(index), text=plan["name"])
                         for index, plan in enumerate(service.get("plans", []))]
        plans.visible = bool(plans.options)
        plans.value = "0" if plans.options else None
        apply_plan()
        results.controls = [ft.Text("選択済み：" + service["name"], color=theme.ACCENT)]
        page.update()

    def search_services(event=None):
        """定番サービスを名称で検索し，候補をボタンで一覧表示する．"""
        try:
            services = api_client.search_services(search.value or "")
            results.controls = [ft.Button(service["name"], height=44,
                               on_click=lambda e, service=service: choose_service(service)) for service in services]
            if not services:
                results.controls = [ft.Text("該当するサービスがありません．下の欄へ手入力できます．", color=theme.INK_SUB)]
        except ApiError as error:
            results.controls = [ft.Text(str(error), color=theme.ERROR),
                                ft.Button("検索を再試行", on_click=search_services)]
        page.update()

    search = ft.TextField(label="定番サービスを名称で検索", prefix_icon=ft.Icons.SEARCH,
                          on_change=search_services, on_submit=search_services)

    def clear_service(event):
        """定番サービスとの関連を解除し，手入力用の空欄に戻す．"""
        selected["service"] = None
        for key in ("name", "plan_name", "amount", "join_url", "cancel_url", "cancel_memo"):
            fields[key].value = ""
        plans.visible = False
        results.controls = []
        page.update()

    def save(event):
        """入力を検証し，二重クリックによる重複登録を防ぐ．"""
        if selected["busy"]:
            return
        for control in fields.values():
            if isinstance(control, ft.Dropdown):
                control.error_text = None
            else:
                control.error = None
        message.value = ""
        message.color = theme.ERROR
        service = selected["service"] or {}
        data = {key: control.value for key, control in fields.items()}
        data.update(icon=service.get("icon", ""), service_id=service.get("id", ""))
        try:
            data = validate_subscription(data)
        except ValidationError as error:
            for key, value in error.errors.items():
                if key in fields:
                    if isinstance(fields[key], ft.Dropdown):
                        fields[key].error_text = value
                    else:
                        fields[key].error = value
            message.value = "入力内容を確認してください．"
            page.update()
            return
        data["trial_end_at"] = data["trial_end_at"] or None
        selected["busy"] = True
        save_button.disabled = True
        for control in [search, plans, manual_button, back_button, *fields.values()]:
            control.disabled = True
        page.update()
        try:
            item = api_client.create_subscription(data)
        except ApiError as error:
            message.value = str(error)
        else:
            on_saved(item)
        finally:
            selected["busy"] = False
            save_button.disabled = False
            for control in [search, plans, manual_button, back_button, *fields.values()]:
                control.disabled = False
            page.update()

    save_button = ft.Button("この内容で登録する", icon=ft.Icons.ADD, bgcolor=theme.ACCENT,
                            color=theme.SURFACE, height=48, on_click=save)
    manual_button = ft.TextButton("定番にないサービスを手入力する", on_click=clear_service)
    back_button = ft.TextButton("一覧に戻る", on_click=lambda e: on_back())
    return ft.Column(spacing=16, scroll=ft.ScrollMode.AUTO, controls=[
        back_button, ft.Text("サブスクを追加", size=26, weight=ft.FontWeight.BOLD, color=theme.INK),
        ft.Text("サービスを選ぶか，契約内容を手入力してください．", color=theme.INK_SUB),
        search, ft.Button("定番サービスを表示・検索", height=44, on_click=search_services), results,
        manual_button, plans, *fields.values(), message, save_button,
    ])
