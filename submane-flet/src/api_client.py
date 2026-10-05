"""アプリ側のデータ取得・登録と，APIの項目名変換をまとめる．"""

from copy import deepcopy
import re
import secrets
from urllib.parse import quote

import httpx

import config
from auth_validation import normalize_email, validate_credentials
from dummy_data import (DummyAuthStore, DummyStore, DuplicateAccountError,
                        InvalidCredentialsError)
from validation import validate_subscription


class ApiError(RuntimeError):
    """通信・設定・レスポンス形式のエラーを画面へ伝える．"""

    def __init__(self, message: str, *, status_code: int | None = None):
        """画面が認証失敗などを区別できるようにHTTPステータスも保持する．"""
        super().__init__(message)
        self.status_code = status_code


def normalize_user(data: dict) -> dict[str, str]:
    """トークンやサーバの内部情報を画面へ渡さず，IDとメールだけを返す．"""
    if not isinstance(data, dict):
        raise ApiError("APIのアカウント返却形式を確認してください．")
    user_id = data.get("id")
    if isinstance(user_id, bool) or not isinstance(user_id, (str, int)) or not str(user_id).strip():
        raise ApiError("APIのアカウント情報にIDがありません．")
    try:
        email = normalize_email(data.get("email"))
    except ValueError as exc:
        raise ApiError("APIのアカウント情報に有効なメールアドレスがありません．") from exc
    return {"id": str(user_id), "email": email}


def normalize_subscription(data: dict) -> dict:
    """APIの項目名を画面用のsnake_caseにそろえる．"""
    if not isinstance(data, dict):
        raise ApiError("APIから受け取った登録情報の形式を確認してください．")
    result = dict(data)
    # 正式APIの項目名が決まったら，この変換表だけを修正します．
    aliases = {
        "planName": "plan_name", "joinedAt": "joined_at",
        "signupUrl": "join_url", "cancelUrl": "cancel_url",
        "cancelNote": "cancel_memo", "trialEndsAt": "trial_ends_at",
        "nextPaymentAt": "next_payment_at", "serviceId": "service_id",
    }
    for source, target in aliases.items():
        if target not in result and source in result:
            result[target] = result[source]
    if result.get("id") is None or not result.get("name"):
        raise ApiError("APIから受け取った登録情報にIDまたは名称がありません．")
    result["id"] = str(result["id"])
    for key in ("icon", "join_url", "cancel_url", "cancel_memo", "plan_name"):
        result.setdefault(key, "")
    result.setdefault("status", "active")
    result.setdefault("next_payment_at", None)
    return result


