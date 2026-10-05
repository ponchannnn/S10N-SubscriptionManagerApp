"""画面の切り替え。各画面はここの関数を呼ぶだけでよい(実際の切り替えは main.py が行う)。

使い方:
    import navigation
    navigation.go(page, navigation.REGISTER)   # 登録画面へ
    navigation.go_detail(page, sub["id"])      # 詳細画面へ
    navigation.go_back(page)                   # 元のタブ画面へ戻る
    sub_id = navigation.get_sub_id(page)       # 詳細画面で、表示するサブスクのIDを受け取る
    navigation.open_url(page, sub["cancel_url"])  # 端末のブラウザで開く
"""

import flet as ft

# ---- 画面のルート ----
HOME = "/"
BREAKDOWN = "/breakdown"
DEADLINE = "/deadline"
REGISTER = "/register"
ACCOUNT = "/account"
DETAIL_PREFIX = "/detail/"

TAB_ROUTES = (HOME, BREAKDOWN, DEADLINE)

_LAST_TAB_KEY = "navigation.last_tab"
_RELOAD_KEY = "navigation.reload"


def detail_route(sub_id) -> str:
    """詳細画面のルートを作る。"""
    return f"{DETAIL_PREFIX}{sub_id}"


def go(page: ft.Page, route: str) -> None:
    """指定した画面へ移る。"""
    page.run_task(page.push_route, route)


def go_detail(page: ft.Page, sub_id) -> None:
    """詳細画面へ移る。"""
    go(page, detail_route(sub_id))


def go_back(page: ft.Page) -> None:
    """最後に開いていたタブ画面(ホーム / 内訳 / 期限)へ戻る。"""
    go(page, last_tab(page))


def reload(page: ft.Page) -> None:
    """今の画面を作り直す(通信エラー後の「もう一度読み込む」など)。"""
    handler = page.session.store.get(_RELOAD_KEY)
    if handler:
        handler()


def get_sub_id(page: ft.Page) -> str | None:
    """今のルートが詳細画面なら、サブスクのIDを文字列で返す。"""
    route = page.route or ""
    if route.startswith(DETAIL_PREFIX):
        return route[len(DETAIL_PREFIX):] or None
    return None


def open_url(page: ft.Page, url: str) -> None:
    """端末のブラウザでURLを開く(入会・退会ページ用)。"""
    if url:
        page.run_task(ft.UrlLauncher().launch_url, url)


# ---- ここから下は main.py が使う ----
def last_tab(page: ft.Page) -> str:
    """最後に開いていたタブ画面のルートを返す。"""
    return page.session.store.get(_LAST_TAB_KEY) or HOME


def remember_tab(page: ft.Page, route: str) -> None:
    """開いたタブ画面を覚えておく。"""
    page.session.store.set(_LAST_TAB_KEY, route)


def set_reload_handler(page: ft.Page, handler) -> None:
    """reload() で呼ぶ関数を登録する。"""
    page.session.store.set(_RELOAD_KEY, handler)
