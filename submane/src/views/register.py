"""石井担当：定番サービス検索と手入力によるサブスク登録画面．"""
import asyncio
from datetime import datetime
import flet as ft
import theme
from api_client import ApiClient, ApiError
from logic.subscriptions import JST, CYCLE_LABELS, STATUS_LABELS, ValidationError, validate_subscription


def register_view(page, api=None, on_saved=None, on_back=None):
    """pageのみでも生成でき，共通APIと遷移コールバックを注入できる．"""
    api = api or ApiClient()
    message = ft.Text("", color=theme.ERROR)
    results = ft.Column(spacing=8)
    plans = ft.Dropdown(label="定番サービスのプラン", visible=False)
    selected = {"service": None, "search_version": 0, "busy": False, "completed": False}
    fields = {
        "name": ft.TextField(label="サービス名 *", max_length=100),
        "plan_name": ft.TextField(label="料金プラン名 *", max_length=100),
        "cycle": ft.Dropdown(label="更新周期 *", value="monthly", options=[
            ft.DropdownOption(key=key, text=value) for key, value in CYCLE_LABELS.items()]),
        "amount": ft.TextField(label="1回の支払額（円） *", keyboard_type=ft.KeyboardType.NUMBER,
                               helper="無料トライアル中も，有料移行後の金額を入力してください．"),
        "joined_at": ft.TextField(label="入会日時 *", value=datetime.now(JST).strftime("%Y-%m-%dT%H:%M"),
                                  helper="日本時間・分単位の例：2026-10-05T12:30"),
        "status": ft.Dropdown(label="契約状態 *", value="active", options=[
            ft.DropdownOption(key=key, text=value) for key, value in STATUS_LABELS.items() if key != "cancelled"]),
        "trial_ends_at": ft.TextField(label="トライアル終了日時 *", visible=False,
                                      hint_text="2026-11-05T12:30"),
        "join_url": ft.TextField(label="入会URL（任意）", hint_text="https://…"),
        "cancel_url": ft.TextField(label="退会URL（任意）", hint_text="https://…"),
        "cancel_memo": ft.TextField(label="退会に必要な情報（任意）", multiline=True,
                                    min_lines=2, max_lines=4, max_length=1000,
                                    helper="例：メールアドレスとパスワードの準備が必要．パスワード自体は入力しないでください．"),
    }

    def status_changed(event):
        """無料トライアルを選択したときだけ終了日時を表示する．"""
        fields["trial_ends_at"].visible = fields["status"].value == "trial"
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
        selected["search_version"] += 1
        selected["completed"] = False
        save_button.disabled = False
        selected["service"] = service
        for key in ("name", "join_url", "cancel_url", "cancel_memo"):
            fields[key].read_only = True
        for key in ("name", "join_url", "cancel_url", "cancel_memo"):
            fields[key].value = service.get(key, "")
        plans.options = [ft.DropdownOption(key=str(index), text=plan["name"])
                         for index, plan in enumerate(service.get("plans", []))]
        plans.visible = bool(plans.options)
        plans.value = "0" if plans.options else None
        apply_plan()
        results.controls = [ft.Text("選択済み：" + service["name"], color=theme.ACCENT)]
        page.update()

    async def search_services(event=None):
        """連続入力では古い検索結果を破棄し，失敗時は再試行できる．"""
        selected["search_version"] += 1
        version = selected["search_version"]
        await asyncio.sleep(0.25)
        if version != selected["search_version"]:
            return
        results.controls = [ft.ProgressRing(width=20, height=20)]
        page.update()
        try:
            services = await api.search_services(search.value or "")
            if version != selected["search_version"]:
                return
            results.controls = [ft.Button(service["name"], height=44,
                               on_click=lambda e, service=service: choose_service(service)) for service in services]
            if not services:
                results.controls = [ft.Text("該当するサービスがありません．下の欄へ手入力できます．", color=theme.INK_SUB)]
        except ApiError as error:
            if version != selected["search_version"]:
                return
            results.controls = [ft.Text(str(error), color=theme.ERROR),
                                ft.Button("検索を再試行", on_click=search_services)]
        page.update()

    search = ft.TextField(label="定番サービスを名称で検索", prefix_icon=ft.Icons.SEARCH,
                          on_change=search_services, on_submit=search_services)

    def clear_service(event):
        """定番サービスとの関連を解除し，手入力用の空欄に戻す．"""
        selected["search_version"] += 1
        selected["completed"] = False
        save_button.disabled = False
        selected["service"] = None
        for key in ("name", "join_url", "cancel_url", "cancel_memo"):
            fields[key].read_only = False
        for key in ("name", "plan_name", "amount", "join_url", "cancel_url", "cancel_memo"):
            fields[key].value = ""
        plans.visible = False
        results.controls = []
        page.update()

    async def save(event):
        """入力を検証し，二重クリックによる重複登録を防ぐ．"""
        if selected["busy"] or selected["completed"]:
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
        plan = service.get("plans", [])[int(plans.value)] if service and plans.value is not None else {}
        data.update(icon=service.get("icon", ""), service_id=service.get("id", ""), plan_id=plan.get("id", ""))
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
        selected["busy"] = True
        save_button.disabled = True
        for control in [search, search_button, plans, manual_button, back_button, *fields.values()]:
            control.disabled = True
        page.update()
        try:
            item = await api.create_subscription(data)
        except ApiError as error:
            message.value = str(error)
            aliases = {"custom_name": "name", "custom_join_url": "join_url",
                       "custom_cancel_url": "cancel_url", "custom_cancel_memo": "cancel_memo"}
            for key, errors in error.details.items():
                control = fields.get(aliases.get(key, key))
                if control is not None:
                    text = "，".join(map(str, errors)) if isinstance(errors, list) else str(errors)
                    if isinstance(control, ft.Dropdown):
                        control.error_text = text
                    else:
                        control.error = text
        else:
            selected["completed"] = True
            if on_saved:
                result = on_saved(item)
                if asyncio.iscoroutine(result):
                    await result
            else:
                message.color = theme.ACCENT
                message.value = "登録しました．"
        finally:
            selected["busy"] = False
            save_button.disabled = selected["completed"]
            for control in [search, search_button, plans, manual_button, back_button, *fields.values()]:
                control.disabled = False
            page.update()

    save_button = ft.Button("この内容で登録する", icon=ft.Icons.ADD, bgcolor=theme.ACCENT,
                            color=theme.SURFACE, height=48, on_click=save)
    manual_button = ft.TextButton("定番にないサービスを手入力する", on_click=clear_service)
    back_button = ft.TextButton("一覧に戻る", on_click=lambda e: on_back() if on_back else page.navigate("/"))
    search_button = ft.Button("定番サービスを表示・検索", height=44, on_click=search_services)
    return ft.Column(spacing=16, controls=[
        back_button, ft.Text("サブスクを追加", size=26, weight=ft.FontWeight.BOLD, color=theme.INK),
        ft.Text("サービスを選ぶか，契約内容を手入力してください．定番の名称・URL・退会案内を変更する場合は手入力に切り替えてください．", color=theme.INK_SUB),
        search, search_button, results,
        manual_button, plans, *fields.values(), message, save_button,
    ])