class ApiClient:
    """各アプリセッションで共有する，非同期のAPIクライアント．"""

    def __init__(self, *, use_dummy=None, base_url=None, access_token=None,
                 transport=None):
        """接続設定と，独立した試用ストアを用意する．"""
        self.use_dummy = config.USE_DUMMY_DATA if use_dummy is None else use_dummy
        self.base_url = (config.API_BASE_URL if base_url is None else base_url).rstrip("/")
        self.access_token = access_token or ""
        self.current_user: dict[str, str] | None = None
        self._session_revision = 0
        self.transport = transport
        self.dummy = DummyStore()
        self.dummy_auth = DummyAuthStore()

    @property
    def is_authenticated(self) -> bool:
        """ログイン応答を検証して取得したユーザとトークンがそろっている．"""
        return bool(self.access_token and self.current_user)

    def clear_session(self):
        """トークンとユーザを破棄し，進行中のログイン応答も無効にする．"""
        self._session_revision += 1
        self.access_token = ""
        self.current_user = None

    def _require_login(self):
        """登録情報の操作を，ログインしている場合に限定する．"""
        if not self.access_token or (self.use_dummy and not self.current_user):
            raise ApiError("ログインしてから利用してください．", status_code=401)

    def _dummy_user_store(self) -> DummyStore:
        """現在ログインしているユーザのストアだけを使う．"""
        self._require_login()
        try:
            return self.dummy_auth.store_for(self.current_user["id"])
        except KeyError as exc:
            self.clear_session()
            raise ApiError("もう一度ログインしてください．", status_code=401) from exc

    async def _request(self, method: str, path: str, *, auth_token=None, **kwargs):
        """正式APIに合わせて変更する通信処理．秘密情報を出力しない．"""
        if not self.base_url.startswith("https://"):
            raise ApiError("APIのHTTPS URLを設定してください．")
        headers = {}
        token = self.access_token if auth_token is None else auth_token
        revision = self._session_revision
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url + "/", headers=headers,
                timeout=config.API_TIMEOUT_SECONDS, transport=self.transport,
            ) as client:
                response = await client.request(method, path.lstrip("/"), **kwargs)
                response.raise_for_status()
                if response.status_code == 204:
                    return None
                return response.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 401:
                if token and token == self.access_token and revision == self._session_revision:
                    self.clear_session()
                raise ApiError("ログイン状態を確認してください．", status_code=status) from exc
            if status == 429:
                raise ApiError("試行回数が多いため，時間をおいてお試しください．",
                               status_code=status) from exc
            raise ApiError("処理に失敗しました．時間をおいてお試しください．",
                           status_code=status) from exc
        except httpx.RequestError as exc:
            raise ApiError("通信できませんでした．ネットワークを確認してください．") from exc
        except ValueError as exc:
            raise ApiError("APIの返却データがJSON形式になっていません．") from exc

    async def sign_up(self, email: str, password: str) -> dict[str, str]:
        """会員登録する．登録だけではログイン済みにしない．"""
        clean = validate_credentials(email, password, is_sign_up=True)
        if self.use_dummy:
            try:
                return await self.dummy_auth.sign_up(**clean)
            except DuplicateAccountError as exc:
                raise ApiError("このメールアドレスは登録済みです．ログインしてください．",
                               status_code=409) from exc
        try:
            response = await self._request("POST", "auth/signup", auth_token="", json=clean)
        except ApiError as exc:
            if exc.status_code == 409:
                raise ApiError("このメールアドレスは登録済みです．ログインしてください．",
                               status_code=409) from exc
            if exc.status_code in {400, 422}:
                raise ApiError("登録内容を確認してください．", status_code=exc.status_code) from exc
            raise
        return normalize_user(response.get("user") if isinstance(response, dict) else None)

    async def log_in(self, email: str, password: str) -> dict[str, str]:
        """正しい認証応答を受け取った場合だけログイン状態を更新する．"""
        clean = validate_credentials(email, password)
        self.clear_session()
        revision = self._session_revision
        if self.use_dummy:
            try:
                user = await self.dummy_auth.log_in(**clean)
            except InvalidCredentialsError as exc:
                raise ApiError("メールアドレスまたはパスワードが違います．",
                               status_code=401) from exc
            token = secrets.token_urlsafe(32)
        else:
            try:
                response = await self._request("POST", "auth/login", auth_token="", json=clean)
            except ApiError as exc:
                if exc.status_code in {400, 401, 403, 422}:
                    raise ApiError("メールアドレスまたはパスワードを確認してください．",
                                   status_code=exc.status_code) from exc
                raise
            if not isinstance(response, dict):
                raise ApiError("APIのログイン返却形式を確認してください．")
            token = response.get("access_token")
            token_type = response.get("token_type", "bearer")
            if (not isinstance(token, str) or not token or len(token) > 8192
                    or not re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", token)
                    or not isinstance(token_type, str) or token_type.casefold() != "bearer"):
                raise ApiError("APIのログイン応答に有効なBearerトークンがありません．")
            user = normalize_user(response.get("user"))
        if revision != self._session_revision:
            raise ApiError("ログイン処理が中断されました．再度お試しください．")
        self.access_token = token
        self.current_user = user
        return deepcopy(user)

    async def log_out(self):
        """端末内の認証を直ちに破棄し，API版ではサーバへも通知する．"""
        token = self.access_token
        self.clear_session()
        if not self.use_dummy and token:
            # ログアウトの対象を，開始時のトークンに固定します．
            try:
                await self._request("POST", "auth/logout", auth_token=token)
            except ApiError as exc:
                if exc.status_code != 401:
                    raise

    async def list_subscriptions(self) -> list[dict]:
        """自分の登録一覧を取得する．ダミーか本物かは画面から隠す．"""
        self._require_login()
        result = self._dummy_user_store().list_subscriptions() if self.use_dummy else await self._request(
            "GET", "subscriptions"
        )
        if not isinstance(result, list):
            raise ApiError("APIの一覧データは配列で返してください．")
        return [normalize_subscription(sub) for sub in result]

    async def get_subscription(self, sub_id: str) -> dict:
        """詳細画面向けに1件取得する．"""
        self._require_login()
        if self.use_dummy:
            try:
                result = self._dummy_user_store().get_subscription(sub_id)
            except KeyError as exc:
                raise ApiError("登録情報が見つかりませんでした．") from exc
        else:
            result = await self._request("GET", f"subscriptions/{quote(str(sub_id), safe='')}")
        return normalize_subscription(result)

    async def create_subscription(self, data: dict) -> dict:
        """入力を検証して登録する．通信失敗時はダミーへ切り替えない．"""
        self._require_login()
        clean = validate_subscription(data)
        result = self._dummy_user_store().create_subscription(clean) if self.use_dummy else await self._request(
            "POST", "subscriptions", json=clean
        )
        return normalize_subscription(result)

    async def search_services(self, keyword: str) -> list[dict]:
        """定番サービスを名称で検索する．"""
        result = self.dummy.search_services(keyword) if self.use_dummy else await self._request(
            "GET", "services", params={"keyword": keyword}
        )
        if not isinstance(result, list) or any(
            not isinstance(service, dict) or not service.get("name") for service in result
        ):
            raise ApiError("サービス検索の返却形式を確認してください．")
        return result
