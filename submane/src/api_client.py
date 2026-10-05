"""APIの呼び出しをまとめる。各画面はここの関数だけを使い、httpx を直接呼ばない。

・config.USE_DUMMY_DATA が True の間は、APIを呼ばずに dummy_data.py の内容で動く
  (登録・編集・削除もアプリを閉じるまでは反映される)
・失敗したときは ApiError を送出する。画面側で except して案内を表示する
・APIの項目名とアプリ内の項目名が違う場合は、_to_app_subscription() / _to_api_subscription()
  の中だけで変換する(画面は直さない)
"""

import copy

import httpx

import config
import dummy_data


class ApiError(Exception):
    """APIの呼び出しに失敗したときの例外。str(err) が画面に出せる日本語の説明になる。"""


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


def _http() -> httpx.Client:
    """httpx のクライアントを返す。cookie を保持するので1つを使い回す。"""
    global _client
    if _client is None:
        _client = httpx.Client(base_url=config.API_BASE_URL, timeout=config.REQUEST_TIMEOUT)
    return _client


def _request(method: str, path: str, **kwargs):
    """APIを呼び、JSONを返す。失敗したら ApiError にそろえる。"""
    global _logged_in
    try:
        response = _http().request(method, path, **kwargs)
    except httpx.TimeoutException as err:
        raise ApiError("サーバからの応答がありません。時間をおいてもう一度お試しください。") from err
    except httpx.HTTPError as err:
        raise ApiError("サーバに接続できません。通信環境を確認してください。") from err
    if response.status_code == 401:
        _logged_in = False
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
    """ログイン済みかどうかを返す。"""
    return _logged_in


def sign_up(email: str, password: str) -> None:
    """会員登録する。成功したらログイン済みになる。"""
    global _logged_in
    if not config.USE_DUMMY_DATA:
        _request("POST", ENDPOINTS["sign_up"], json={"email": email, "password": password})
    _logged_in = True


def log_in(email: str, password: str) -> None:
    """ログインする。"""
    global _logged_in
    if not config.USE_DUMMY_DATA:
        _request("POST", ENDPOINTS["log_in"], json={"email": email, "password": password})
    _logged_in = True


def log_out() -> None:
    """ログアウトする。"""
    global _logged_in
    if not config.USE_DUMMY_DATA:
        _request("POST", ENDPOINTS["log_out"])
    _logged_in = False


# ------------------------------------------------------------------
# サブスク
# ------------------------------------------------------------------
def list_subscriptions() -> list[dict]:
    """自分のサブスク一覧を登録順で返す。"""
    if config.USE_DUMMY_DATA:
        return copy.deepcopy(_dummy_subs)
    return [_to_app_subscription(item) for item in _request("GET", ENDPOINTS["subscriptions"]) or []]


def get_subscription(sub_id) -> dict:
    """サブスクを1件返す。"""
    if config.USE_DUMMY_DATA:
        return copy.deepcopy(_find_dummy(sub_id))
    return _to_app_subscription(_request("GET", ENDPOINTS["subscription"].format(sub_id=sub_id)))


def create_subscription(data: dict) -> dict:
    """サブスクを登録し、登録された1件を返す。"""
    if config.USE_DUMMY_DATA:
        new_id = max((sub["id"] for sub in _dummy_subs), default=0) + 1
        sub = _to_app_subscription({**data, "id": new_id})
        _dummy_subs.append(sub)
        return copy.deepcopy(sub)
    return _to_app_subscription(_request("POST", ENDPOINTS["subscriptions"], json=_to_api_subscription(data)))


def update_subscription(sub_id, data: dict) -> dict:
    """サブスクを編集し、更新後の1件を返す。解約・再契約は data に status を入れる。"""
    if config.USE_DUMMY_DATA:
        sub = _find_dummy(sub_id)
        sub.update({key: value for key, value in data.items() if key != "id"})
        return copy.deepcopy(sub)
    path = ENDPOINTS["subscription"].format(sub_id=sub_id)
    return _to_app_subscription(_request("PUT", path, json=_to_api_subscription(data)))


def delete_subscription(sub_id) -> None:
    """サブスクを削除する。"""
    if config.USE_DUMMY_DATA:
        _dummy_subs.remove(_find_dummy(sub_id))
        return
    _request("DELETE", ENDPOINTS["subscription"].format(sub_id=sub_id))


# ------------------------------------------------------------------
# 定番サービス
# ------------------------------------------------------------------
def search_services(keyword: str) -> list[dict]:
    """定番サービスを名称で検索する。keyword が空なら全件。"""
    if config.USE_DUMMY_DATA:
        word = (keyword or "").strip().lower()
        return [copy.deepcopy(s) for s in dummy_data.SERVICES if word in s["name"].lower()]
    return _request("GET", ENDPOINTS["services"], params={"q": keyword}) or []


def icon_url(icon: str | None) -> str | None:
    """アイコンのURLを返す。APIが / から始まるパスを返した場合はAPIのURLを前に付ける。"""
    if not icon:
        return None
    if icon.startswith("/"):
        return config.API_BASE_URL + icon
    return icon
