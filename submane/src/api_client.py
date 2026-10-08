"""APIの呼び出しをまとめる。各画面はここの関数だけを使い、httpx を直接呼ばない。

・config.USE_DUMMY_DATA が True の間は、APIを呼ばずに dummy_data.py の内容で動く
  (登録・編集・削除もアプリを閉じるまでは反映される)
・USE_DUMMY_DATA が False のときは、local_db.py(docs/local_db.md)に前回の取得結果を
  キャッシュし、サーバに接続できないときはそのキャッシュを返す
・失敗したときは ApiError(接続できないときは ApiError のサブクラス OfflineError)を送出する。
  画面側で except ApiError して案内を表示する
・APIの項目名とアプリ内の項目名が違う場合は、_to_app_subscription() / _to_api_subscription()
  の中だけで変換する(画面は直さない)
"""

import copy
from datetime import datetime
from urllib.parse import urlparse

import httpx

import config
import dummy_data
import local_db


class ApiError(Exception):
    """APIの呼び出しに失敗したときの例外。str(err) が画面に出せる日本語の説明になる。"""


class OfflineError(ApiError):
    """サーバに接続できなかったとき。list_subscriptions() などはこれを捕まえてキャッシュへ切り替える。"""


# ------------------------------------------------------------------
# APIのパス(仮)。API担当の仕様書(docs/)が確定したらここを合わせる
# ------------------------------------------------------------------
ENDPOINTS = {
    "sign_up": "/api/auth/register",
    "log_in": "/api/auth/login",
    "log_out": "/api/auth/logout",
    "subscriptions": "/api/subscriptions",
    "subscription": "/api/subscriptions/{sub_id}",
    "services": "/api/services",
}

# ------------------------------------------------------------------
# 内部の状態
# ------------------------------------------------------------------
_client: httpx.Client | None = None  # ログイン状態(cookie)を保つため使い回す
_logged_in = config.USE_DUMMY_DATA and config.DUMMY_START_LOGGED_IN
_dummy_subs = copy.deepcopy(dummy_data.SUBSCRIPTIONS)
_session_restored = False  # 起動後、保存していたCookieを一度だけ読み込んだか
_HOST = urlparse(config.API_BASE_URL).hostname if config.API_BASE_URL else None


def _http() -> httpx.Client:
    """httpx のクライアントを返す。cookie を保持するので1つを使い回す。"""
    global _client, _logged_in, _session_restored
    if _client is None:
        _client = httpx.Client(base_url=config.API_BASE_URL, timeout=config.REQUEST_TIMEOUT)
    if not _session_restored:
        _session_restored = True
        cookie = local_db.get_state("session_cookie")
        if cookie:
            _client.cookies.set("session_id", cookie, domain=_HOST)
            _logged_in = True
    return _client


def _save_session(email: str | None = None) -> None:
    """ログイン・会員登録の直後: 受け取ったCookieと(あれば)メールアドレスを保存する。"""
    cookie = _http().cookies.get("session_id")
    if cookie:
        local_db.set_state("session_cookie", cookie)
    if email:
        local_db.set_state("user_email", email)


def _request(method: str, path: str, **kwargs):
    """APIを呼び、JSONを返す。通信できなければ OfflineError、APIがエラーを返したら ApiError にそろえる。"""
    global _logged_in
    try:
        response = _http().request(method, path, **kwargs)
    except httpx.TimeoutException as err:
        raise OfflineError("サーバからの応答がありません。時間をおいてもう一度お試しください。") from err
    except httpx.HTTPError as err:
        raise OfflineError("サーバに接続できません。通信環境を確認してください。") from err
    if response.status_code == 401:
        _logged_in = False
        local_db.clear_user_data()
        raise ApiError("ログインの有効期限が切れました。もう一度ログインしてください。")
    if response.status_code == 404:
        raise ApiError("データが見つかりません。")
    if response.status_code >= 400:
        raise ApiError(f"サーバでエラーが起きました(コード {response.status_code})。")
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError as err:
        raise ApiError("サーバから想定外の応答が返りました。") from err


def _to_app_subscription(data: dict) -> dict:
    """APIのサブスク1件を、アプリ内で使う形にそろえる。"""
    return {
        "id": data.get("id"),
        "name": data.get("name", ""),
        "icon": data.get("icon"),
        "plan_name": data.get("plan_name", ""),
        "cycle": data.get("cycle", "monthly"),
        "amount": int(data.get("amount") or 0),
        "joined_at": data.get("joined_at"),
        "join_url": data.get("join_url", ""),
        "cancel_url": data.get("cancel_url", ""),
        "cancel_memo": data.get("cancel_memo", ""),
        "status": data.get("status", "active"),
        "trial_end_at": data.get("trial_end_at"),
    }


def _to_api_subscription(data: dict) -> dict:
    """アプリ内のサブスク1件を、APIへ送る形にする(今は同じ項目名)。"""
    return dict(data)


def _find_dummy(sub_id) -> dict:
    """ダミーデータから1件探す。なければ ApiError。"""
    for sub in _dummy_subs:
        if str(sub["id"]) == str(sub_id):
            return sub
    raise ApiError("データが見つかりません。")


# ------------------------------------------------------------------
# アカウント
# ------------------------------------------------------------------
def is_logged_in() -> bool:
    """ログイン済みかどうかを返す。本物のAPIのときは、保存したCookieの有無も見る。"""
    if not config.USE_DUMMY_DATA:
        _http()  # 保存していたCookieをまだ読んでいなければここで読む
    return _logged_in


