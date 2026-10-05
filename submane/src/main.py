"""アプリの起動と画面の切り替え。

画面を増やすとき:
  1. views/ に「page を受け取って中身を返す関数」を作る
  2. navigation.py にルートを足す
  3. 下の SCREENS に1行足す
ヘッダーと下部タブはここで全画面に付けるので、各画面は中身だけを返せばよい。
"""

import traceback
from dataclasses import dataclass
from typing import Callable

import flet as ft

import api_client
import navigation
import theme
from components import feedback
from components.app_header import app_header
from components.tab_bar import tab_bar
from views.account import account_view
from views.breakdown import breakdown_view
from views.deadline import deadline_view
from views.detail import detail_view
from views.home import home_view
from views.register import register_view


@dataclass
class Screen:
    """1画面分の設定。"""

    view: Callable[[ft.Page], ft.Control]  # 画面の中身を返す関数
    title: str | None = None               # ヘッダーに出す画面名(None ならアプリ名)


# ルート → 画面。タブ画面(ホーム / 内訳 / 期限)は title なし
SCREENS = {
    navigation.HOME: Screen(home_view),
    navigation.BREAKDOWN: Screen(breakdown_view),
    navigation.DEADLINE: Screen(deadline_view),
    navigation.REGISTER: Screen(register_view, title="サブスクを追加"),
    navigation.ACCOUNT: Screen(account_view, title="アカウント"),
}
DETAIL_SCREEN = Screen(detail_view, title="サブスクの詳細")


def _resolve(route: str) -> Screen | None:
    """ルートに対応する画面を返す。なければ None。"""
    if route.startswith(navigation.DETAIL_PREFIX):
        return DETAIL_SCREEN
    return SCREENS.get(route)


def _shell(route: str, header: ft.Control, content: ft.Control, footer: ft.Control | None) -> ft.View:
    """ヘッダー + 中身 + 下部タブ を1つの画面(View)にまとめる。"""
    controls = [header, ft.Container(content=content, expand=True)]
    if footer:
        controls.append(footer)
    return ft.View(
        route=route,
        padding=0,
        spacing=0,
        bgcolor=theme.GROUND,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    expand=True,
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=controls,
                ),
            )
        ],
    )


def main(page: ft.Page) -> None:
    """アプリの入口。"""
    page.title = "サブマネ"
    theme.apply(page)

    # PCで確認するときはスマホの大きさのウィンドウにする(実機では何もしない)
    window = getattr(page, "window", None)
    if window is not None and not page.web and page.platform in (
        ft.PagePlatform.WINDOWS,
        ft.PagePlatform.MACOS,
        ft.PagePlatform.LINUX,
    ):
        window.width = theme.BASE_WIDTH
        window.height = theme.BASE_HEIGHT

    def build_content(screen: Screen) -> ft.Control:
        """画面の中身を作る。画面側で想定外のエラーが起きてもアプリ全体は止めない。"""
        try:
            return screen.view(page)
        except Exception:  # noqa: BLE001 開発中に原因を追えるよう、内容はコンソールに出す
            traceback.print_exc()
            return feedback.error_panel(page, "画面の表示中にエラーが起きました。")

    def show_route(e=None) -> None:
        """今のルートに合わせて画面を組み立てる。"""
        route = getattr(e, "route", None) or page.route or navigation.HOME
        screen = _resolve(route)
        if screen is None:
            navigation.go(page, navigation.HOME)
            return

        page.views.clear()

        # 未ログインなら会員登録・ログイン画面だけを出す
        if not api_client.is_logged_in():
            if route != navigation.ACCOUNT:
                navigation.go(page, navigation.ACCOUNT)
                return
            header = app_header(page, show_actions=False)
            page.views.append(_shell(route, header, build_content(screen), footer=None))
            page.update()
            return

        if route in navigation.TAB_ROUTES:
            navigation.remember_tab(page, route)
            page.views.append(_shell(route, app_header(page), build_content(screen), tab_bar(page, route)))
        else:
            # タブ画面の上に重ねる。端末の「戻る」で元のタブ画面に戻れる
            base = navigation.last_tab(page)
            page.views.append(_shell(base, app_header(page), ft.Container(), tab_bar(page, base)))
            header = app_header(page, title=screen.title, show_back=True, show_actions=False)
            page.views.append(_shell(route, header, build_content(screen), tab_bar(page, None)))
        page.update()

    def on_view_pop(e) -> None:
        """端末の「戻る」操作。"""
        navigation.go_back(page)

    navigation.set_reload_handler(page, show_route)
    page.on_route_change = show_route
    page.on_view_pop = on_view_pop
    show_route()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
