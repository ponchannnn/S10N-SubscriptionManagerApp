"""会員登録・ログイン画面(担当: 西内)。

ログイン済みなら自分の情報(メールアドレス)とログアウトボタンを、
未ログインなら新規登録・ログインを切り替えられるフォームを返す。
"""

import flet as ft

import api_client
import navigation
import theme
from api_client import ApiError
from components import feedback


def account_view(page: ft.Page) -> ft.Control:
    """会員登録・ログイン画面の中身を返す。"""
    if api_client.is_logged_in():
        return _signed_in_view(page)
    return _sign_in_view(page)


def _signed_in_view(page: ft.Page) -> ft.Control:
    """ログイン済みのときの中身。"""
    email = api_client.get_user_email() or "ダミーデータでログイン中"

    def log_out(event):
        api_client.log_out()
        navigation.reload(page)

    return ft.Column(
        spacing=16,
        controls=[
            theme.text("ログイン中", size=26, weight="bold"),
            theme.text(email, size=14, color=theme.INK_SUB),
            ft.OutlinedButton("ログアウト", on_click=log_out, height=theme.TAP_MIN),
        ],
    )


def _sign_in_view(page: ft.Page) -> ft.Control:
    """未ログインのときの中身(新規登録・ログインを切り替えるフォーム)。"""
    state = {"mode": "login", "busy": False}
    message = ft.Text("", color=theme.ERROR)
    email_field = ft.TextField(label="メールアドレス", keyboard_type=ft.KeyboardType.EMAIL)
    password_field = ft.TextField(label="パスワード", password=True, can_reveal_password=True,
                                  helper="8文字以上")
    title = theme.text("ログイン", size=26, weight="bold")
    toggle_button = ft.TextButton("はじめての方はこちら(新規登録)")
    submit_button = feedback.primary_button("ログイン", on_click=lambda e: submit(e))

    def apply_mode():
        """今のモード(login/signup)に合わせて文言を変える。"""
        is_signup = state["mode"] == "signup"
        title.value = "新規登録" if is_signup else "ログイン"
        toggle_button.content = "登録済みの方はこちら(ログイン)" if is_signup else "はじめての方はこちら(新規登録)"
        submit_button.content = "新規登録" if is_signup else "ログイン"
        page.update()

    def toggle_mode(event):
        state["mode"] = "signup" if state["mode"] == "login" else "login"
        message.value = ""
        email_field.error = None
        password_field.error = None
        apply_mode()

    toggle_button.on_click = toggle_mode

    def submit(event):
        if state["busy"]:
            return
        email_field.error = None
        password_field.error = None
        message.value = ""
        if not (email_field.value or "").strip():
            email_field.error = "入力してください．"
        if not password_field.value:
            password_field.error = "入力してください．"
        elif len(password_field.value) < 8:
            password_field.error = "8文字以上で入力してください．"
        if email_field.error or password_field.error:
            page.update()
            return

        state["busy"] = True
        submit_button.disabled = True
        toggle_button.disabled = True
        page.update()
        try:
            if state["mode"] == "signup":
                api_client.sign_up(email_field.value.strip(), password_field.value)
            else:
                api_client.log_in(email_field.value.strip(), password_field.value)
        except ApiError as error:
            message.value = str(error)
        else:
            navigation.go(page, navigation.HOME)
            return
        finally:
            state["busy"] = False
            submit_button.disabled = False
            toggle_button.disabled = False
            page.update()

    return ft.Column(
        spacing=16,
        controls=[
            title,
            theme.text("サブマネを使うには会員登録またはログインしてください．", color=theme.INK_SUB),
            email_field,
            password_field,
            message,
            submit_button,
            toggle_button,
        ],
    )