def sign_up(email: str, password: str) -> None:
    """会員登録する。成功したらログイン済みになる。"""
    global _logged_in
    if not config.USE_DUMMY_DATA:
        _request("POST", ENDPOINTS["sign_up"], json={"email": email, "password": password})
        _save_session(email)
        refresh_services()
    _logged_in = True


def log_in(email: str, password: str) -> None:
    """ログインする。"""
    global _logged_in
    if not config.USE_DUMMY_DATA:
        _request("POST", ENDPOINTS["log_in"], json={"email": email, "password": password})
        _save_session(email)
        refresh_services()
    _logged_in = True


def log_out() -> None:
    """ログアウトする。端末に残した前回のデータも消す。"""
    global _logged_in
    if not config.USE_DUMMY_DATA:
        _request("POST", ENDPOINTS["log_out"])
    _logged_in = False
    local_db.clear_user_data()


# ------------------------------------------------------------------
# サブスク
# ------------------------------------------------------------------
def list_subscriptions() -> list[dict]:
    """自分のサブスク一覧を登録順で返す。通信できなければ前回取得した一覧を返す。"""
    if config.USE_DUMMY_DATA:
        return copy.deepcopy(_dummy_subs)
    try:
        items = [_to_app_subscription(item) for item in _request("GET", ENDPOINTS["subscriptions"]) or []]
    except OfflineError:
        cached = local_db.load_subscriptions()
        if not cached:
            raise
        return cached
    local_db.replace_subscriptions(items, datetime.now().astimezone().isoformat())
    return items


def get_subscription(sub_id) -> dict:
    """サブスクを1件返す。通信できなければ前回取得した内容を返す。"""
    if config.USE_DUMMY_DATA:
        return copy.deepcopy(_find_dummy(sub_id))
    try:
        item = _to_app_subscription(_request("GET", ENDPOINTS["subscription"].format(sub_id=sub_id)))
    except OfflineError:
        cached = local_db.load_subscription(sub_id)
        if cached is None:
            raise
        return cached
    local_db.upsert_subscription(item)
    return item


def create_subscription(data: dict) -> dict:
    """サブスクを登録し、登録された1件を返す。通信できないときはそのまま失敗する(あとで送る仕組みは作らない)。"""
    if config.USE_DUMMY_DATA:
        new_id = max((sub["id"] for sub in _dummy_subs), default=0) + 1
        sub = _to_app_subscription({**data, "id": new_id})
        _dummy_subs.append(sub)
        return copy.deepcopy(sub)
    item = _to_app_subscription(_request("POST", ENDPOINTS["subscriptions"], json=_to_api_subscription(data)))
    local_db.upsert_subscription(item)
    return item


def update_subscription(sub_id, data: dict) -> dict:
    """サブスクを編集し、更新後の1件を返す。解約・再契約は data に status を入れる。"""
    if config.USE_DUMMY_DATA:
        sub = _find_dummy(sub_id)
        sub.update({key: value for key, value in data.items() if key != "id"})
        return copy.deepcopy(sub)
    path = ENDPOINTS["subscription"].format(sub_id=sub_id)
    item = _to_app_subscription(_request("PUT", path, json=_to_api_subscription(data)))
    local_db.upsert_subscription(item)
    return item


def delete_subscription(sub_id) -> None:
    """サブスクを削除する。"""
    if config.USE_DUMMY_DATA:
        _dummy_subs.remove(_find_dummy(sub_id))
        return
    _request("DELETE", ENDPOINTS["subscription"].format(sub_id=sub_id))
    local_db.delete_subscription(sub_id)


# ------------------------------------------------------------------
# 定番サービス
# ------------------------------------------------------------------
def refresh_services() -> None:
    """定番サービスのマスタを取得し直し、オフライン検索用に保存する(ログイン直後に呼ぶ)。"""
    if config.USE_DUMMY_DATA:
        return
    try:
        services = _request("GET", ENDPOINTS["services"]) or []
    except OfflineError:
        return
    local_db.replace_services(services)


def search_services(keyword: str) -> list[dict]:
    """定番サービスを名称で検索する。keyword が空なら全件。通信できなければ前回のマスタから探す。"""
    if config.USE_DUMMY_DATA:
        word = (keyword or "").strip().lower()
        return [copy.deepcopy(s) for s in dummy_data.SERVICES if word in s["name"].lower()]
    try:
        return _request("GET", ENDPOINTS["services"], params={"q": keyword}) or []
    except OfflineError:
        return local_db.search_services(keyword or "")


def icon_url(icon: str | None) -> str | None:
    """アイコンのURLを返す。APIが / から始まるパスを返した場合はAPIのURLを前に付ける。"""
    if not icon:
        return None
    if icon.startswith("/"):
        return config.API_BASE_URL + icon
    return icon


# ------------------------------------------------------------------
# 端末ごとの設定(ログアウトしても残る)
# ------------------------------------------------------------------
def get_yearly_mode() -> str:
    """年額プランの計上方法("billing"=更新月に全額 / "average"=月割り)。内訳画面が使う。"""
    return local_db.get_state("yearly_mode", "billing")


def set_yearly_mode(mode: str) -> None:
    """年額プランの計上方法を端末に保存する。"""
    local_db.set_state("yearly_mode", mode)


def last_updated() -> str | None:
    """前回 list_subscriptions() でサーバから取得できた時刻(ISO文字列)。取得したことがなければ None。"""
    return local_db.get_state("subscriptions_fetched_at")
