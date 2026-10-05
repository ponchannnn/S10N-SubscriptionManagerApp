"""石井担当機能を起動する単独確認用アプリ．"""
import argparse
import os
from pathlib import Path
from urllib.parse import quote, unquote
import flet as ft
import config
import theme
from api_client import ApiClient, ApiError
from views.preview import preview_list, preview_status
from views.register import register_view


async def main(page: ft.Page):
    """共通コード未完成でも登録から状態変更まで確認できるようにする．"""
    page.title = "サブマネ | 石井担当"
    page.bgcolor = theme.GROUND
    page.padding = theme.GUTTER
    page.theme = ft.Theme(color_scheme_seed=theme.ACCENT, font_family=theme.FONT)
    page.theme_mode = ft.ThemeMode.LIGHT
    page.fonts = {theme.FONT: "fonts/ZenKakuGothicNew-Regular.ttf"}
    page.window.width = 390
    page.window.height = 850
    api = ApiClient()
    state = {"order": "frequency", "notice": "", "route_version": 0}
    content = ft.Column(spacing=16, scroll=ft.ScrollMode.AUTO, expand=True)
    page.add(ft.Text("サブマネ", color=theme.ACCENT, size=24, weight=ft.FontWeight.BOLD),
             ft.Text("ローカル試作版：正式なサービス情報はAPI接続後に取得します．" if config.USE_DUMMY_DATA else "API接続モード",
                     size=12, color=theme.INK_SUB), content)

    def navigate(route):
        """画面遷移を単独確認用mainへ集約する．"""
        page.navigate(route)

    async def saved(item):
        """保存完了の案内を一覧へ渡す．"""
        state["notice"] = item["name"] + "を保存しました．"
        await page.push_route("/")

    async def order_changed(event):
        """選んだ並び順で一覧を再取得して表示する．"""
        state["order"] = event.control.value
        await route_changed()

    async def route_changed(event=None):
        """取得失敗と読み込み中を表示し，遅い応答による画面巻き戻りを防ぐ．"""
        state["route_version"] += 1
        version = state["route_version"]
        route = page.route or "/"
        content.controls = [ft.ProgressRing()]
        page.update()
        try:
            if route == "/register":
                view = register_view(page, api, on_saved=saved, on_back=lambda: navigate("/"))
            elif route.startswith("/status/"):
                item = await api.get_subscription(unquote(route[len("/status/"):]))
                view = preview_status(page, item, api, lambda: navigate("/"), saved)
            else:
                items = await api.list_subscriptions()
                view = preview_list(page, items, state["order"], order_changed,
                                    lambda: navigate("/register"),
                                    lambda sub_id: navigate("/status/" + quote(str(sub_id), safe="")),
                                    state["notice"])
                state["notice"] = ""
        except ApiError as error:
            view = ft.Column(controls=[ft.Text(str(error), color=theme.ERROR),
                                       ft.Button("再試行", on_click=route_changed),
                                       ft.TextButton("一覧へ戻る", on_click=lambda e: navigate("/"))])
        if version == state["route_version"]:
            content.controls = [view]
            page.update()

    page.on_route_change = route_changed
    await route_changed()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="サブマネ 石井担当の動作確認")
    parser.add_argument("--web", action="store_true", help="ブラウザで確認")
    parser.add_argument("--headless", action="store_true", help="ブラウザを自動で開かない")
    parser.add_argument("--port", type=int, default=8550)
    args = parser.parse_args()
    view = ft.AppView.WEB_BROWSER if args.web else ft.AppView.FLET_APP
    if args.headless:
        os.environ["FLET_FORCE_WEB_SERVER"] = "true"
        view = ft.AppView.WEB_BROWSER
    ft.run(main, view=view, host="127.0.0.1", port=args.port,
           assets_dir=str(Path(__file__).parent / "assets"))
