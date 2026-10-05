"""詳細画面に組み込む解約・再契約の状態変更部品．"""
from datetime import datetime
import flet as ft
import theme
from api_client import ApiError
from logic.subscriptions import ValidationError, cancellation_patch, reactivation_patch, valid_url


def status_actions(page, subscription, api, on_changed):
    """公式サイトを開く操作と，手続き後の記録を別の操作として提供する．"""
    cancelled = subscription.get("status") == "cancelled"
    url = subscription.get("join_url" if cancelled else "cancel_url", "")
    label = "入会サイトを開く" if cancelled else "退会サイトを開く"
    error_text = ft.Text("", color=theme.ERROR)
    new_joined = ft.TextField(label="再契約の入会日時（日本時間）",
                             value=datetime.now().strftime("%Y-%m-%dT%H:%M"),
                             visible=cancelled)
    confirm = ft.Checkbox(label="公式サイトで手続きを完了しました", value=False)
    busy = {"value": False}

    def change_status(event):
        """手続き完了確認後に保存し，成功した場合だけ一覧を更新する．"""
        if busy["value"]:
            return
        if not confirm.value:
            error_text.value = "公式サイトでの手続き完了を確認してください．"
            page.update()
            return
        try:
            patch = reactivation_patch(subscription, new_joined.value) if cancelled else cancellation_patch()
        except ValidationError as error:
            new_joined.error = error.errors.get("joined_at")
            page.update()
            return
        # api_client(共通コード)側の項目名は trial_end_at(s なし)
        if "trial_ends_at" in patch:
            patch["trial_end_at"] = patch.pop("trial_ends_at") or None
        busy["value"] = True
        save.disabled = True
        new_joined.disabled = True
        confirm.disabled = True
        error_text.value = ""
        page.update()
        try:
            item = api.update_subscription(subscription["id"], patch)
        except ApiError as error:
            error_text.value = str(error)
        else:
            on_changed(item)
        finally:
            busy["value"] = False
            save.disabled = False
            new_joined.disabled = False
            confirm.disabled = False
            page.update()

    save = ft.Button("再契約済みとして記録" if cancelled else "解約済みとして記録",
                     bgcolor=theme.ACCENT, color=theme.SURFACE, height=48, on_click=change_status)
    return ft.Column(spacing=12, controls=[
        ft.Text("再契約する" if cancelled else "解約する", size=20, weight=ft.FontWeight.BOLD),
        ft.Text("公式サイトで手続きを済ませた後，契約状態を更新してください．", color=theme.INK_SUB),
        ft.Button(label, url=url if url and valid_url(url) else None,
                  disabled=not bool(url and valid_url(url)), height=44, icon=ft.Icons.OPEN_IN_NEW),
        ft.Text("URLが未登録です．公式サイトで手続きしてください．", visible=not bool(url), color=theme.INK_SUB),
        new_joined, confirm, error_text, save,
    ])
