"""仮API契約を一か所にまとめ，ローカルJSON保存と切り替える．"""
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
from logic.subscriptions import normalize_keyword, validate_subscription


class ApiError(RuntimeError):
    """画面に表示できる保存・通信エラー．"""


class ApiClient:
    """asyncメソッドで画面を止めずに保存や通信を行う．"""

    def __init__(self, data_file=None, use_dummy=None, base_url=None, http_session=None):
        self.data_file = Path(data_file or config.DATA_FILE)
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
            self._http_session = httpx.AsyncClient(base_url=self.base_url + "/", timeout=15)
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
            return response.json()
        except httpx.HTTPStatusError as error:
            message = "ログイン状態を確認してください．" if error.response.status_code in (401, 403) else "保存・取得に失敗しました．時間をおいて再試行してください．"
            raise ApiError(message) from error
        except (httpx.HTTPError, ValueError) as error:
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
                for key in ("next_payment_at",):
                    if key in data:
                        item[key] = data[key]
            self._write(items)
            return copy.deepcopy(item)

    async def search_services(self, keyword=""):
        """定番サービスを検索する．ローカルの結果はコピーして返す．"""
        if not self.use_dummy:
            result = await self._request("GET", "services", params={"q": keyword})
            if not isinstance(result, list):
                raise ApiError("サービス検索の応答形式が想定と異なります．")
            return result
        query = normalize_keyword(keyword)
        return copy.deepcopy([service for service in SERVICES if query in normalize_keyword(
            " ".join([service["name"], *service["aliases"]]))])

    async def list_subscriptions(self):
        """登録済みの一覧を返す．"""
        if self.use_dummy:
            return await asyncio.to_thread(self._local, "list")
        result = await self._request("GET", "subscriptions")
        if not isinstance(result, list):
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
        return await self._request("POST", "subscriptions", json=data)

    async def update_subscription(self, sub_id, data):
        """登録済みサブスクを部分更新する．"""
        if self.use_dummy:
            return await asyncio.to_thread(self._local, "update", sub_id, data)
        return await self._request("PATCH", "subscriptions/" + quote(str(sub_id), safe=""), json=data)
