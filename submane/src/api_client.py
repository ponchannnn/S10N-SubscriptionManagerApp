import asyncio
import copy
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from threading import RLock
from uuid import uuid4
from urllib.parse import quote
import httpx
import config
from dummy_data import SERVICES
from logic.api_contract import registration_payload, update_payload
from logic.subscriptions import normalize_keyword, validate_subscription


import dummy_data


class ApiError(RuntimeError):
    """画面に表示できる保存・通信エラー．"""

    def __init__(self, message, *, status_code=None, code=None, details=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.details = details if isinstance(details, dict) else {}


class OfflineError(ApiError):
    """オンライン専用の登録・更新を実行できない．"""





# ------------------------------------------------------------------
# サーバ設計書v0.2のAPIパス
# ------------------------------------------------------------------
ENDPOINTS = {
    "sign_up": "api/v1/signup",
    "log_in": "api/v1/session",
    "log_out": "api/v1/session",
    "subscriptions": "api/v1/subscriptions",
    "subscription": "api/v1/subscriptions/{sub_id}",
    "services": "api/v1/services",
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
        if not config.API_BASE_URL or "<" in config.API_BASE_URL:
            raise ApiError("APIの接続先が未設定です．")
        _client = httpx.Client(base_url=config.API_BASE_URL, timeout=config.REQUEST_TIMEOUT)
    return _client


def _request(method: str, path: str, **kwargs):
    """APIを呼び、JSONを返す。失敗したら ApiError にそろえる。"""
    global _logged_in
    try:
        base = str(_http().base_url).rstrip("/")
        if base.endswith("/api/v1"):
            path = path.removeprefix("api/v1/")
        response = _http().request(method, base + "/" + path, **kwargs)
    except httpx.TimeoutException as err:
        raise OfflineError("サーバからの応答がありません。時間をおいてもう一度お試しください。") from err
    except httpx.HTTPError as err:
        raise OfflineError("サーバに接続できません。通信環境を確認してください。") from err
    if response.status_code == 401:
        _logged_in = False
        raise ApiError("ログインの有効期限が切れました。もう一度ログインしてください。")
    if response.status_code == 404:
        raise ApiError("データが見つかりません。")
    if response.status_code >= 400:
        try:
            body = response.json().get("error", {})
        except (ValueError, AttributeError):
            body = {}
        body = body if isinstance(body, dict) else {}
        raise ApiError(body.get("message") or f"サーバでエラーが起きました(コード {response.status_code})。",
                       status_code=response.status_code, code=body.get("code"), details=body.get("details"))
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError as err:
        raise ApiError("サーバから想定外の応答が返りました。") from err


def _display_time(value):
    if not value:
        return None
    from logic.subscriptions import JST, parse_time
    return parse_time(value).astimezone(JST).replace(tzinfo=None).isoformat(timespec="minutes")


def _to_app_subscription(data: dict) -> dict:
    """APIのサブスク1件を、アプリ内で使う形にそろえる。"""
    return {
        "id": data.get("id"),
        "name": data.get("name", ""),
        "icon": data.get("icon"),
        "plan_name": data.get("plan_name", ""),
        "cycle": data.get("cycle", "monthly"),
        "amount": int(data.get("amount") or 0),
        "joined_at": _display_time(data.get("joined_at")),
        "join_url": data.get("join_url", ""),
        "cancel_url": data.get("cancel_url", ""),
        "cancel_memo": data.get("cancel_memo", ""),
        "status": data.get("status", "active"),
        "trial_end_at": _display_time(data.get("trial_ends_at", data.get("trial_end_at"))),
        "trial_ends_at": _display_time(data.get("trial_ends_at", data.get("trial_end_at"))),
        **{key: data.get(key) for key in ("service_id", "plan_id", "created_at", "registered_at", "next_payment_at")},
    }


def _to_api_subscription(data: dict) -> dict:
    """統合コードの旧トライアル項目名をサーバ仕様へ合わせる．"""
    payload = dict(data)
    if "trial_end_at" in payload:
        payload["trial_ends_at"] = payload.pop("trial_end_at")
    return payload


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
        _request("DELETE", ENDPOINTS["log_out"])
    _logged_in = False


# ------------------------------------------------------------------
# サブスク
# ------------------------------------------------------------------
def list_subscriptions() -> list[dict]:
    """自分のサブスク一覧を登録順で返す。"""
    if config.USE_DUMMY_DATA:
        return copy.deepcopy(_dummy_subs)
    result = _request("GET", ENDPOINTS["subscriptions"])
    result = result.get("subscriptions") if isinstance(result, dict) else result
    if not isinstance(result, list):
        raise ApiError("一覧の応答形式が想定と異なります．")
    return [_to_app_subscription(item) for item in result]


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
    data = validate_subscription(data)
    if data["status"] == "cancelled":
        raise ApiError("登録時は契約中またはトライアル中を選択してください．")
    return _to_app_subscription(_request("POST", ENDPOINTS["subscriptions"], json=registration_payload(data)))


def update_subscription(sub_id, data: dict) -> dict:
    """サブスクを編集し、更新後の1件を返す。解約・再契約は data に status を入れる。"""
    if config.USE_DUMMY_DATA:
        sub = _find_dummy(sub_id)
        sub.update({key: value for key, value in data.items() if key != "id"})
        if data.get("status") in {"active", "cancelled"}:
            sub.update(trial_end_at=None, trial_ends_at=None, next_payment_at=None)
        return copy.deepcopy(sub)
    path = ENDPOINTS["subscription"].format(sub_id=sub_id)
    return _to_app_subscription(_request("PATCH", path, json=update_payload(_to_api_subscription(data))))


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
        word = normalize_keyword(keyword or "")
        return [copy.deepcopy(s) for s in dummy_data.SERVICES if word in normalize_keyword(s["name"])]
    result = _request("GET", ENDPOINTS["services"], params={"q": keyword})
    result = result.get("services") if isinstance(result, dict) else result
    if not isinstance(result, list):
        raise ApiError("サービス検索の応答形式が想定と異なります．")
    return result


def icon_url(icon: str | None) -> str | None:
    """アイコンのURLを返す。APIが / から始まるパスを返した場合はAPIのURLを前に付ける。"""
    if not icon:
        return None
    if icon.startswith("/"):
        return config.API_BASE_URL + icon
    return icon


# 単独試作の互換API．共通画面は上記のモジュール関数を利用する．
class ApiClient:
    """asyncメソッドで画面を止めずに保存や通信を行う．"""

    def __init__(self, data_file=None, use_dummy=None, base_url=None, http_session=None):
        self.data_file = Path(data_file or Path(__file__).resolve().parents[1] / "data" / "subscriptions.json")
        self.use_dummy = config.USE_DUMMY_DATA if use_dummy is None else use_dummy
        self.base_url = config.API_BASE_URL if base_url is None else base_url
        self._http_session = http_session
        self._owns_session = http_session is None
        self._lock = RLock()

    def http_session(self):
        """ログイン担当と共有するCookie保持用のHTTPセッションを返す．"""
        if not self.base_url:
            raise ApiError("APIのURLが未設定です．")
        if self._http_session is None or self._http_session.is_closed:
            self._http_session = httpx.AsyncClient(base_url=self.base_url.rstrip("/") + "/", timeout=15)
            self._owns_session = True
        return self._http_session

    async def aclose(self):
        """このクライアントが所有する通信セッションを終了する．"""
        if self._owns_session and self._http_session is not None:
            await self._http_session.aclose()

    async def _request(self, method, path, **kwargs):
        """APIエラーと不正なJSONを利用者向けのエラーに変換する．"""
        if not self.base_url:
            raise ApiError("APIのURLが未設定です．")
        try:
            response = await self.http_session().request(method, path, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else None
        except httpx.HTTPStatusError as error:
            message = "ログイン状態を確認してください．" if error.response.status_code in (401, 403) else "保存・取得に失敗しました．時間をおいて再試行してください．"
            try:
                body = error.response.json().get("error", {})
            except (ValueError, AttributeError):
                body = {}
            if not isinstance(body, dict):
                body = {}
            raise ApiError(body.get("message") or message,
                           status_code=error.response.status_code,
                           code=body.get("code"), details=body.get("details")) from error
        except httpx.HTTPError as error:
            raise OfflineError("通信できません．接続後に再試行してください．送信の自動再試行は行いません．") from error
        except ValueError as error:
            raise ApiError("通信できませんでした．接続先とネットワークを確認してください．") from error

    def _read(self):
        """壊れたファイルを空データで上書きせず，エラーとして扱う．"""
        if not self.data_file.exists():
            return []
        try:
            values = json.loads(self.data_file.read_text(encoding="utf-8"))
            if not isinstance(values, list) or any(not isinstance(value, dict) or "id" not in value for value in values):
                raise ValueError("Invalid records")
            return values
        except (OSError, ValueError) as error:
            raise ApiError("保存データを読み取れません．JSONファイルを確認してください．") from error

    def _write(self, items):
        """一時ファイルから置換し，途中で保存が失敗しても元データを残す．"""
        temporary = None
        try:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.data_file.parent, delete=False) as output:
                temporary = output.name
                json.dump(items, output, ensure_ascii=False, indent=2)
            os.replace(temporary, self.data_file)
        except OSError as error:
            raise ApiError("保存できません．フォルダの書き込み権限を確認してください．") from error
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def _local(self, operation, sub_id=None, data=None):
        """単一プロセス内の読み書きをロックして処理する．"""
        with self._lock:
            items = self._read()
            if operation == "list":
                return copy.deepcopy(items)
            if operation == "create":
                item = {**data, "id": uuid4().hex,
                        "registered_at": datetime.now().astimezone().isoformat(), "next_payment_at": None}
                items.append(item)
            else:
                item = next((value for value in items if value["id"] == sub_id), None)
                if item is None:
                    raise ApiError("このサブスクは見つかりません．一覧を更新してください．")
                if operation == "get":
                    return copy.deepcopy(item)
                validated = validate_subscription({**item, **data})
                item.update(validated)
                if data.get("status") in {"active", "cancelled"}:
                    item["next_payment_at"] = None
                    item["trial_ends_at"] = ""
                for key in ("next_payment_at",):
                    if key in data:
                        item[key] = data[key]
            self._write(items)
            return copy.deepcopy(item)

    async def search_services(self, keyword=""):
        """定番サービスを検索する．ローカルの結果はコピーして返す．"""
        if not self.use_dummy:
            result = await self._request("GET", "services", params={"q": keyword})
            result = result.get("services") if isinstance(result, dict) else result
            if not isinstance(result, list) or any(not isinstance(item, dict) for item in result):
                raise ApiError("サービス検索の応答形式が想定と異なります．")
            return result
        query = normalize_keyword(keyword)
        return copy.deepcopy([service for service in SERVICES if query in normalize_keyword(
            " ".join([service["name"], *service.get("aliases", [])]))])

    async def list_subscriptions(self):
        """登録済みの一覧を返す．"""
        if self.use_dummy:
            return await asyncio.to_thread(self._local, "list")
        result = await self._request("GET", "subscriptions")
        result = result.get("subscriptions") if isinstance(result, dict) else result
        if not isinstance(result, list) or any(not isinstance(item, dict) for item in result):
            raise ApiError("一覧の応答形式が想定と異なります．")
        return result

    async def get_subscription(self, sub_id):
        """一件のサブスクを返す．"""
        if self.use_dummy:
            return await asyncio.to_thread(self._local, "get", sub_id)
        return await self._request("GET", "subscriptions/" + quote(str(sub_id), safe=""))

    async def create_subscription(self, data):
        """検証済みのサブスクを作成する．"""
        data = validate_subscription(data)
        if self.use_dummy:
            return await asyncio.to_thread(self._local, "create", data=data)
        if data["status"] == "cancelled":
            raise ApiError("登録時は契約中またはトライアル中を選択してください．解約は詳細画面で記録します．")
        try:
            payload = registration_payload(data)
        except (ValueError, TypeError) as error:
            raise ApiError("サービスまたはプランのIDが不正です．定番サービスを再選択してください．") from error
        return await self._request("POST", "subscriptions", json=payload)

    async def update_subscription(self, sub_id, data):
        """登録済みサブスクを部分更新する．"""
        if self.use_dummy:
            return await asyncio.to_thread(self._local, "update", sub_id, data)
        return await self._request("PATCH", "subscriptions/" + quote(str(sub_id), safe=""), json=update_payload(data))
