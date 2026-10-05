# 石井ブランチ・統合後の全コード

2026-10-05更新．コードを省略せず掲載しています．

## pyproject.toml

```toml
[project]
name = "submane"
version = "0.1.0"
description = "サブスクリプション管理アプリ「サブマネ」"
readme = "README.md"
requires-python = ">=3.12"
# アプリ(APK)に入るライブラリ。バージョンは全員そろえる。上げるときは全員で同時に。
dependencies = [
    "flet==1.0.3",
    "flet-charts==1.0.3",   # 内訳画面の円グラフ
    "httpx==0.28.1",        # APIの呼び出し
]

[dependency-groups]
dev = [
    "flet-cli==1.0.3",
    "flet-desktop==1.0.3",
    "flet-web==1.0.3",
    "pytest",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.flet]
org = "jp.e1"                 # 仮。パッケージ名の先頭になる
product = "サブマネ"
company = "Team E1"

[tool.flet.app]
path = "src"
```

## .gitignore

```text
.venv/
__pycache__/
build/
.pytest_cache/
*.pyc
data/
.reference/
*.log
```

## ../.gitignore

```text
# macOS
.DS_Store

# Python
__pycache__/
*.pyc
.venv/

# Flet / Flutter build output
build/

# Editor
.vscode/
.idea/

# ローカル作業・テスト生成物
.pytest_cache/
.reference/
.tools/
data/
*.log
```

## run.ps1

```powershell
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& "$PSScriptRoot/.venv/Scripts/python.exe" "$PSScriptRoot/src/main.py" @args
```

## setup.ps1

```powershell
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12をインストールするか，既存の.venvを利用してください．' }
& "$PSScriptRoot/.venv/Scripts/python.exe" -m pip install 'flet[all]==1.0.3' 'httpx==0.28.1' 'flet-charts==1.0.3' 'pytest==9.1.1'
if ($LASTEXITCODE -ne 0) { throw '依存ライブラリのインストールに失敗しました．' }
```

## src/api_client.py

```python
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
```

## src/components/__init__.py

```python
"""チームの画面で再利用する石井担当部品．"""
```

## src/components/app_header.py

```python
"""ヘッダー。タブ画面ではアプリ名、それ以外の画面では戻るボタンと画面名を出す。"""

import flet as ft

import navigation
import theme


def app_header(page: ft.Page, title: str | None = None, show_back: bool = False, show_actions: bool = True) -> ft.Control:
    """ヘッダーを返す(main.py が全画面に付ける)。

    title        : 画面名。None ならアプリ名「サブマネ」を出す
    show_back    : 戻るボタンを出すか
    show_actions : 右側の「追加」とアカウントボタンを出すか
    """
    left = []
    if show_back:
        left.append(
            ft.IconButton(
                icon=ft.Icons.ARROW_BACK,
                icon_color=theme.INK,
                tooltip="戻る",
                width=theme.TAP_MIN,
                height=theme.TAP_MIN,
                on_click=lambda e: navigation.go_back(page),
            )
        )
    if title:
        left.append(theme.text(title, size=18, weight="bold"))
    else:
        left.append(theme.text("サブマネ", size=22, weight="black"))

    right = []
    if show_actions:
        right = [
            ft.FilledButton(
                content="追加",
                icon=ft.Icons.ADD,
                height=theme.TAP_MIN,
                bgcolor=theme.ACCENT,
                color=theme.ON_ACCENT,
                icon_color=theme.ON_ACCENT,
                style=ft.ButtonStyle(
                    text_style=ft.TextStyle(font_family=theme.FONT_BOLD, size=14),
                    padding=ft.Padding.only(left=12, right=16),
                ),
                on_click=lambda e: navigation.go(page, navigation.REGISTER),
            ),
            ft.Container(
                width=theme.TAP_MIN,
                height=theme.TAP_MIN,
                border_radius=theme.TAP_MIN / 2,
                bgcolor=theme.SURFACE,
                border=ft.Border.all(1, theme.LINE),
                alignment=ft.Alignment.CENTER,
                tooltip="アカウント",
                content=ft.Icon(ft.Icons.PERSON_OUTLINE, size=22, color=theme.INK),
                on_click=lambda e: navigation.go(page, navigation.ACCOUNT),
            ),
        ]

    return ft.Container(
        padding=ft.Padding.only(left=8 if show_back else theme.GUTTER, right=theme.GUTTER, top=12),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(controls=left, spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row(controls=right, spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ],
        ),
    )
```

## src/components/feedback.py

```python
"""データが0件のとき、通信に失敗したときなどの案内表示。"""

import flet as ft

import navigation
import theme


def primary_button(label: str, on_click, icon=None) -> ft.Control:
    """主要な操作のボタン(緑の塗り)。"""
    return ft.FilledButton(
        content=label,
        icon=icon,
        height=theme.TAP_MIN,
        bgcolor=theme.ACCENT,
        color=theme.ON_ACCENT,
        icon_color=theme.ON_ACCENT,
        style=ft.ButtonStyle(text_style=ft.TextStyle(font_family=theme.FONT_BOLD, size=14)),
        on_click=on_click,
    )


def message_panel(message: str, icon=None, button_label: str | None = None, on_click=None, color: str = theme.INK_SUB) -> ft.Control:
    """中央寄せの案内文(+ ボタン)を返す。"""
    controls = []
    if icon:
        controls.append(ft.Icon(icon, size=40, color=color))
    controls.append(theme.text(message, size=14, color=theme.INK_SUB, text_align=ft.TextAlign.CENTER))
    if button_label and on_click:
        controls.append(primary_button(button_label, on_click))
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=theme.GUTTER, vertical=48),
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            controls=controls,
            spacing=20,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def error_panel(page: ft.Page, message: str) -> ft.Control:
    """通信エラーなどの案内と「もう一度読み込む」ボタンを返す。"""
    return message_panel(
        message,
        icon=ft.Icons.ERROR_OUTLINE,
        button_label="もう一度読み込む",
        on_click=lambda e: navigation.reload(page),
        color=theme.DANGER,
    )
```

## src/components/service_icon.py

```python
"""サービスのアイコン。状態(無料トライアル中 / 解約済み)の見た目もここでそろえる。

アイコンを表示する画面は必ずこの部品を使う:
    from components.service_icon import service_icon
    service_icon(sub)             # ホームと同じ72px
    service_icon(sub, size=44)    # 一覧の行など小さく出すとき
"""

from zlib import crc32
import flet as ft

import api_client
import theme

BADGE_SIZE = 30      # トライアルの時計バッジ(外周の縁取りを含む)
BADGE_OVERHANG = 8   # バッジがタイルからはみ出す量


def footprint(size: float = 72) -> tuple[float, float]:
    """service_icon が占める (幅, 高さ) を返す。バッジのはみ出し分を含む。"""
    return size + BADGE_OVERHANG * 2, size + BADGE_OVERHANG


def service_icon(sub: dict, size: float = 72, color_index: int | None = None, ring_color: str = theme.GROUND) -> ft.Control:
    """サブスク1件のアイコンを返す。

    sub         : サブスク1件(name / icon / status を使う)
    size        : タイルの一辺(px)
    color_index : アイコン画像がないときのタイル色の番号(theme.TILE_COLORS)
    ring_color  : バッジの縁取り色。アイコンを置く場所の背景色に合わせる
    """
    if color_index is None:
        identity = str(sub.get("service_id") or sub.get("id") or sub.get("name") or "?")
        color_index = crc32(identity.encode("utf-8"))
    cancelled = sub.get("status") == "cancelled"
    trial = sub.get("status") == "trial"
    radius = round(size * 0.28)
    name = sub.get("name") or "?"

    # 画像がない(または読み込めない)ときは、頭文字のタイルを出す
    monogram = ft.Container(
        width=size,
        height=size,
        border_radius=radius,
        bgcolor=theme.OFF_FILL if cancelled else theme.tile_color(color_index),
        alignment=ft.Alignment.CENTER,
        content=theme.text(
            name[0],
            size=round(size * 0.42),
            weight="black",
            color=theme.OFF_INK if cancelled else theme.ON_ACCENT,
        ),
    )

    url = api_client.icon_url(sub.get("icon"))
    if url:
        image = ft.Image(src=url, width=size, height=size, fit=ft.BoxFit.COVER, error_content=monogram)
        if cancelled:  # 解約済みは白黒にして薄くする
            image.color = theme.OFF_FILL
            image.color_blend_mode = ft.BlendMode.SATURATION
            image.opacity = 0.55
        tile = ft.Container(
            width=size,
            height=size,
            border_radius=radius,
            bgcolor=theme.OFF_FILL if cancelled else theme.SURFACE,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=image,
        )
    else:
        tile = monogram

    tile.left = BADGE_OVERHANG
    tile.top = BADGE_OVERHANG
    controls = [tile]

    if trial:
        scale = min(1.0, size / 72)
        badge = round(BADGE_SIZE * max(scale, 0.7))
        controls.append(
            ft.Container(
                width=badge,
                height=badge,
                right=0,
                top=0,
                border_radius=badge / 2,
                bgcolor=theme.TRIAL,
                border=ft.Border.all(3, ring_color),
                alignment=ft.Alignment.CENTER,
                content=ft.Icon(ft.Icons.ACCESS_TIME, size=round(badge * 0.5), color=theme.ON_ACCENT),
            )
        )

    width, height = footprint(size)
    return ft.Stack(width=width, height=height, controls=controls)


def status_label(sub: dict) -> str:
    """状態を表す短い文言を返す(読み上げや補足表示用)。契約中は空文字。"""
    return {"trial": "無料トライアル中", "cancelled": "解約済み"}.get(sub.get("status"), "")
```

## src/components/status_actions.py

```python
"""詳細画面に組み込む解約・再契約の状態変更部品．"""
from datetime import datetime
import inspect
import flet as ft
import theme
from api_client import ApiError
from logic.api_bridge import call_api
from logic.subscriptions import JST, ValidationError, cancellation_patch, reactivation_patch, valid_url


def status_actions(page, subscription, api, on_changed):
    """公式サイトを開く操作と，手続き後の記録を別の操作として提供する．"""
    cancelled = subscription.get("status") == "cancelled"
    url = subscription.get("join_url" if cancelled else "cancel_url", "")
    label = "入会サイトを開く" if cancelled else "退会サイトを開く"
    error_text = ft.Text("", color=theme.ERROR)
    new_joined = ft.TextField(label="再契約の入会日時（日本時間）",
                             value=datetime.now(JST).strftime("%Y-%m-%dT%H:%M"),
                             visible=cancelled)
    confirm = ft.Checkbox(label="公式サイトで手続きを完了しました", value=False)
    busy = {"value": False, "completed": False}

    async def change_status(event):
        """手続き完了確認後に保存し，成功した場合だけ一覧を更新する．"""
        if busy["value"] or busy["completed"]:
            return
        if not confirm.value:
            error_text.value = "公式サイトでの手続き完了を確認してください．"
            page.update()
            return
        new_joined.error = None
        try:
            patch = reactivation_patch(subscription, new_joined.value) if cancelled else cancellation_patch()
        except ValidationError as error:
            new_joined.error = error.errors.get("joined_at")
            page.update()
            return
        busy["value"] = True
        save.disabled = True
        new_joined.disabled = True
        confirm.disabled = True
        error_text.value = ""
        page.update()
        try:
            item = await call_api(api, "update_subscription", subscription["id"], patch)
        except ApiError as error:
            error_text.value = str(error)
        else:
            busy["completed"] = True
            result = on_changed(item)
            if inspect.isawaitable(result):
                await result
        finally:
            busy["value"] = False
            save.disabled = busy["completed"]
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
```

## src/components/tab_bar.py

```python
"""下部タブ(ホーム / 内訳 / 期限)。"""

import flet as ft

import navigation
import theme

TABS = [
    (navigation.HOME, "ホーム", ft.Icons.GRID_VIEW_ROUNDED),
    (navigation.BREAKDOWN, "内訳", ft.Icons.PIE_CHART_OUTLINE),
    (navigation.DEADLINE, "期限", ft.Icons.EVENT_OUTLINED),
]


def _tab(page: ft.Page, route: str, label: str, icon, selected: bool) -> ft.Control:
    """タブ1つ分を返す。"""
    color = theme.ACCENT if selected else theme.INK_SUB
    return ft.Container(
        expand=True,
        height=56,
        on_click=lambda e: navigation.go(page, route),
        content=ft.Column(
            spacing=2,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=56,
                    height=30,
                    border_radius=15,
                    bgcolor=theme.ACCENT_SOFT if selected else None,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icon, size=20, color=color),
                ),
                theme.text(label, size=11, weight="bold" if selected else "regular", color=color),
            ],
        ),
    )


def tab_bar(page: ft.Page, current_route: str | None) -> ft.Control:
    """下部タブを返す(main.py が全画面に付ける)。current_route のタブを選択中にする。"""
    return ft.Container(
        bgcolor=theme.SURFACE,
        border=ft.Border.only(top=ft.BorderSide(1, theme.LINE)),
        padding=ft.Padding.only(left=theme.GUTTER, right=theme.GUTTER, top=8, bottom=8),
        content=ft.Row(
            spacing=8,
            controls=[_tab(page, route, label, icon, route == current_route) for route, label, icon in TABS],
        ),
    )
```

## src/config.py

```python
"""アプリ全体の設定。APIのURLなどはここだけで管理する。"""

# True の間はAPIを呼ばず、dummy_data.py の内容で動く
import os

USE_DUMMY_DATA = os.getenv("SUBMANE_USE_DUMMY_DATA", "true").lower() == "true"

# APIができたら設定する(末尾の / は付けない)
API_BASE_URL = os.getenv("SUBMANE_API_BASE_URL", "https://<APIのURL>").rstrip("/")

# APIの応答を待つ秒数
REQUEST_TIMEOUT = 10.0

# ダミーデータで動かすとき、最初からログイン済みとして扱うか
# (False にすると起動時に会員登録・ログイン画面が出る)
DUMMY_START_LOGGED_IN = True
```

## src/dummy_data.py

```python
"""APIができるまで使うダミーデータ。

金額・日時・URLはすべて動作確認用の仮の値で、実際のサービスの料金やURLではない。
項目は README 5章「アプリが必要とするサブスク1件のデータ」に合わせている
(+ 無料トライアルの終了日時 trial_end_at)。
"""


def _sub(sub_id, name, cycle, amount, joined_at, status="active", trial_end_at=None, plan_name=None):
    """ダミーのサブスク1件を作る。"""
    slug = f"service-{sub_id}"
    return {
        "id": sub_id,
        "name": name,
        "icon": None,  # APIからアイコンURLを受け取るまでは頭文字のタイルを表示
        "plan_name": plan_name or ("月額プラン" if cycle == "monthly" else "年額プラン"),
        "cycle": cycle,
        "amount": amount,
        "joined_at": joined_at,
        "join_url": f"https://example.com/{slug}/join",
        "cancel_url": f"https://example.com/{slug}/cancel",
        "cancel_memo": "退会手続きにはログイン用のメールアドレスとパスワードの準備が必要です。",
        "status": status,
        "trial_end_at": trial_end_at,
    }


SUBSCRIPTIONS = [
    _sub(1, "Netflix", "monthly", 1500, "2025-04-12T20:15"),
    _sub(2, "Spotify", "monthly", 1000, "2024-11-03T08:40"),
    _sub(3, "Audible", "monthly", 1500, "2025-01-20T22:05", status="cancelled"),
    _sub(4, "U-NEXT", "monthly", 2200, "2026-09-20T21:00", status="trial", trial_end_at="2026-10-20T21:00"),
    _sub(5, "Amazonプライム", "yearly", 6000, "2023-10-18T12:30"),
    _sub(6, "YouTube Premium", "monthly", 1300, "2025-07-01T19:00"),
    _sub(7, "Disney+", "monthly", 1100, "2025-12-24T10:00"),
    _sub(8, "FODプレミアム", "monthly", 1000, "2025-03-08T23:10", status="cancelled"),
    _sub(9, "DAZN", "monthly", 4200, "2026-02-14T18:45"),
    _sub(10, "Apple Music", "monthly", 1100, "2024-06-30T09:20"),
    _sub(11, "Adobe CC", "yearly", 86000, "2025-11-05T14:00"),
    _sub(12, "Hulu", "monthly", 1000, "2026-01-31T21:30"),
    _sub(13, "Kindle Unlimited", "monthly", 1000, "2026-09-28T07:50", status="trial", trial_end_at="2026-10-28T07:50"),
    _sub(14, "Lemino", "monthly", 1000, "2025-05-17T16:25", status="cancelled"),
    _sub(15, "ABEMAプレミアム", "monthly", 1100, "2026-03-22T22:00"),
    _sub(16, "iCloud+", "monthly", 400, "2023-08-09T11:11", plan_name="200GB"),
    _sub(17, "dアニメストア", "monthly", 600, "2026-04-06T00:30"),
    _sub(18, "NHKオンデマンド", "monthly", 1000, "2025-08-15T13:00", status="cancelled"),
]

# 定番サービスのマスタ(名称検索用)。
# 既存のダミー契約から作る分(1件プラン)に加え、料金プランが複数ある例として
# 石井担当が作成したデモサービス(複数プランの選択UI確認用)もそのまま載せている。
SERVICES = [
    {
        "id": sub["id"],
        "name": sub["name"],
        "icon": None,
        "join_url": sub["join_url"],
        "cancel_url": sub["cancel_url"],
        "cancel_memo": sub["cancel_memo"],
        "plans": [{"name": sub["plan_name"], "cycle": sub["cycle"], "amount": sub["amount"]}],
    }
    for sub in SUBSCRIPTIONS
] + [
    {"id": "video-demo", "name": "動画サービス（デモ）",
     "join_url": "https://example.com/video/join", "cancel_url": "https://example.com/video/cancel",
     "cancel_memo": "退会手続きにはメールアドレスとパスワードの準備が必要です．",
     "plans": [{"name": "月額プラン（デモ）", "cycle": "monthly", "amount": 1000},
               {"name": "年額プラン（デモ）", "cycle": "yearly", "amount": 10000}]},
    {"id": "music-demo", "name": "音楽サービス（デモ）",
     "join_url": "https://example.com/music/join", "cancel_url": "https://example.com/music/cancel",
     "cancel_memo": "契約した窓口を確認してください．",
     "plans": [{"name": "個人プラン（デモ）", "cycle": "monthly", "amount": 800}]},
    {"id": "book-demo", "name": "読書サービス（デモ）",
     "join_url": "https://example.com/book/join", "cancel_url": "https://example.com/book/cancel",
     "cancel_memo": "パスワードの準備が必要です．",
     "plans": [{"name": "月額プラン（デモ）", "cycle": "monthly", "amount": 500}]},
]
```

## src/logic/__init__.py

```python
"""石井担当の入力検証，並び替え，状態変更．"""
```

## src/logic/api_bridge.py

```python
"""共通の同期APIと担当画面のasyncイベントを接続する．"""
import asyncio
import inspect


async def call_api(api, method, *args):
    function = getattr(api, method)
    if inspect.iscoroutinefunction(function):
        return await function(*args)
    return await asyncio.to_thread(function, *args)
```

## src/logic/api_contract.py

```python
"""サーバ設計書v0.2の登録・状態変更リクエストへの変換．"""
from logic.subscriptions import parse_time


def registration_payload(data):
    """画面表示用の項目とAPIが計算する項目を送信しない．"""
    result = {key: data[key] for key in ("plan_name", "amount", "cycle")}
    result["joined_at"] = parse_time(data["joined_at"]).isoformat(timespec="minutes")
    if data.get("service_id"):
        result["service_id"] = int(data["service_id"])
        if data.get("plan_id"):
            result["plan_id"] = int(data["plan_id"])
    else:
        result.update({"custom_name": data["name"],
                       "custom_join_url": data.get("join_url") or None,
                       "custom_cancel_url": data.get("cancel_url") or None,
                       "custom_cancel_memo": data.get("cancel_memo") or None})
    if data.get("status") == "trial":
        result["trial_ends_at"] = parse_time(data["trial_ends_at"]).isoformat(timespec="minutes")
    return result


def update_payload(data):
    """状態変更時もnext_payment_atなどの読み取り専用値を除外する．"""
    allowed = {"service_id", "plan_id", "custom_name", "custom_join_url", "custom_cancel_url",
               "custom_cancel_memo", "plan_name", "amount", "cycle", "joined_at",
               "trial_ends_at", "memo", "status"}
    result = {key: value for key, value in data.items() if key in allowed}
    for key in ("joined_at", "trial_ends_at"):
        if result.get(key):
            result[key] = parse_time(result[key]).isoformat(timespec="minutes")
    return result
```

## src/logic/dates.py

```python
"""次回更新日(次回支払日)の計算。README 7章のルールをここ1か所にまとめる。

支払日の考え方:
  ・起点は入会日時。無料トライアルの終了日時があればそちらを起点にする
    (トライアル中の次回支払日 = トライアル終了日時)
  ・起点から「月額なら1か月ごと、年額なら12か月ごと」に支払日が来る
  ・月末のずれは、その月の末日に寄せる(1/31入会の月額 → 2/28、3/31、4/30)
  ・解約済みには支払日がない
"""

import calendar
from datetime import datetime

CYCLE_MONTHS = {"monthly": 1, "yearly": 12}


def parse_datetime(value) -> datetime | None:
    """ "2026-09-20T21:00" のような文字列を datetime にする。空なら None。"""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def add_months(base: datetime, months: int) -> datetime:
    """base の months か月後を返す。その日がない月は末日に寄せる。"""
    total = base.year * 12 + (base.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    last_day = calendar.monthrange(year, month)[1]
    return base.replace(year=year, month=month, day=min(base.day, last_day))


def cycle_months(sub: dict) -> int:
    """更新周期を月数で返す(月額=1、年額=12)。"""
    return CYCLE_MONTHS.get(sub.get("cycle"), 1)


def payment_anchor(sub: dict) -> datetime | None:
    """支払日の起点(最初の支払日)を返す。"""
    return parse_datetime(sub.get("trial_end_at")) or parse_datetime(sub.get("joined_at"))


def payment_in_month(sub: dict, year: int, month: int) -> datetime | None:
    """指定した年月に来る支払日を返す。なければ None。"""
    if sub.get("status") == "cancelled":
        return None
    anchor = payment_anchor(sub)
    if anchor is None:
        return None
    diff = (year - anchor.year) * 12 + (month - anchor.month)
    if diff < 0 or diff % cycle_months(sub) != 0:
        return None
    return add_months(anchor, diff)


def next_payment_at(sub: dict, now: datetime | None = None) -> datetime | None:
    """現在より後で最も近い支払日を返す。解約済みは None。"""
    if sub.get("status") == "cancelled":
        return None
    if sub.get("next_payment_at"):
        from logic.subscriptions import JST, parse_time
        return parse_time(sub["next_payment_at"]).astimezone(JST).replace(tzinfo=None)
    anchor = payment_anchor(sub)
    if anchor is None:
        return None
    now = now or datetime.now()
    if anchor > now:
        return anchor
    step = cycle_months(sub)
    diff = (now.year - anchor.year) * 12 + (now.month - anchor.month)
    count = diff // step
    candidate = add_months(anchor, count * step)
    while candidate <= now:
        count += 1
        candidate = add_months(anchor, count * step)
    return candidate
```

## src/logic/ordering.py

```python
"""サブスク一覧の並び替え。どの並び順でも解約済みは末尾にまとめる。"""

ORDER_FREQUENCY = "frequency"    # 更新頻度順(月額 → 年額)
ORDER_REGISTERED = "registered"  # 登録順
ORDER_LABELS = {ORDER_FREQUENCY: "更新頻度順", ORDER_REGISTERED: "登録順"}

_CYCLE_RANK = {"weekly": 0, "monthly": 1, "yearly": 2}  # 小さいほど更新頻度が高い


def sort_subscriptions(subs: list[dict], order: str = ORDER_FREQUENCY) -> list[dict]:
    """並び替えた新しいリストを返す(元のリストは変えない)。同順位は元の並びを保つ。"""

    def key(pair):
        index, sub = pair
        cancelled = 1 if sub.get("status") == "cancelled" else 0
        rank = _CYCLE_RANK.get(sub.get("cycle"), 9) if order == ORDER_FREQUENCY else 0
        return (cancelled, rank, index)

    from logic.subscriptions import sort_subscriptions as sort_registered
    return sort_registered(subs, order)


def count_by_status(subs: list[dict]) -> dict:
    """件数を数える。active は「契約中(トライアル中を含む)」。"""
    cancelled = sum(1 for sub in subs if sub.get("status") == "cancelled")
    trial = sum(1 for sub in subs if sub.get("status") == "trial")
    return {"active": len(subs) - cancelled, "trial": trial, "cancelled": cancelled}
```

## src/logic/payments.py

```python
"""支払い見込みの計算。README 7章のルールをここ1か所にまとめる。

年額プランの扱いは2通りから選べる:
  MODE_BILLING : 更新月に全額を計上する(実際に引き落とされる月)
  MODE_AVERAGE : 12で割って毎月に計上する(月あたりの負担)
"""

from logic import dates

MODE_BILLING = "billing"
MODE_AVERAGE = "average"


def amount_in_month(sub: dict, year: int, month: int, mode: str = MODE_BILLING) -> int:
    """そのサブスクが指定した年月に支払う見込み額(円)を返す。"""
    if sub.get("status") == "cancelled":
        return 0
    amount = int(sub.get("amount") or 0)
    if mode == MODE_AVERAGE and sub.get("cycle") == "yearly":
        anchor = dates.payment_anchor(sub)
        if anchor is None or (year, month) < (anchor.year, anchor.month):
            return 0
        return round(amount / 12)
    return amount if dates.payment_in_month(sub, year, month) else 0


def month_total(subs: list[dict], year: int, month: int, mode: str = MODE_BILLING) -> int:
    """指定した年月の支払い見込み総額を返す。"""
    return sum(amount_in_month(sub, year, month, mode) for sub in subs)


def previous_month(year: int, month: int) -> tuple[int, int]:
    """前月の (年, 月) を返す。"""
    return (year - 1, 12) if month == 1 else (year, month - 1)


def next_month(year: int, month: int) -> tuple[int, int]:
    """翌月の (年, 月) を返す。"""
    return (year + 1, 1) if month == 12 else (year, month + 1)


def summarize(subs: list[dict], year: int, month: int, mode: str = MODE_BILLING) -> dict:
    """内訳画面に必要な値をまとめて返す。

    戻り値:
      total          : 当月の支払い見込み総額
      previous_total : 前月の支払い見込み総額
      diff           : 当月 − 前月
      items          : 金額が多い順の [{"sub": サブスク, "amount": 金額, "ratio": 割合(0〜1)}]
    """
    items = []
    for sub in subs:
        amount = amount_in_month(sub, year, month, mode)
        if amount > 0:
            items.append({"sub": sub, "amount": amount})
    items.sort(key=lambda item: item["amount"], reverse=True)
    total = sum(item["amount"] for item in items)
    for item in items:
        item["ratio"] = item["amount"] / total if total else 0.0
    previous_total = month_total(subs, *previous_month(year, month), mode)
    return {
        "total": total,
        "previous_total": previous_total,
        "diff": total - previous_total,
        "items": items,
    }
```

## src/logic/subscriptions.py

```python
"""UIから独立した登録・解約・再契約の規則．"""
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
from urllib.parse import urlsplit
import unicodedata

STATUS_LABELS = {"active": "契約中", "trial": "無料トライアル中", "cancelled": "解約済み"}
CYCLE_LABELS = {"monthly": "月額", "yearly": "年額"}
SORT_LABELS = {"frequency": "更新頻度順", "registered": "登録順", "deadline": "期限が近い順"}


class ValidationError(ValueError):
    """入力欄ごとのエラーを保持する．"""

    def __init__(self, errors):
        self.errors = errors
        super().__init__("入力内容を確認してください．")


def normalize_keyword(value):
    """全角英数字と大文字・小文字の違いを吸収する．"""
    return unicodedata.normalize("NFKC", value).casefold().strip()


def valid_url(value):
    """HTTP(S)の絶対URLのみ受け付ける．空欄は任意項目として許可する．"""
    if not value:
        return True
    try:
        parsed = urlsplit(value)
        return (parsed.scheme in {"http", "https"} and bool(parsed.hostname)
                and not parsed.username and not parsed.password
                and not any(char.isspace() for char in value)
                and parsed.port != 0)
    except ValueError:
        return False


def parse_time(value):
    """画面とAPIで共通の分単位の日時形式を読み取る．"""
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    return parsed.replace(tzinfo=JST) if parsed.tzinfo is None else parsed


def validate_subscription(data):
    """登録内容を検証し，APIへ渡す辞書を返す．"""
    result = {key: str(data.get(key, "") or "").strip() for key in (
        "name", "plan_name", "cycle", "joined_at", "join_url", "cancel_url",
        "cancel_memo", "status", "trial_ends_at", "icon", "service_id", "plan_id",
    )}
    if not result["trial_ends_at"]:
        result["trial_ends_at"] = str(data.get("trial_end_at") or "").strip()
    errors = {}
    for key, maximum in (("name", 100), ("plan_name", 100), ("cancel_memo", 1000)):
        if key != "cancel_memo" and not result[key]:
            errors[key] = "入力してください．"
        elif len(result[key]) > maximum:
            errors[key] = f"{maximum}文字以内で入力してください．"
    amount = unicodedata.normalize("NFKC", str(data.get("amount", ""))).strip()
    if not amount or not amount.isascii() or not amount.isdecimal():
        errors["amount"] = "0以上の整数を円単位で入力してください．"
    elif int(amount) > 999999999:
        errors["amount"] = "金額が大きすぎます．"
    else:
        result["amount"] = int(amount)
    if result["cycle"] not in CYCLE_LABELS:
        errors["cycle"] = "月額または年額を選択してください．"
    if result["status"] not in STATUS_LABELS:
        errors["status"] = "契約状態を選択してください．"
    for key in ("join_url", "cancel_url", "icon"):
        if len(result[key]) > 2048 or not valid_url(result[key]):
            errors[key] = "http://またはhttps://で始まるURLを入力してください．"
    joined = None
    try:
        joined = parse_time(result["joined_at"])
    except ValueError:
        errors["joined_at"] = "実在する日時を YYYY-MM-DDTHH:MM で入力してください．"
    if result["status"] == "trial":
        try:
            ending = parse_time(result["trial_ends_at"])
            if joined is not None and ending < joined:
                errors["trial_ends_at"] = "入会日時以降の日時を入力してください．"
        except ValueError:
            errors["trial_ends_at"] = "トライアル終了日時を YYYY-MM-DDTHH:MM で入力してください．"
    else:
        result["trial_ends_at"] = ""
    if errors:
        raise ValidationError(errors)
    return result


def sort_subscriptions(items, order="frequency"):
    """解約済みを末尾に集め，元データを変更せず安定した順序で返す．"""
    if order not in SORT_LABELS:
        raise ValueError("不明な並び順です．")
    def key(pair):
        index, item = pair
        cancelled = item.get("status") == "cancelled"
        value = item.get("created_at") or item.get("registered_at")
        try:
            registered = (parse_time(value).timestamp() if value else float("inf"), index)
        except (ValueError, TypeError, OSError):
            registered = (float("inf"), index)
        if order == "frequency":
            secondary = ({"weekly": 0, "monthly": 1, "yearly": 2}.get(item.get("cycle"), 9), registered)
        elif order == "deadline":
            value = item.get("next_payment_at") or item.get("trial_ends_at")
            try:
                time = parse_time(value).timestamp() if value else float("inf")
            except (ValueError, TypeError, OSError):
                time = float("inf")
            secondary = (time, registered)
        else:
            secondary = registered
        return (cancelled, secondary)
    return [item for _, item in sorted(enumerate(items), key=key)]


def cancellation_patch():
    """解約済みとして記録する更新内容を返す．公式手続きは利用者が行う．"""
    return {"status": "cancelled"}


def reactivation_patch(subscription, joined_at):
    """再契約の入会日時を検証し，サーバが再計算するための入会日時だけを送る．"""
    data = validate_subscription({**subscription, "status": "active", "joined_at": joined_at})
    return {"status": "active", "joined_at": data["joined_at"]}
```

## src/main.py

```python
"""アプリの起動と画面の切り替え。

画面を増やすとき:
  1. views/ に「page を受け取って中身を返す関数」を作る
  2. navigation.py にルートを足す
  3. 下の SCREENS に1行足す
ヘッダーと下部タブはここで全画面に付けるので、各画面は中身だけを返せばよい。
"""

import traceback
from dataclasses import dataclass
from pathlib import Path
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
    ft.run(main, assets_dir=str(Path(__file__).parent / "assets"))
```

## src/navigation.py

```python
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
```

## src/theme.py

```python
"""色・フォント・余白(全画面共通)。画面ごとに色コードを直接書かず、ここの定数を使う。"""

import flet as ft

# ---- 色 ----
GROUND = "#F3F5F4"       # 画面の地色
SURFACE = "#FFFFFF"      # ボタン、タブバー、カード
INK = "#14201C"          # 本文
INK_SUB = "#4A5552"      # 補足テキスト
LINE = "#D3D8D6"         # 枠線
ACCENT = "#0E6B5C"       # 主要ボタン、選択中の表示
ACCENT_SOFT = "#DCEBE7"  # 選択中タブの背景
TRIAL = "#B45309"        # 無料トライアルのバッジ
OFF_FILL = "#D3D8D6"     # 解約済みアイコンの面
OFF_INK = "#5A6360"      # 解約済みの文字
DOT = "#AEB6B3"          # ページ位置の点(非選択)
DANGER = "#A23B2A"       # エラー表示(通信エラーなどの案内)
ERROR = "#B3261E"        # エラー表示(入力フォームの検証エラー)
ON_ACCENT = "#FFFFFF"    # ACCENT や TRIAL の上に載せる文字

# アイコン画像がないサービスのタイル色、円グラフの色(白文字が読める濃さ)
TILE_COLORS = [
    "#7A2E3A", "#2F5D50", "#1F3A5F", "#8A4B14", "#2B4C7E", "#3D4A1F",
    "#6B2D5C", "#23515E", "#4A3728", "#36594A", "#5B3F8C", "#5E2A4F",
]

# ---- 寸法 ----
GUTTER = 24        # 画面左右の余白
TAP_MIN = 44       # タップできる要素の最小サイズ
BASE_WIDTH = 390   # 基準の画面幅
BASE_HEIGHT = 844

# ---- フォント(assets/fonts/ に同梱) ----
FONT = "ZenKaku"             # 本文
FONT_BOLD = "ZenKakuBold"    # 見出し、強調
FONT_BLACK = "ZenKakuBlack"  # アプリ名、アイコンの頭文字
FONTS = {
    FONT: "/fonts/ZenKakuGothicNew-Regular.ttf",
    FONT_BOLD: "/fonts/ZenKakuGothicNew-Bold.ttf",
    FONT_BLACK: "/fonts/ZenKakuGothicNew-Black.ttf",
}
_FAMILY_BY_WEIGHT = {"regular": FONT, "bold": FONT_BOLD, "black": FONT_BLACK}


def apply(page: ft.Page) -> None:
    """ページ全体にフォントと配色を設定する(main.py が起動時に1回呼ぶ)。"""
    page.fonts = FONTS
    page.theme = ft.Theme(color_scheme_seed=ACCENT, font_family=FONT)
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = GROUND
    page.padding = 0


def text(value: str, size: float = 14, weight: str = "regular", color: str = INK, **kwargs) -> ft.Text:
    """共通フォントの文字を作る。weight は "regular" / "bold" / "black"。"""
    return ft.Text(value, size=size, color=color, font_family=_FAMILY_BY_WEIGHT[weight], **kwargs)


def tile_color(index: int) -> str:
    """番号に応じたタイル色を返す(色数を超えたら最初に戻る)。"""
    return TILE_COLORS[index % len(TILE_COLORS)]


def yen(amount: int) -> str:
    """金額を「¥1,234」の形にする。"""
    return f"¥{amount:,}"
```

## src/views/__init__.py

```python
"""登録画面と状態変更の動作確認画面．"""
```

## src/views/account.py

```python
"""会員登録・ログイン画面(担当: 西内)。

いまは画面の切り替えを確認するための仮置き。担当者がこのファイルを書き換える。
関数名 account_view と引数(page)は main.py が使うので変えないこと。
"""

import flet as ft

from components import feedback


def account_view(page: ft.Page) -> ft.Control:
    """会員登録・ログイン画面の中身を返す。"""
    return feedback.message_panel("会員登録・ログイン画面は準備中です。\n(担当: 西内)", icon=ft.Icons.CONSTRUCTION)
```

## src/views/breakdown.py

```python
"""内訳画面(担当: 玉造)。月ごとの支払い見込み総額、円グラフ、サービス別の金額一覧。

・金額の計算は logic/payments.py だけで行う(この画面では計算しない)
・年額プランを「更新月に全額計上」するか「月割り」にするかを画面上で切り替えられる
・円グラフは flet-charts の PieChart
"""

from datetime import datetime

import flet as ft
import flet_charts as fch

import api_client
import navigation
import theme
from components import feedback
from logic import payments

MAX_SECTIONS = 6          # 円グラフで個別に出す件数。残りは「その他」にまとめる
OTHERS_COLOR = theme.OFF_INK
_MODE_KEY = "breakdown.yearly_mode"
_MODE_LABELS = {
    payments.MODE_BILLING: "年額は更新月に計上",
    payments.MODE_AVERAGE: "年額を月割り",
}


def _diff_text(diff: int) -> str:
    """前月差分の文言を返す。"""
    if diff > 0:
        return f"先月より {theme.yen(diff)} 多い"
    if diff < 0:
        return f"先月より {theme.yen(-diff)} 少ない"
    return "先月と同じ"


def _cycle_text(sub: dict, mode: str) -> str:
    """一覧の補足(プラン名と計上のしかた)を返す。"""
    if sub.get("cycle") == "yearly":
        cycle = "年額を月割り" if mode == payments.MODE_AVERAGE else "年額(今月が更新月)"
    else:
        cycle = "月額"
    if sub.get("status") == "trial":
        cycle += " / トライアル終了後"
    plan = sub.get("plan_name")
    return f"{plan} / {cycle}" if plan and plan not in ("月額プラン", "年額プラン") else cycle


def _pie(items: list[dict], colors: list[str]) -> ft.Control:
    """サービス別の支出割合の円グラフを返す。"""
    title_style = ft.TextStyle(size=12, color=theme.ON_ACCENT, font_family=theme.FONT_BOLD)
    shown = items[:MAX_SECTIONS]
    sections = [
        fch.PieChartSection(
            value=item["amount"],
            color=colors[index],
            radius=48,
            title=f"{round(item['ratio'] * 100)}%" if item["ratio"] >= 0.08 else "",
            title_style=title_style,
        )
        for index, item in enumerate(shown)
    ]
    rest = items[MAX_SECTIONS:]
    if rest:
        ratio = sum(item["ratio"] for item in rest)
        sections.append(
            fch.PieChartSection(
                value=sum(item["amount"] for item in rest),
                color=OTHERS_COLOR,
                radius=48,
                title=f"{round(ratio * 100)}%" if ratio >= 0.08 else "",
                title_style=title_style,
            )
        )
    return ft.Container(
        height=220,
        content=fch.PieChart(sections=sections, sections_space=2, center_space_radius=54, expand=True),
    )


def _item_row(page: ft.Page, item: dict, color: str, mode: str, last: bool) -> ft.Control:
    """金額一覧の1行を返す。タップで詳細画面へ。"""
    sub = item["sub"]
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        border=None if last else ft.Border.only(bottom=ft.BorderSide(1, theme.LINE)),
        on_click=lambda e: navigation.go_detail(page, sub["id"]),
        content=ft.Row(
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(width=12, height=12, border_radius=3, bgcolor=color),
                ft.Column(
                    expand=True,
                    spacing=0,
                    controls=[
                        theme.text(sub["name"], size=14, weight="bold", max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        theme.text(_cycle_text(sub, mode), size=11, color=theme.INK_SUB, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ],
                ),
                ft.Column(
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.END,
                    controls=[
                        theme.text(theme.yen(item["amount"]), size=14, weight="bold"),
                        theme.text(f"{round(item['ratio'] * 100)}%", size=11, color=theme.INK_SUB),
                    ],
                ),
            ],
        ),
    )


def breakdown_view(page: ft.Page) -> ft.Control:
    """内訳画面の中身を返す。"""
    try:
        subs = api_client.list_subscriptions()
    except api_client.ApiError as err:
        return feedback.error_panel(page, str(err))

    now = datetime.now()
    state = {
        "year": now.year,
        "month": now.month,
        "mode": page.session.store.get(_MODE_KEY) or payments.MODE_BILLING,
    }
    body = ft.Column(spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    def render() -> None:
        """今の年月と計上方法で、中身を組み立て直す。"""
        year, month, mode = state["year"], state["month"], state["mode"]
        summary = payments.summarize(subs, year, month, mode)
        items = summary["items"]
        colors = [theme.tile_color(index) if index < MAX_SECTIONS else OTHERS_COLOR for index in range(len(items))]
        is_this_month = (year, month) == (now.year, now.month)

        controls = [
            # 月の切り替え
            ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
                controls=[
                    ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, icon_color=theme.INK, tooltip="前の月", on_click=lambda e: move_month(-1)),
                    ft.Container(
                        width=150,
                        alignment=ft.Alignment.CENTER,
                        content=theme.text(f"{year}年{month}月" + ("(今月)" if is_this_month else ""), size=16, weight="bold"),
                    ),
                    ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, icon_color=theme.INK, tooltip="次の月", on_click=lambda e: move_month(1)),
                ],
            ),
            # 総額と前月差分
            ft.Container(
                padding=ft.Padding.only(top=4, bottom=16),
                content=ft.Column(
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        theme.text(theme.yen(summary["total"]), size=40, weight="black"),
                        theme.text(_diff_text(summary["diff"]), size=13, color=theme.INK_SUB),
                    ],
                ),
            ),
            # 年額プランの計上方法
            ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.SegmentedButton(
                        selected=[mode],
                        show_selected_icon=False,
                        segments=[
                            ft.Segment(value=value, label=theme.text(label, size=12))
                            for value, label in _MODE_LABELS.items()
                        ],
                        on_change=change_mode,
                    )
                ],
            ),
        ]

        if not items:
            controls.append(feedback.message_panel("この月に支払い予定のサブスクはありません。"))
        else:
            controls.append(ft.Container(padding=ft.Padding.only(top=20, bottom=20), content=_pie(items, colors)))
            if len(items) > MAX_SECTIONS:
                controls.append(
                    ft.Container(
                        padding=ft.Padding.only(bottom=8),
                        content=theme.text(
                            f"円グラフは上位{MAX_SECTIONS}件を表示し、残りは「その他」(灰色)にまとめています。",
                            size=11,
                            color=theme.INK_SUB,
                        ),
                    )
                )
            controls.append(
                ft.Container(
                    bgcolor=theme.SURFACE,
                    border=ft.Border.all(1, theme.LINE),
                    border_radius=16,
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    content=ft.Column(
                        spacing=0,
                        controls=[
                            _item_row(page, item, colors[index], mode, last=index == len(items) - 1)
                            for index, item in enumerate(items)
                        ],
                    ),
                )
            )
        body.controls = controls

    def move_month(step: int) -> None:
        mover = payments.next_month if step > 0 else payments.previous_month
        state["year"], state["month"] = mover(state["year"], state["month"])
        render()
        page.update()

    def change_mode(e) -> None:
        selected = e.control.selected
        if not selected:
            return
        state["mode"] = selected[0]
        page.session.store.set(_MODE_KEY, state["mode"])  # アプリを閉じるまで選択を覚えておく
        render()
        page.update()

    render()

    return ft.Column(
        expand=True,
        spacing=0,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            ft.Container(
                padding=ft.Padding.only(left=theme.GUTTER, right=theme.GUTTER, top=24, bottom=8),
                content=theme.text("支払い見込み", size=26, weight="bold"),
            ),
            ft.Container(
                padding=ft.Padding.only(left=theme.GUTTER, right=theme.GUTTER, bottom=32),
                content=body,
            ),
        ],
    )
```

## src/views/deadline.py

```python
"""期限画面(担当: 小湊)。支払期日が近い順にサブスクを並べ，残り日数を強調表示する。"""

from datetime import datetime

import flet as ft

import api_client
import navigation
import theme
from components.service_icon import service_icon
from logic.dates import next_payment_at


def _badge(days_left: int) -> ft.Control:
    """残り日数に応じたバッジを返す(当日は赤，3日以内は注意色)。"""
    if days_left <= 0:
        text, bg, fg = "本日更新", ft.Colors.RED_100, ft.Colors.RED_800
    elif days_left <= 3:
        text, bg, fg = f"あと {days_left} 日", ft.Colors.ORANGE_100, theme.TRIAL
    else:
        text, bg, fg = f"あと {days_left} 日", theme.GROUND, theme.INK_SUB
    return ft.Container(
        bgcolor=bg,
        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        border_radius=16,
        content=theme.text(text, size=12, weight="bold", color=fg),
    )


def _card(page: ft.Page, sub: dict, due: datetime) -> ft.Control:
    """一覧1件分のカードを返す。タップで詳細画面へ。"""
    days_left = (due.date() - datetime.now().date()).days
    return ft.Container(
        bgcolor=theme.SURFACE,
        border_radius=12,
        padding=16,
        border=ft.Border.all(1, theme.LINE),
        on_click=lambda e: navigation.go_detail(page, sub.get("id")),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    spacing=12,
                    controls=[
                        service_icon(sub, size=44),
                        ft.Column(
                            alignment=ft.MainAxisAlignment.CENTER,
                            horizontal_alignment=ft.CrossAxisAlignment.START,
                            spacing=2,
                            controls=[
                                theme.text(sub.get("name", ""), size=16, weight="bold"),
                                theme.text(f"{theme.yen(sub.get('amount', 0))}（{due.strftime('%m/%d')}）",
                                          size=13, color=theme.INK_SUB),
                            ],
                        ),
                    ],
                ),
                _badge(days_left),
            ],
        ),
    )


def deadline_view(page: ft.Page) -> ft.Control:
    """期限画面の中身を返す。"""
    items = []
    for sub in api_client.list_subscriptions() or []:
        due = next_payment_at(sub)
        if due is not None:
            items.append((sub, due))
    items.sort(key=lambda pair: pair[1])

    cards = [_card(page, sub, due) for sub, due in items]
    if not cards:
        cards = [ft.Container(
            padding=32,
            alignment=ft.Alignment.CENTER,
            content=theme.text("直近で更新予定のサブスクはありません。", size=14, color=theme.INK_SUB),
        )]

    return ft.Column(
        scroll=ft.ScrollMode.AUTO,
        spacing=16,
        controls=[
            theme.text("支払期日が近いサブスク", size=22, weight="bold"),
            theme.text("解約の検討やチャージ確認にお役立てください。", size=13, color=theme.INK_SUB),
            ft.Column(spacing=10, controls=cards),
        ],
    )
```

## src/views/detail.py

```python
"""詳細画面(担当: 小湊)。

登録済みサブスク1件の詳細表示、入会・退会ページへの遷移、解約・再契約、削除を行う。
解約・再契約の確認フローは components.status_actions に委ねる(登録画面とは独立して作られた部品)。
"""

import flet as ft

import api_client
import navigation
import theme
from api_client import ApiError
from components import feedback
from components.service_icon import service_icon
from components.status_actions import status_actions
from logic.dates import next_payment_at


def _next_payment_text(item: dict) -> str:
    """次回更新日の表示文言を返す(解約済みはなし)。"""
    dt = next_payment_at(item)
    return dt.strftime("%Y年%m月%d日") if dt else "なし（解約済み）"


def detail_view(page: ft.Page) -> ft.Control:
    """詳細画面の中身を返す。"""
    sub_id = navigation.get_sub_id(page)
    try:
        item = api_client.get_subscription(sub_id)
    except ApiError as error:
        return feedback.message_panel(str(error), icon=ft.Icons.ERROR_OUTLINE)

    def open_delete_dialog(event):
        def confirm_delete(event):
            api_client.delete_subscription(sub_id)
            page.pop_dialog()
            page.show_dialog(ft.SnackBar(ft.Text("削除しました．")))
            navigation.go_back(page)

        dialog = ft.AlertDialog(
            title=ft.Text("サブスクの削除"),
            content=ft.Text(f"「{item.get('name')}」を一覧から削除してもよろしいですか．"),
            actions=[
                ft.TextButton("キャンセル", on_click=lambda e: page.pop_dialog()),
                ft.TextButton("削除", on_click=confirm_delete),
            ],
        )
        page.show_dialog(dialog)

    def status_changed(updated: dict):
        page.show_dialog(ft.SnackBar(ft.Text("契約状態を更新しました．")))
        navigation.reload(page)

    return ft.Column(
        scroll=ft.ScrollMode.AUTO,
        spacing=20,
        controls=[
            ft.Container(
                bgcolor=theme.SURFACE,
                border_radius=12,
                padding=20,
                border=ft.Border.all(1, theme.LINE),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                    controls=[
                        service_icon(item, size=64),
                        theme.text(item.get("name", ""), size=22, weight="bold"),
                        theme.text(item.get("plan_name", ""), size=14, color=theme.INK_SUB),
                        ft.Divider(color=theme.LINE, height=1),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                theme.text("利用料金", size=14, color=theme.INK_SUB),
                                theme.text(
                                    f"{theme.yen(item.get('amount', 0))} / "
                                    + ("月" if item.get("cycle") == "monthly" else "年"),
                                    size=18, weight="bold",
                                ),
                            ],
                        ),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                theme.text("次回更新日", size=14, color=theme.INK_SUB),
                                theme.text(
                                    _next_payment_text(item), size=16, weight="bold",
                                    color=theme.TRIAL if item.get("status") == "trial" else theme.INK,
                                ),
                            ],
                        ),
                    ],
                ),
            ),
            ft.Container(
                bgcolor=theme.SURFACE,
                border_radius=12,
                padding=16,
                border=ft.Border.all(1, theme.LINE),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.START,
                    spacing=8,
                    controls=[
                        ft.Row(controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINED, size=18, color=theme.INK_SUB),
                            theme.text("手続き時の確認事項", size=14, weight="bold"),
                        ]),
                        theme.text(item.get("cancel_memo") or "メモはありません．", size=13, color=theme.INK_SUB),
                    ],
                ),
            ),
            status_actions(page, item, api_client, status_changed),
            ft.OutlinedButton(
                content=ft.Row([ft.Icon(ft.Icons.DELETE_OUTLINE), ft.Text("削除する")],
                    alignment=ft.MainAxisAlignment.CENTER),
                style=ft.ButtonStyle(color=theme.DANGER),
                height=48,
                on_click=open_delete_dialog,
            ),
        ],
    )
```

## src/views/home.py

```python
"""ホーム画面(担当: 玉造)。契約中サブスクのアイコン一覧。

・4列 x 3行 = 1ページ12件。横スワイプ(ft.PageView)でページを送る
・無料トライアル中は時計バッジ、解約済みはグレーアウト(components/service_icon.py)
・並び順は「更新頻度順」「登録順」。どちらでも解約済みは末尾(logic/ordering.py)
・アイコンをタップすると詳細画面へ移る
"""

import math

import flet as ft

import api_client
import navigation
import theme
from components import feedback
from components.service_icon import footprint, service_icon, status_label
from logic import ordering

COLUMNS = 4
ROWS = 3
PER_PAGE = COLUMNS * ROWS
SIDE_PADDING = 16   # 一覧の左右余白(バッジのはみ出し分があるので GUTTER より少し狭い)
NAME_HEIGHT = 20    # サービス名の行の高さ
ROW_GAP = 18        # 行と行の間


def _icon_size(page: ft.Page) -> int:
    """画面幅に合わせたアイコンの大きさを返す(基準幅390pxで72px)。"""
    width = page.width or theme.BASE_WIDTH
    cell = (min(width, 430) - SIDE_PADDING * 2) / COLUMNS
    return int(max(48, min(72, cell - 17)))


def _tile(page: ft.Page, sub: dict, size: int, color_index: int) -> ft.Control:
    """アイコン + サービス名の1マスを返す。タップで詳細画面へ。"""
    cancelled = sub.get("status") == "cancelled"
    state = status_label(sub)
    label = f"{sub['name']}({state})の詳細を開く" if state else f"{sub['name']}の詳細を開く"
    return ft.Container(
        expand=1,
        on_click=lambda e: navigation.go_detail(page, sub["id"]),
        content=ft.Semantics(
            label=label,
            button=True,
            content=ft.Column(
                spacing=6,
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    service_icon(sub, size=size, color_index=color_index),
                    ft.Container(
                        height=NAME_HEIGHT,
                        padding=ft.Padding.symmetric(horizontal=2),
                        alignment=ft.Alignment.CENTER,
                        content=theme.text(
                            sub["name"],
                            size=12,
                            color=theme.OFF_INK if cancelled else theme.INK,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ),
                ],
            ),
        ),
    )


def _row_height(size: int) -> int:
    """一覧1行分の高さを返す。"""
    return int(footprint(size)[1]) + 6 + NAME_HEIGHT


def _build_pages(page: ft.Page, subs: list[dict], size: int, color_index: dict) -> list[ft.Control]:
    """並び替え済みのサブスクを、12件ずつのページに分けて返す。"""
    pages = []
    for start in range(0, len(subs), PER_PAGE):
        chunk = subs[start:start + PER_PAGE]
        rows = []
        for row_start in range(0, len(chunk), COLUMNS):
            cells = [_tile(page, sub, size, color_index[sub["id"]]) for sub in chunk[row_start:row_start + COLUMNS]]
            cells += [ft.Container(expand=1) for _ in range(COLUMNS - len(cells))]  # 端数の行を左詰めにする
            rows.append(ft.Row(controls=cells, spacing=0, vertical_alignment=ft.CrossAxisAlignment.START))
        pages.append(
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=SIDE_PADDING),
                content=ft.Column(controls=rows, spacing=ROW_GAP),
            )
        )
    return pages


def _legend() -> ft.Control:
    """バッジとグレー表示の意味を示す凡例を返す。"""
    return ft.Row(
        spacing=12,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Row(
                spacing=5,
                controls=[
                    ft.Container(
                        width=16,
                        height=16,
                        border_radius=8,
                        bgcolor=theme.TRIAL,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.ACCESS_TIME, size=11, color=theme.ON_ACCENT),
                    ),
                    theme.text("トライアル中", size=11, color=theme.INK_SUB),
                ],
            ),
            ft.Row(
                spacing=5,
                controls=[
                    ft.Container(width=14, height=14, border_radius=4, bgcolor=theme.OFF_FILL),
                    theme.text("解約済み", size=11, color=theme.INK_SUB),
                ],
            ),
        ],
    )


def home_view(page: ft.Page) -> ft.Control:
    """ホーム画面の中身を返す。"""
    try:
        subs = api_client.list_subscriptions()
    except api_client.ApiError as err:
        return feedback.error_panel(page, str(err))

    heading = ft.Container(
        padding=ft.Padding.only(left=theme.GUTTER, right=theme.GUTTER, top=24),
        content=theme.text("契約中のサブスク", size=26, weight="bold"),
    )

    if not subs:
        return ft.Column(
            expand=True,
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                heading,
                feedback.message_panel(
                    "まだサブスクが登録されていません。\n契約中のサービスを追加すると、ここに一覧で表示されます。",
                    button_label="サブスクを追加",
                    on_click=lambda e: navigation.go(page, navigation.REGISTER),
                ),
            ],
        )

    counts = ordering.count_by_status(subs)
    size = _icon_size(page)
    # タイルの色は登録順で固定し、並び替えても同じサービスは同じ色にする
    color_index = {sub["id"]: index for index, sub in enumerate(subs)}
    page_count = math.ceil(len(subs) / PER_PAGE)
    rows_shown = min(ROWS, math.ceil(len(subs) / COLUMNS))
    state = {"order": ordering.ORDER_FREQUENCY, "current": 0}

    def sorted_pages() -> list[ft.Control]:
        return _build_pages(page, ordering.sort_subscriptions(subs, state["order"]), size, color_index)

    # ---- ページ位置(点と「1 / 2」) ----
    dots = ft.Row(spacing=0, alignment=ft.MainAxisAlignment.CENTER, visible=page_count > 1)
    page_label = theme.text("", size=12, color=theme.INK_SUB)

    def show_page(index: int) -> None:
        page.run_task(pager.go_to_page, index, 250)

    def refresh_position() -> None:
        current = state["current"]
        dots.controls = [
            ft.Container(
                width=28,
                height=theme.TAP_MIN,
                alignment=ft.Alignment.CENTER,
                tooltip=f"{index + 1}ページ目を表示",
                on_click=lambda e, index=index: show_page(index),
                content=ft.Container(
                    width=20 if index == current else 8,
                    height=8,
                    border_radius=4,
                    bgcolor=theme.ACCENT if index == current else theme.DOT,
                ),
            )
            for index in range(page_count)
        ]
        page_label.value = f"{current + 1} / {page_count}" if page_count > 1 else ""

    def on_page_change(e) -> None:
        state["current"] = int(e.control.selected_index or 0)
        refresh_position()
        page.update()

    # ---- アイコン一覧(横スワイプ) ----
    pager = ft.PageView(
        controls=sorted_pages(),
        height=rows_shown * _row_height(size) + (rows_shown - 1) * ROW_GAP + 4,
        on_change=on_page_change,
    )

    # ---- 並び替え ----
    order_label = theme.text(ordering.ORDER_LABELS[state["order"]], size=13, weight="bold")

    def change_order(order: str) -> None:
        if order == state["order"]:
            return
        state["order"] = order
        state["current"] = 0
        order_label.value = ordering.ORDER_LABELS[order]
        pager.controls = sorted_pages()
        pager.selected_index = 0
        refresh_position()
        page.update()

    sort_menu = ft.PopupMenuButton(
        tooltip="並び順を変える",
        content=ft.Container(
            height=theme.TAP_MIN,
            padding=ft.Padding.symmetric(horizontal=12),
            border_radius=12,
            bgcolor=theme.SURFACE,
            border=ft.Border.all(1, theme.LINE),
            content=ft.Row(
                spacing=6,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.SWAP_VERT, size=18, color=theme.INK),
                    order_label,
                    ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN, size=18, color=theme.INK),
                ],
            ),
        ),
        items=[
            ft.PopupMenuItem(content=theme.text(label, size=14), on_click=lambda e, order=order: change_order(order))
            for order, label in ordering.ORDER_LABELS.items()
        ],
    )

    refresh_position()

    return ft.Column(
        expand=True,
        spacing=0,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            heading,
            ft.Container(
                padding=ft.Padding.only(left=theme.GUTTER, right=theme.GUTTER, top=4),
                content=theme.text(
                    f"契約中 {counts['active']}件 / うちトライアル {counts['trial']}件 / 解約済み {counts['cancelled']}件",
                    size=13,
                    color=theme.INK_SUB,
                ),
            ),
            ft.Container(
                padding=ft.Padding.only(left=theme.GUTTER, right=theme.GUTTER, top=16, bottom=20),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    wrap=True,
                    run_spacing=8,
                    controls=[sort_menu, _legend()],
                ),
            ),
            pager,
            ft.Container(
                padding=ft.Padding.only(top=8, bottom=24),
                content=ft.Column(
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[dots, page_label],
                ),
            ),
        ],
    )
```

## src/views/register.py

```python
"""石井担当：定番サービス検索と手入力によるサブスク登録画面．"""
import asyncio
from datetime import datetime
import flet as ft
import theme
import api_client
import navigation
from api_client import ApiError
from logic.api_bridge import call_api
from logic.subscriptions import JST, CYCLE_LABELS, STATUS_LABELS, ValidationError, validate_subscription


def register_view(page, api=None, on_saved=None, on_back=None):
    """pageのみでも生成でき，共通APIと遷移コールバックを注入できる．"""
    api = api or api_client
    def default_saved(item):
        page.show_dialog(ft.SnackBar(ft.Text(item["name"] + "を保存しました．")))
        navigation.go_back(page)
    on_saved = on_saved or default_saved
    on_back = on_back or (lambda: navigation.go_back(page))
    message = ft.Text("", color=theme.ERROR)
    results = ft.Column(spacing=8)
    plans = ft.Dropdown(label="定番サービスのプラン", visible=False)
    selected = {"service": None, "search_version": 0, "busy": False, "completed": False}
    fields = {
        "name": ft.TextField(label="サービス名 *", max_length=100),
        "plan_name": ft.TextField(label="料金プラン名 *", max_length=100),
        "cycle": ft.Dropdown(label="更新周期 *", value="monthly", options=[
            ft.DropdownOption(key=key, text=value) for key, value in CYCLE_LABELS.items()]),
        "amount": ft.TextField(label="1回の支払額（円） *", keyboard_type=ft.KeyboardType.NUMBER,
                               helper="無料トライアル中も，有料移行後の金額を入力してください．"),
        "joined_at": ft.TextField(label="入会日時 *", value=datetime.now(JST).strftime("%Y-%m-%dT%H:%M"),
                                  helper="日本時間・分単位の例：2026-10-05T12:30"),
        "status": ft.Dropdown(label="契約状態 *", value="active", options=[
            ft.DropdownOption(key=key, text=value) for key, value in STATUS_LABELS.items() if key != "cancelled"]),
        "trial_ends_at": ft.TextField(label="トライアル終了日時 *", visible=False,
                                      hint_text="2026-11-05T12:30"),
        "join_url": ft.TextField(label="入会URL（任意）", hint_text="https://…"),
        "cancel_url": ft.TextField(label="退会URL（任意）", hint_text="https://…"),
        "cancel_memo": ft.TextField(label="退会に必要な情報（任意）", multiline=True,
                                    min_lines=2, max_lines=4, max_length=1000,
                                    helper="例：メールアドレスとパスワードの準備が必要．パスワード自体は入力しないでください．"),
    }

    def status_changed(event):
        """無料トライアルを選択したときだけ終了日時を表示する．"""
        fields["trial_ends_at"].visible = fields["status"].value == "trial"
        page.update()

    fields["status"].on_select = status_changed

    def apply_plan(event=None):
        """選択したプランを自動入力し，その後の手修正を許可する．"""
        service = selected["service"]
        if service and plans.value is not None:
            plan = service["plans"][int(plans.value)]
            for key, source in (("plan_name", "name"), ("cycle", "cycle"), ("amount", "amount")):
                fields[key].value = str(plan[source])
        page.update()

    plans.on_select = apply_plan

    def choose_service(service):
        """名称，URL，メモとプラン候補を取り込む．"""
        if selected["busy"]:
            return
        selected["search_version"] += 1
        selected["completed"] = False
        save_button.disabled = False
        selected["service"] = service
        for key in ("name", "join_url", "cancel_url", "cancel_memo"):
            fields[key].read_only = True
        for key in ("name", "join_url", "cancel_url", "cancel_memo"):
            fields[key].value = service.get(key, "")
        plans.options = [ft.DropdownOption(key=str(index), text=plan["name"])
                         for index, plan in enumerate(service.get("plans", []))]
        plans.visible = bool(plans.options)
        plans.value = "0" if plans.options else None
        apply_plan()
        results.controls = [ft.Text("選択済み：" + service["name"], color=theme.ACCENT)]
        page.update()

    async def search_services(event=None):
        """連続入力では古い検索結果を破棄し，失敗時は再試行できる．"""
        selected["search_version"] += 1
        version = selected["search_version"]
        await asyncio.sleep(0.25)
        if version != selected["search_version"]:
            return
        results.controls = [ft.ProgressRing(width=20, height=20)]
        page.update()
        try:
            services = await call_api(api, "search_services", search.value or "")
            if version != selected["search_version"]:
                return
            results.controls = [ft.Button(service["name"], height=44,
                               on_click=lambda e, service=service: choose_service(service)) for service in services]
            if not services:
                results.controls = [ft.Text("該当するサービスがありません．下の欄へ手入力できます．", color=theme.INK_SUB)]
        except ApiError as error:
            if version != selected["search_version"]:
                return
            results.controls = [ft.Text(str(error), color=theme.ERROR),
                                ft.Button("検索を再試行", on_click=search_services)]
        page.update()

    search = ft.TextField(label="定番サービスを名称で検索", prefix_icon=ft.Icons.SEARCH,
                          on_change=search_services, on_submit=search_services)

    def clear_service(event):
        """定番サービスとの関連を解除し，手入力用の空欄に戻す．"""
        selected["search_version"] += 1
        selected["completed"] = False
        save_button.disabled = False
        selected["service"] = None
        for key in ("name", "join_url", "cancel_url", "cancel_memo"):
            fields[key].read_only = False
        for key in ("name", "plan_name", "amount", "join_url", "cancel_url", "cancel_memo"):
            fields[key].value = ""
        plans.visible = False
        results.controls = []
        page.update()

    async def save(event):
        """入力を検証し，二重クリックによる重複登録を防ぐ．"""
        if selected["busy"] or selected["completed"]:
            return
        for control in fields.values():
            if isinstance(control, ft.Dropdown):
                control.error_text = None
            else:
                control.error = None
        message.value = ""
        message.color = theme.ERROR
        service = selected["service"] or {}
        data = {key: control.value for key, control in fields.items()}
        plan = service.get("plans", [])[int(plans.value)] if service and plans.value is not None else {}
        data.update(icon=service.get("icon", ""), service_id=service.get("id", ""), plan_id=plan.get("id", ""))
        try:
            data = validate_subscription(data)
        except ValidationError as error:
            for key, value in error.errors.items():
                if key in fields:
                    if isinstance(fields[key], ft.Dropdown):
                        fields[key].error_text = value
                    else:
                        fields[key].error = value
            message.value = "入力内容を確認してください．"
            page.update()
            return
        selected["busy"] = True
        save_button.disabled = True
        for control in [search, search_button, plans, manual_button, back_button, *fields.values()]:
            control.disabled = True
        page.update()
        try:
            item = await call_api(api, "create_subscription", data)
        except ApiError as error:
            message.value = str(error)
            aliases = {"custom_name": "name", "custom_join_url": "join_url",
                       "custom_cancel_url": "cancel_url", "custom_cancel_memo": "cancel_memo"}
            for key, errors in error.details.items():
                control = fields.get(aliases.get(key, key))
                if control is not None:
                    text = "，".join(map(str, errors)) if isinstance(errors, list) else str(errors)
                    if isinstance(control, ft.Dropdown):
                        control.error_text = text
                    else:
                        control.error = text
        else:
            selected["completed"] = True
            if on_saved:
                result = on_saved(item)
                if asyncio.iscoroutine(result):
                    await result
            else:
                message.color = theme.ACCENT
                message.value = "登録しました．"
        finally:
            selected["busy"] = False
            save_button.disabled = selected["completed"]
            for control in [search, search_button, plans, manual_button, back_button, *fields.values()]:
                control.disabled = False
            page.update()

    save_button = ft.Button("この内容で登録する", icon=ft.Icons.ADD, bgcolor=theme.ACCENT,
                            color=theme.SURFACE, height=48, on_click=save)
    manual_button = ft.TextButton("定番にないサービスを手入力する", on_click=clear_service)
    back_button = ft.TextButton("一覧に戻る", on_click=lambda e: on_back() if on_back else page.navigate("/"))
    search_button = ft.Button("定番サービスを表示・検索", height=44, on_click=search_services)
    return ft.Column(spacing=16, scroll=ft.ScrollMode.AUTO, controls=[
        back_button, ft.Text("サブスクを追加", size=26, weight=ft.FontWeight.BOLD, color=theme.INK),
        ft.Text("サービスを選ぶか，契約内容を手入力してください．定番の名称・URL・退会案内を変更する場合は手入力に切り替えてください．", color=theme.INK_SUB),
        search, search_button, results,
        manual_button, plans, *fields.values(), message, save_button,
    ])
```

## tests/conftest.py

```python
"""api_client はテスト間で共有されるモジュールなので，状態をテストごとに初期化する。"""
import copy

import pytest

import api_client
import dummy_data


@pytest.fixture(autouse=True)
def reset_dummy_store():
    """api_client のダミー一覧・ログイン状態をテストごとに初期状態へ戻す。"""
    api_client._dummy_subs = copy.deepcopy(dummy_data.SUBSCRIPTIONS)
    api_client._logged_in = True
    yield
```

## tests/test_api_contract.py

```python
"""設計書v0.2のサーバ応答・送信内容と通信断を外部通信なしで検証する．"""
import asyncio
import json
from datetime import datetime, timezone
import httpx
import pytest
from api_client import ApiClient, ApiError, OfflineError
from logic.subscriptions import cancellation_patch, reactivation_patch, sort_subscriptions


def draft(**changes):
    return {"name": "手入力", "plan_name": "月額", "amount": 1000, "cycle": "monthly",
            "joined_at": "2026-10-05T12:30", "status": "active", **changes}


def test_wrapped_services_and_subscriptions_keep_server_fields():
    async def scenario():
        record = {"id": 42, "next_payment_at": "2026-11-05T12:30+09:00", "created_at": "2026-10-05T12:30+09:00"}
        def handler(request):
            if request.url.path.endswith("services"):
                assert request.url.params["q"] == "動画"
                return httpx.Response(200, json={"services": [{"id": 3, "plans": [{"id": 30}]}]})
            return httpx.Response(200, json={"subscriptions": [record], "server_time": "2026-10-05T12:30+09:00"})
        async with httpx.AsyncClient(base_url="https://test.example/api/v1/", transport=httpx.MockTransport(handler)) as session:
            api = ApiClient(use_dummy=False, base_url="https://test.example/api/v1", http_session=session)
            assert (await api.search_services("動画"))[0]["plans"][0]["id"] == 30
            assert await api.list_subscriptions() == [record]
    asyncio.run(scenario())


@pytest.mark.parametrize("standard", [True, False])
def test_registration_sends_ids_or_custom_fields_and_japanese_time(standard):
    async def scenario():
        def handler(request):
            assert request.method == "POST" and request.url.path == "/api/v1/subscriptions"
            payload = json.loads(request.content)
            assert payload["joined_at"] == "2026-10-05T12:30+09:00"
            assert payload["trial_ends_at"] == "2026-10-10T12:30+09:00"
            assert not {"status", "name", "icon", "next_payment_at"} & payload.keys()
            if standard:
                assert payload["service_id"] == 3 and payload["plan_id"] == 30
                assert "custom_name" not in payload
            else:
                assert payload["custom_name"] == "手入力"
                assert payload["custom_cancel_url"] == "https://example.com/cancel"
                assert "service_id" not in payload
            return httpx.Response(201, json={"id": 42, "status": "trial", **payload})
        async with httpx.AsyncClient(base_url="https://test.example/api/v1/", transport=httpx.MockTransport(handler)) as session:
            api = ApiClient(use_dummy=False, base_url="https://test.example/api/v1", http_session=session)
            data = draft(status="trial", trial_ends_at="2026-10-10T12:30", cancel_url="https://example.com/cancel")
            if standard:
                data.update(service_id=3, plan_id=30)
            assert (await api.create_subscription(data))["id"] == 42
    asyncio.run(scenario())


def test_cancel_and_reactivate_accept_server_dates_without_sending_computed_fields():
    async def scenario():
        seen = []
        def handler(request):
            seen.append(json.loads(request.content))
            assert request.method == "PATCH" and request.url.path == "/api/v1/subscriptions/42"
            return httpx.Response(200, json={"id": 42, "next_payment_at": "2026-11-05T12:30+09:00", **seen[-1]})
        async with httpx.AsyncClient(base_url="https://test.example/api/v1/", transport=httpx.MockTransport(handler)) as session:
            api = ApiClient(use_dummy=False, base_url="https://test.example/api/v1", http_session=session)
            await api.update_subscription(42, cancellation_patch())
            result = await api.update_subscription(42, reactivation_patch(draft(joined_at="2026-01-01T12:30+09:00", status="cancelled"), "2026-10-05T12:30"))
            assert seen == [{"status": "cancelled"}, {"status": "active", "joined_at": "2026-10-05T12:30+09:00"}]
            assert result["next_payment_at"] == "2026-11-05T12:30+09:00"
    asyncio.run(scenario())


def test_validation_error_retains_field_details():
    async def scenario():
        body = {"error": {"code": "validation_error", "message": "入力内容に誤りがあります", "details": {"amount": ["金額を確認してください"]}}}
        async with httpx.AsyncClient(base_url="https://test.example/api/v1/", transport=httpx.MockTransport(lambda request: httpx.Response(422, json=body))) as session:
            api = ApiClient(use_dummy=False, base_url="https://test.example/api/v1", http_session=session)
            with pytest.raises(ApiError) as error:
                await api.create_subscription(draft())
            assert error.value.status_code == 422
            assert error.value.code == "validation_error"
            assert error.value.details == body["error"]["details"]
    asyncio.run(scenario())


def test_offline_registration_does_not_retry_or_write_dummy_storage(tmp_path):
    async def scenario():
        calls = []
        def handler(request):
            calls.append(request)
            raise httpx.ConnectError("offline", request=request)
        file = tmp_path / "must-not-exist.json"
        async with httpx.AsyncClient(base_url="https://test.example/api/v1/", transport=httpx.MockTransport(handler)) as session:
            api = ApiClient(file, use_dummy=False, base_url="https://test.example/api/v1", http_session=session)
            with pytest.raises(OfflineError):
                await api.create_subscription(draft())
            assert len(calls) == 1 and not file.exists()
    asyncio.run(scenario())


def test_registration_order_uses_created_at_and_datetime_objects():
    records = [{"id": "later", "created_at": "2026-10-05T12:30+09:00"},
               {"id": "earlier", "created_at": datetime(2026, 10, 5, 2, tzinfo=timezone.utc)},
               {"id": "cancelled", "status": "cancelled", "created_at": "2026-01-01T00:00"}]
    assert [item["id"] for item in sort_subscriptions(records, "registered")] == ["earlier", "later", "cancelled"]


def test_deadline_order_compares_naive_japanese_time_and_utc():
    records = [{"id": "later", "next_payment_at": "2026-10-05T04:00+00:00"},
               {"id": "earlier", "next_payment_at": "2026-10-05T12:30"}]
    assert [item["id"] for item in sort_subscriptions(records, "deadline")] == ["earlier", "later"]
```

## tests/test_api_session.py

```python
"""Cookie認証を保持し，取得エラーを画面用の例外に変換する．"""
import httpx
import pytest

import api_client
import config
from api_client import ApiError


def test_cookie_session_is_shared_across_requests(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path == "/api/v1/session":
            return httpx.Response(200, json={"ok": True},
                                   headers={"set-cookie": "session=test; Path=/; HttpOnly; Secure"})
        return httpx.Response(200, json=[])

    monkeypatch.setattr(config, "USE_DUMMY_DATA", False)
    monkeypatch.setattr(api_client, "_client", httpx.Client(
        base_url="https://test.example", transport=httpx.MockTransport(handler)))

    api_client.log_in("demo@example.com", "secret")
    api_client.search_services("動画")
    api_client.list_subscriptions()

    assert seen[1].headers["cookie"] == "session=test"
    assert seen[2].headers["cookie"] == "session=test"
    assert "authorization" not in seen[2].headers


@pytest.mark.parametrize("status", [401, 403, 500])
def test_http_errors_become_api_errors(monkeypatch, status):
    monkeypatch.setattr(config, "USE_DUMMY_DATA", False)
    monkeypatch.setattr(api_client, "_client", httpx.Client(
        base_url="https://test.example",
        transport=httpx.MockTransport(lambda request: httpx.Response(status, json={"error": "details"})),
    ))
    with pytest.raises(ApiError):
        api_client.list_subscriptions()
```

## tests/test_dates.py

```python
"""logic/dates.py のテスト。"""

from datetime import datetime

from logic import dates


def sub(joined_at, cycle="monthly", status="active", trial_end_at=None):
    return {"joined_at": joined_at, "cycle": cycle, "status": status, "trial_end_at": trial_end_at, "amount": 1000}


def test_monthly_next_payment():
    s = sub("2026-09-20T21:00")
    assert dates.next_payment_at(s, datetime(2026, 10, 5, 9, 0)) == datetime(2026, 10, 20, 21, 0)


def test_same_day_before_and_after_time():
    s = sub("2026-09-20T21:00")
    assert dates.next_payment_at(s, datetime(2026, 10, 20, 20, 59)) == datetime(2026, 10, 20, 21, 0)
    assert dates.next_payment_at(s, datetime(2026, 10, 20, 21, 0)) == datetime(2026, 11, 20, 21, 0)


def test_month_end_is_clamped_without_drift():
    s = sub("2026-01-31T10:00")
    assert dates.next_payment_at(s, datetime(2026, 2, 1)) == datetime(2026, 2, 28, 10, 0)
    assert dates.next_payment_at(s, datetime(2026, 3, 1)) == datetime(2026, 3, 31, 10, 0)
    assert dates.next_payment_at(s, datetime(2026, 4, 1)) == datetime(2026, 4, 30, 10, 0)


def test_august_31():
    s = sub("2026-08-31T10:00")
    assert dates.next_payment_at(s, datetime(2026, 9, 1)) == datetime(2026, 9, 30, 10, 0)
    assert dates.next_payment_at(s, datetime(2026, 10, 1)) == datetime(2026, 10, 31, 10, 0)


def test_leap_day_yearly():
    s = sub("2024-02-29T12:00", cycle="yearly")
    assert dates.next_payment_at(s, datetime(2024, 3, 1)) == datetime(2025, 2, 28, 12, 0)
    assert dates.next_payment_at(s, datetime(2027, 3, 1)) == datetime(2028, 2, 29, 12, 0)


def test_yearly_across_new_year():
    s = sub("2025-12-15T08:00", cycle="yearly")
    assert dates.next_payment_at(s, datetime(2026, 1, 3)) == datetime(2026, 12, 15, 8, 0)


def test_monthly_across_new_year():
    s = sub("2025-11-25T08:00")
    assert dates.next_payment_at(s, datetime(2025, 12, 26)) == datetime(2026, 1, 25, 8, 0)


def test_cancelled_has_no_payment():
    s = sub("2026-01-10T10:00", status="cancelled")
    assert dates.next_payment_at(s, datetime(2026, 5, 1)) is None
    assert dates.payment_in_month(s, 2026, 5) is None


def test_trial_uses_trial_end():
    s = sub("2026-09-20T21:00", status="trial", trial_end_at="2026-10-20T21:00")
    assert dates.next_payment_at(s, datetime(2026, 10, 5)) == datetime(2026, 10, 20, 21, 0)
    assert dates.payment_in_month(s, 2026, 9) is None
    assert dates.payment_in_month(s, 2026, 10) == datetime(2026, 10, 20, 21, 0)
    assert dates.payment_in_month(s, 2026, 11) == datetime(2026, 11, 20, 21, 0)


def test_payment_in_month_before_join_and_yearly():
    monthly = sub("2026-03-10T10:00")
    assert dates.payment_in_month(monthly, 2026, 2) is None
    assert dates.payment_in_month(monthly, 2026, 3) == datetime(2026, 3, 10, 10, 0)
    yearly = sub("2025-11-05T14:00", cycle="yearly")
    assert dates.payment_in_month(yearly, 2026, 10) is None
    assert dates.payment_in_month(yearly, 2026, 11) == datetime(2026, 11, 5, 14, 0)
```

## tests/test_payments.py

```python
"""logic/payments.py と logic/ordering.py のテスト。"""

from logic import ordering, payments

SUBS = [
    {"id": 1, "name": "月額A", "cycle": "monthly", "amount": 1000, "joined_at": "2025-01-10T10:00", "status": "active"},
    {"id": 2, "name": "年額B", "cycle": "yearly", "amount": 12000, "joined_at": "2025-11-05T10:00", "status": "active"},
    {"id": 3, "name": "解約C", "cycle": "monthly", "amount": 500, "joined_at": "2025-01-10T10:00", "status": "cancelled"},
    {"id": 4, "name": "試用D", "cycle": "monthly", "amount": 2000, "joined_at": "2026-09-20T10:00", "status": "trial",
     "trial_end_at": "2026-10-20T10:00"},
]


def test_billing_mode_counts_yearly_only_in_renewal_month():
    assert payments.month_total(SUBS, 2026, 10) == 1000 + 2000
    assert payments.month_total(SUBS, 2026, 11) == 1000 + 12000 + 2000


def test_average_mode_splits_yearly():
    assert payments.month_total(SUBS, 2026, 10, payments.MODE_AVERAGE) == 1000 + 1000 + 2000
    # 入会前の月には計上しない
    assert payments.amount_in_month(SUBS[1], 2025, 10, payments.MODE_AVERAGE) == 0


def test_cancelled_is_excluded_and_trial_starts_at_trial_end():
    assert payments.amount_in_month(SUBS[2], 2026, 10) == 0
    assert payments.amount_in_month(SUBS[3], 2026, 9) == 0
    assert payments.amount_in_month(SUBS[3], 2026, 10) == 2000


def test_summarize():
    result = payments.summarize(SUBS, 2026, 11)
    assert result["total"] == 15000
    assert result["previous_total"] == 3000
    assert result["diff"] == 12000
    assert [item["sub"]["id"] for item in result["items"]] == [2, 4, 1]
    assert abs(sum(item["ratio"] for item in result["items"]) - 1.0) < 1e-9


def test_summarize_empty_month():
    result = payments.summarize(SUBS, 2024, 1)
    assert result["total"] == 0 and result["items"] == [] and result["diff"] == 0


def test_month_helpers():
    assert payments.previous_month(2026, 1) == (2025, 12)
    assert payments.next_month(2026, 12) == (2027, 1)


def test_ordering_keeps_cancelled_last():
    by_frequency = [s["id"] for s in ordering.sort_subscriptions(SUBS, ordering.ORDER_FREQUENCY)]
    assert by_frequency == [1, 4, 2, 3]
    by_registered = [s["id"] for s in ordering.sort_subscriptions(SUBS, ordering.ORDER_REGISTERED)]
    assert by_registered == [1, 2, 4, 3]
    assert ordering.count_by_status(SUBS) == {"active": 3, "trial": 1, "cancelled": 1}
```

## tests/test_shared_integration.py

```python
"""develop共通APIと石井担当画面の接続を検証する．"""
import asyncio
import json
import flet as ft
import httpx
import api_client
import config
from components.status_actions import status_actions
from views.register import register_view
from logic.subscriptions import cancellation_patch


class PageStub:
    def update(self):
        pass


def test_registration_and_status_use_same_shared_store():
    async def scenario():
        saved = []
        page = PageStub()
        initial = len(api_client.list_subscriptions())
        view = register_view(page, on_saved=saved.append, on_back=lambda: None)
        fields = {c.label: c for c in view.controls if isinstance(c, ft.TextField)}
        fields["サービス名 *"].value = "共通APIへの登録"
        fields["料金プラン名 *"].value = "月額"
        fields["1回の支払額（円） *"].value = "1000"
        await view.controls[-1].on_click(None)
        assert len(api_client.list_subscriptions()) == initial + 1
        item = api_client.get_subscription(saved[0]["id"])
        changed = []
        actions = status_actions(page, item, api_client, changed.append)
        next(c for c in actions.controls if isinstance(c, ft.Checkbox)).value = True
        await actions.controls[-1].on_click(None)
        assert api_client.get_subscription(item["id"])["status"] == "cancelled"
        assert changed[0]["id"] == item["id"]
    asyncio.run(scenario())


def test_shared_api_uses_v02_paths_payload_and_cookie(monkeypatch):
    seen = []
    def handler(request):
        seen.append(request)
        if request.url.path == "/api/v1/session":
            return httpx.Response(200, json={"user": {"id": 1}}, headers={"set-cookie": "session_id=test; Path=/; Secure"})
        assert request.headers["cookie"] == "session_id=test"
        if request.method == "GET":
            return httpx.Response(200, json={"subscriptions": [{"id": 42, "name": "試作", "joined_at": "2026-10-05T12:30+09:00", "trial_ends_at": None, "next_payment_at": "2026-11-05T12:30+09:00"}]})
        if request.method == "POST":
            payload = json.loads(request.content)
            assert payload["service_id"] == 3 and payload["plan_id"] == 30
            assert "status" not in payload and "name" not in payload
            return httpx.Response(201, json={"id": 42, "name": "試作", **payload})
        assert request.method == "PATCH"
        assert json.loads(request.content) == {"status": "cancelled"}
        return httpx.Response(200, json={"id": 42, "status": "cancelled"})
    monkeypatch.setattr(config, "USE_DUMMY_DATA", False)
    with httpx.Client(base_url="https://test.example/api/v1/", transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(api_client, "_client", client)
        api_client.log_in("demo@example.com", "secret")
        item = api_client.list_subscriptions()[0]
        assert item["joined_at"] == "2026-10-05T12:30"
        assert item["next_payment_at"] == "2026-11-05T12:30+09:00"
        api_client.create_subscription({"name": "試作", "plan_name": "月額", "amount": 1000, "cycle": "monthly", "status": "active", "joined_at": "2026-10-05T12:30", "service_id": 3, "plan_id": 30})
        api_client.update_subscription(42, cancellation_patch())
    assert [r.url.path for r in seen] == ["/api/v1/session", "/api/v1/subscriptions", "/api/v1/subscriptions", "/api/v1/subscriptions/42"]



def test_shared_views_construct_without_flet_api_errors():
    from types import SimpleNamespace
    from views.home import home_view
    from views.detail import detail_view
    from views.deadline import deadline_view
    from views.breakdown import breakdown_view
    class Store(dict):
        def set(self, key, value):
            self[key] = value
    page = PageStub()
    page.width = 390
    page.route = "/detail/1"
    page.session = SimpleNamespace(store=Store())
    for builder in (home_view, detail_view, deadline_view, breakdown_view):
        assert isinstance(builder(page), ft.Control)


def test_detail_uses_server_payment_date_instead_of_recalculation():
    from views.detail import _next_payment_text
    value = _next_payment_text({"status": "active", "joined_at": "2026-01-01T12:00", "cycle": "monthly", "next_payment_at": "2026-11-05T12:30+09:00"})
    assert value == "2026年11月05日"



def test_deadline_handles_mixed_server_dates_and_dummy_fallback():
    from views.deadline import deadline_view
    api_client._dummy_subs[0]["next_payment_at"] = "2026-11-05T03:30+00:00"
    assert isinstance(deadline_view(PageStub()), ft.Control)
```

## tests/test_storage.py

```python
"""ダミーデータに対する保存・解約・再契約の整合性と，検索結果の独立性を確認する．"""
import api_client
from logic.subscriptions import cancellation_patch, reactivation_patch


def test_save_cancel_reactivate_and_reload():
    item = api_client.create_subscription({
        "name": "手入力", "plan_name": "年間", "cycle": "yearly",
        "amount": "1200", "joined_at": "2026-01-31T12:00", "status": "active",
        "join_url": "https://example.com/join", "cancel_url": "https://example.com/cancel",
    })
    cancelled = api_client.update_subscription(item["id"], cancellation_patch())
    assert cancelled["status"] == "cancelled"
    assert cancelled["join_url"] == item["join_url"]
    active = api_client.update_subscription(item["id"], reactivation_patch(cancelled, "2026-10-05T12:00"))
    assert active["id"] == item["id"]
    reloaded = api_client.list_subscriptions()
    match = next(sub for sub in reloaded if sub["id"] == item["id"])
    assert match["joined_at"] == "2026-10-05T12:00"


def test_search_is_case_insensitive_and_does_not_mutate_master():
    values = api_client.search_services("NETFLIX")
    assert len(values) == 1
    values[0]["name"] = "書き換え"
    assert api_client.search_services("netflix")[0]["name"] != "書き換え"
```

## tests/test_subscriptions.py

```python
"""登録の境界値，並び順，解約・再契約で失うべき情報を検証する．"""
import pytest
from logic.subscriptions import (
    ValidationError, cancellation_patch, reactivation_patch,
    sort_subscriptions, validate_subscription, valid_url,
)


def record(**changes):
    """登録可能な基本データを作る．"""
    return {"name": "テスト", "plan_name": "月額", "amount": "1000", "cycle": "monthly",
            "status": "active", "joined_at": "2026-01-31T12:00", **changes}


def test_registration_normalizes_amount_and_preserves_manual_urls():
    data = validate_subscription(record(amount="１０００", join_url="https://example.com/join"))
    assert data["amount"] == 1000
    assert data["join_url"] == "https://example.com/join"


@pytest.mark.parametrize("changes,field", [
    ({"amount": "-1"}, "amount"), ({"amount": "1.5"}, "amount"),
    ({"amount": ""}, "amount"), ({"amount": "1000000000"}, "amount"),
    ({"name": " "}, "name"), ({"plan_name": ""}, "plan_name"),
    ({"joined_at": "2026-02-29T12:00"}, "joined_at"),
    ({"join_url": "javascript:alert(1)"}, "join_url"),
    ({"cancel_url": "https://user:pass@example.com"}, "cancel_url"),
    ({"cycle": "weekly"}, "cycle"), ({"status": "unknown"}, "status"),
    ({"status": "trial", "trial_ends_at": ""}, "trial_ends_at"),
    ({"status": "trial", "trial_ends_at": "2026-01-30T12:00"}, "trial_ends_at"),
])
def test_invalid_registration(changes, field):
    with pytest.raises(ValidationError) as raised:
        validate_subscription(record(**changes))
    assert field in raised.value.errors


def test_zero_yen_and_leap_day_are_valid():
    assert validate_subscription(record(amount="0", joined_at="2028-02-29T12:00"))["amount"] == 0


def test_trial_records_ending_and_cancellation_discards_it():
    data = validate_subscription(record(status="trial", trial_ends_at="2026-02-28T12:00"))
    assert data["trial_ends_at"] == "2026-02-28T12:00"
    cancelled = validate_subscription({**data, **cancellation_patch()})
    assert cancelled["trial_ends_at"] == ""
    assert cancelled["cancel_url"] == data["cancel_url"]


def test_reactivation_replaces_joined_date_and_clears_old_payment():
    patch = reactivation_patch(record(status="cancelled", next_payment_at="2026-02-28T12:00"), "2026-10-05T12:00")
    assert patch == {"status": "active", "joined_at": "2026-10-05T12:00"}


def test_sort_keeps_cancelled_last_and_does_not_mutate_input():
    items = [record(id="cancelled", status="cancelled"), record(id="year", cycle="yearly"), record(id="month")]
    assert [item["id"] for item in sort_subscriptions(items)] == ["month", "year", "cancelled"]
    assert [item["id"] for item in sort_subscriptions(items, "registered")] == ["year", "month", "cancelled"]
    assert [item["id"] for item in items] == ["cancelled", "year", "month"]


def test_deadline_sort_handles_unknown_dates_and_cancelled():
    items = [record(id="unknown"), record(id="later", next_payment_at="2026-12-01T00:00+09:00"),
             record(id="trial", status="trial", trial_ends_at="2026-10-10T00:00"),
             record(id="cancelled", status="cancelled", next_payment_at="2026-01-01T00:00")]
    assert [item["id"] for item in sort_subscriptions(items, "deadline")] == ["trial", "later", "unknown", "cancelled"]


@pytest.mark.parametrize("url", ["https://example.com", "http://example.com/path", ""])
def test_valid_url(url):
    assert valid_url(url)
```

## tests/test_ui_workflow.py

```python
"""Fletコントロールの生成と，画面イベントから保存までの流れを確認する．"""
import asyncio
import flet as ft
from api_client import ApiClient
from components.service_icon import service_icon
from components.status_actions import status_actions
from views.register import register_view



class PageStub:
    """画面イベントの検証に必要な更新・遷移を記録する．"""

    def update(self):
        """描画通信は行わない．"""

    def navigate(self, route):
        """検証中の遷移先を記録する．"""
        self.route = route


def test_registration_search_plan_and_save(tmp_path):
    async def scenario():
        page = PageStub()
        client = ApiClient(tmp_path / "records.json", use_dummy=True)
        saved = []
        view = register_view(page, client, on_saved=saved.append)
        fields = {control.label: control for control in view.controls if isinstance(control, (ft.TextField, ft.Dropdown))}
        search_button = next(control for control in view.controls if isinstance(control, ft.Button) and control.content == "定番サービスを表示・検索")
        await search_button.on_click(None)
        results = next(control for control in view.controls if isinstance(control, ft.Column))
        next(c for c in results.controls if c.content == "動画サービス（デモ）").on_click(None)
        assert fields["サービス名 *"].value == "動画サービス（デモ）"
        assert int(fields["1回の支払額（円） *"].value) >= 0
        fields["定番サービスのプラン"].value = "1"
        fields["定番サービスのプラン"].on_select(None)
        assert fields["料金プラン名 *"].value
        save = next(control for control in view.controls if isinstance(control, ft.Button) and control.content == "この内容で登録する")
        fields["1回の支払額（円） *"].value = "-1"
        await save.on_click(None)
        assert fields["1回の支払額（円） *"].error and not saved
        fields["1回の支払額（円） *"].value = "10000"
        await save.on_click(None)
        assert len(saved) == 1 and saved[0]["amount"] == 10000
        assert save.disabled and not fields["サービス名 *"].disabled
        await save.on_click(None)
        assert len(saved) == 1
    asyncio.run(scenario())


def test_status_requires_confirmation_and_preserves_id(tmp_path):
    async def scenario():
        page = PageStub()
        client = ApiClient(tmp_path / "records.json", use_dummy=True)
        item = await client.create_subscription({"name": "試作", "plan_name": "月額", "amount": "1000",
                    "cycle": "monthly", "status": "active", "joined_at": "2026-01-01T12:00"})
        changed = []
        view = status_actions(page, item, client, changed.append)
        save = view.controls[-1]
        await save.on_click(None)
        assert not changed
        check = next(control for control in view.controls if isinstance(control, ft.Checkbox))
        check.value = True
        await save.on_click(None)
        assert changed[0]["status"] == "cancelled"
        view = status_actions(page, changed[0], client, changed.append)
        joined = next(control for control in view.controls if isinstance(control, ft.TextField))
        joined.value = "invalid"
        next(control for control in view.controls if isinstance(control, ft.Checkbox)).value = True
        await view.controls[-1].on_click(None)
        assert joined.error and len(changed) == 1
        joined.value = "2026-10-05T12:00"
        await view.controls[-1].on_click(None)
        assert changed[-1]["status"] == "active" and changed[-1]["id"] == item["id"]
    asyncio.run(scenario())


def test_preview_and_icons_construct_with_pinned_flet(tmp_path):
    page = PageStub()
    item = {"id": "demo", "name": "試作", "plan_name": "月額", "amount": 1000,
            "cycle": "monthly", "status": "active", "joined_at": "2026-01-01T12:00"}
    assert isinstance(service_icon(item), ft.Stack)
    assert isinstance(service_icon({**item, "status": "trial"}), ft.Stack)
    assert isinstance(service_icon({**item, "status": "cancelled", "icon": "https://example.com/icon.png"}), ft.Stack)



def test_api_field_error_is_shown_and_input_is_preserved():
    from api_client import ApiError
    class FailingApi:
        async def create_subscription(self, data):
            raise ApiError("入力内容に誤りがあります", status_code=422,
                           details={"custom_name": ["名称を確認してください"]})
    async def scenario():
        view = register_view(PageStub(), FailingApi())
        fields = {control.label: control for control in view.controls if isinstance(control, ft.TextField)}
        fields["サービス名 *"].value = "試作"
        fields["料金プラン名 *"].value = "月額"
        fields["1回の支払額（円） *"].value = "1000"
        save = view.controls[-1]
        await save.on_click(None)
        assert fields["サービス名 *"].error == "名称を確認してください"
        assert fields["サービス名 *"].value == "試作" and not save.disabled
    asyncio.run(scenario())


def test_delayed_search_does_not_replace_manual_entry():
    class DelayedApi:
        def __init__(self):
            self.started = asyncio.Event()
            self.finish = asyncio.Event()
        async def search_services(self, keyword):
            self.started.set()
            await self.finish.wait()
            return [{"id": 3, "name": "古い結果"}]
    async def scenario():
        api = DelayedApi()
        view = register_view(PageStub(), api)
        search = next(c for c in view.controls if isinstance(c, ft.Button) and c.content == "定番サービスを表示・検索")
        pending = asyncio.create_task(search.on_click(None))
        await api.started.wait()
        next(c for c in view.controls if isinstance(c, ft.TextButton) and c.content == "定番にないサービスを手入力する").on_click(None)
        api.finish.set()
        await pending
        results = next(c for c in view.controls if isinstance(c, ft.Column))
        assert results.controls == []
    asyncio.run(scenario())


def test_preview_accepts_null_trial_end_and_datetime_joined(tmp_path):
    from datetime import datetime
    item = {"id": 42, "name": "試作", "plan_name": "月額", "amount": 1000,
            "cycle": "monthly", "status": "active", "joined_at": datetime(2026, 10, 5, 12),
            "trial_ends_at": None, "cancel_url": None}
    assert service_icon(item)



def test_icon_color_stays_with_subscription_when_order_changes():
    item = {"id": 42, "name": "試作", "status": "active"}
    other = {"id": 50, "name": "別契約", "status": "active"}
    initial = {value["id"]: service_icon(value).controls[0].bgcolor for value in [item, other]}
    reordered = {value["id"]: service_icon(value).controls[0].bgcolor for value in [other, item]}
    assert initial == reordered
```

## docs/register.html

```html
<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>サブマネ | サブスク登録</title>
<style>
@font-face { font-family: 'Zen Kaku Gothic New'; src: url('../src/assets/fonts/ZenKakuGothicNew-Regular.ttf') format('truetype'); font-display: swap; }
:root { --ground:#F3F5F4; --surface:#fff; --ink:#14201C; --muted:#4A5552; --line:#D3D8D6; --accent:#0E6B5C; --soft:#DCEBE7; --trial:#B45309; --error:#B3261E; }
* { box-sizing:border-box; }
body { margin:0; background:var(--ground); color:var(--ink); font-family:'Zen Kaku Gothic New','Yu Gothic',sans-serif; }
button,input,select,textarea { font:inherit; }
button,a,input,select,textarea { -webkit-tap-highlight-color:transparent; }
button { cursor:pointer; }
[hidden] { display:none !important; }
:focus-visible { outline:3px solid var(--accent); outline-offset:3px; }
.app { max-width:430px; margin:auto; min-height:100vh; padding:env(safe-area-inset-top) 24px calc(32px + env(safe-area-inset-bottom)); }
header { display:flex; align-items:center; justify-content:space-between; padding:16px 0 10px; }
.brand { font-size:22px; font-weight:900; color:var(--accent); }
.back { min-height:44px; display:inline-flex; align-items:center; color:var(--muted); font-size:13px; text-decoration:none; }
h1 { font-size:26px; line-height:1.4; margin:14px 0 8px; }
h2 { font-size:18px; margin:0 0 16px; }
p { line-height:1.7; }
.intro { font-size:14px; color:var(--muted); margin:0 0 20px; }
.demo { font-size:12px; background:var(--soft); color:var(--accent); border-radius:10px; padding:10px 12px; margin:0 0 24px; }
.section { border-top:1px solid var(--line); padding:24px 0 8px; }
.step { color:var(--accent); font-size:12px; display:block; margin-bottom:4px; letter-spacing:.08em; }
.field { margin-bottom:18px; }
label { display:block; font-size:13px; font-weight:bold; margin-bottom:7px; }
.required { color:var(--accent); font-size:11px; margin-left:6px; }
.optional { color:var(--muted); font-size:11px; font-weight:normal; margin-left:6px; }
input,select,textarea { width:100%; min-width:0; min-height:48px; border:1px solid var(--line); border-radius:10px; padding:12px; color:var(--ink); background:var(--surface); font-size:15px; }
textarea { resize:vertical; min-height:96px; }
input[aria-invalid="true"],select[aria-invalid="true"] { border-color:var(--error); }
.helper { display:block; margin:6px 0 0; font-size:12px; color:var(--muted); line-height:1.65; }
.error { display:block; font-size:12px; line-height:1.6; color:var(--error); margin-top:5px; }
.pair { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.results { display:flex; flex-direction:column; gap:8px; margin:12px 0; }
.service { display:flex; align-items:center; gap:12px; text-align:left; width:100%; padding:12px; background:var(--surface); border:1px solid var(--line); border-radius:12px; min-height:68px; }
.service[aria-pressed="true"] { border:2px solid var(--accent); background:var(--soft); }
.service-icon { flex:0 0 40px; height:40px; display:grid; place-items:center; border-radius:12px; color:white; background:var(--accent); font-size:18px; }
.service-name { font-weight:bold; font-size:14px; }
.service-note { color:var(--muted); font-size:11px; display:block; margin-top:2px; }
.text-button { border:0; background:none; color:var(--accent); min-height:44px; padding:8px 0; font-size:13px; text-align:left; }
.primary { width:100%; min-height:50px; border:0; border-radius:12px; background:var(--accent); color:white; font-size:15px; font-weight:bold; padding:12px; }
button:disabled { cursor:default; opacity:.6; }
.notice { margin:12px 0; font-size:13px; color:var(--error); }
.success { border:1px solid var(--accent); background:var(--soft); border-radius:12px; padding:18px; margin:18px 0; }
.success h2 { margin-bottom:8px; color:var(--accent); }
.success p { font-size:13px; margin:4px 0; }
.saved { padding:12px 0; border-bottom:1px solid var(--line); }
.saved strong { display:block; font-size:14px; }
.saved span { color:var(--muted); font-size:12px; }
.saved.cancelled { opacity:.6; }
.saved.trial strong::before { content:'◷ '; color:var(--trial); }
footer { color:var(--muted); font-size:11px; text-align:center; margin-top:24px; }
@media(max-width:350px) { .app { padding-left:16px; padding-right:16px; } .pair { grid-template-columns:1fr; gap:0; } }
</style>
</head>
<body>
<div class="app">
  <header><span class="brand">サブマネ</span><a class="back" href="home_mock.html">‹ ホームの見本へ</a></header>
  <main>
    <h1>サブスクを追加</h1>
    <p class="intro">サービスを選ぶか，契約内容を手入力して登録してください．</p>
    <p class="demo">HTMLデモ：登録内容はこのブラウザに保存します．Flet版とは同期しません．</p>
    <section aria-labelledby="search-heading">
      <span class="step">STEP 01</span><h2 id="search-heading">サービスを選ぶ</h2>
      <label for="search">定番サービスを名称で検索</label>
      <input id="search" type="search" placeholder="動画，音楽，読書など" autocomplete="off" aria-describedby="master-note">
      <span class="helper" id="master-note">表示される名称・料金・URLは架空のデモ情報です．</span>
      <div class="results" id="results" aria-label="検索結果"></div>
      <p class="helper" id="search-status" role="status"></p>
      <button class="text-button" id="manual" type="button">＋ 定番にないサービスを手入力する</button>
    </section>
    <form id="registration" novalidate>
      <section class="section" aria-labelledby="contract-heading">
        <span class="step">STEP 02</span><h2 id="contract-heading">契約内容を入力</h2>
        <div class="field" id="preset-field" hidden>
          <label for="preset">定番サービスのプラン</label><select id="preset"></select>
          <span class="helper">プランを選んだ後，各項目を修正できます．</span>
        </div>
        <div class="field"><label for="name">サービス名<span class="required">必須</span></label>
          <input id="name" name="name" maxlength="100" required aria-describedby="name-error"><span class="error" id="name-error"></span></div>
        <div class="field"><label for="plan_name">料金プラン名<span class="required">必須</span></label>
          <input id="plan_name" name="plan_name" maxlength="100" placeholder="個人プランなど" required aria-describedby="plan_name-error"><span class="error" id="plan_name-error"></span></div>
        <div class="pair">
          <div class="field"><label for="cycle">更新周期<span class="required">必須</span></label>
            <select id="cycle" name="cycle" aria-describedby="cycle-error"><option value="monthly">月額</option><option value="yearly">年額</option></select><span class="error" id="cycle-error"></span></div>
          <div class="field"><label for="amount">1回の支払額（円）<span class="required">必須</span></label>
            <input id="amount" name="amount" type="text" inputmode="numeric" placeholder="1000" required aria-describedby="amount-error amount-help"><span class="error" id="amount-error"></span></div>
        </div>
        <p class="helper" id="amount-help">無料トライアル中も，有料移行後の1回の金額を入力してください．</p>
        <div class="field" style="margin-top:18px"><label for="joined_at">入会日時<span class="required">必須</span></label>
          <input id="joined_at" name="joined_at" type="datetime-local" step="60" required aria-describedby="joined_at-error joined-help">
          <span class="helper" id="joined-help">日本時間・分単位で入力してください．</span><span class="error" id="joined_at-error"></span></div>
        <div class="field"><label for="status">契約状態<span class="required">必須</span></label>
          <select id="status" name="status" aria-describedby="status-error"><option value="active">契約中</option><option value="trial">無料トライアル中</option><option value="cancelled">解約済み</option></select><span class="error" id="status-error"></span></div>
        <div class="field" id="trial-field" hidden><label for="trial_ends_at">トライアル終了日時<span class="required">必須</span></label>
          <input id="trial_ends_at" name="trial_ends_at" type="datetime-local" step="60" aria-describedby="trial_ends_at-error trial-help">
          <span class="helper" id="trial-help">この日時をトライアルの次回支払日として扱います．</span><span class="error" id="trial_ends_at-error"></span></div>
      </section>
      <section class="section" aria-labelledby="url-heading">
        <span class="step">STEP 03</span><h2 id="url-heading">入会・退会の情報</h2>
        <div class="field"><label for="join_url">入会URL<span class="optional">任意</span></label>
          <input id="join_url" name="join_url" type="url" maxlength="2048" placeholder="https://…" aria-describedby="join_url-error"><span class="error" id="join_url-error"></span></div>
        <div class="field"><label for="cancel_url">退会URL<span class="optional">任意</span></label>
          <input id="cancel_url" name="cancel_url" type="url" maxlength="2048" placeholder="https://…" aria-describedby="cancel_url-error"><span class="error" id="cancel_url-error"></span></div>
        <div class="field"><label for="cancel_memo">退会に必要な情報<span class="optional">任意</span></label>
          <textarea id="cancel_memo" name="cancel_memo" maxlength="1000" placeholder="例：メールアドレスとパスワードの準備が必要" aria-describedby="memo-help cancel_memo-error"></textarea>
          <span class="helper" id="memo-help">パスワード自体は入力しないでください．必要な準備や手順だけを記録します．</span><span class="error" id="cancel_memo-error"></span></div>
      </section>
      <p class="notice" id="message" role="alert"></p>
      <button class="primary" id="submit" type="submit">この内容で登録する</button>
    </form>
    <section class="success" id="success" aria-labelledby="success-heading" hidden>
      <h2 id="success-heading">登録しました</h2><p id="success-detail"></p>
      <button class="text-button" type="button" id="another">続けて別のサブスクを追加する →</button>
    </section>
    <section class="section" aria-labelledby="saved-heading">
      <h2 id="saved-heading">このブラウザに登録したサブスク</h2>
      <div id="saved-list"></div><p class="helper" id="saved-status" role="status"></p>
      <button class="text-button" id="export" type="button" disabled>登録データをJSONで保存する ↓</button>
    </section>
  </main>
  <footer>サブマネ · 石井担当の登録画面</footer>
</div>
<script>
'use strict';
const STORAGE_KEY = 'submane.ishii.html.subscriptions.v1';
const SERVICES = [
  { id:'video-demo', name:'動画サービス（デモ）', aliases:['動画','video'], join_url:'https://example.com/video/join', cancel_url:'https://example.com/video/cancel', cancel_memo:'退会手続きにはメールアドレスとパスワードの準備が必要です．', plans:[{name:'月額プラン（デモ）',cycle:'monthly',amount:1000},{name:'年額プラン（デモ）',cycle:'yearly',amount:10000}] },
  { id:'music-demo', name:'音楽サービス（デモ）', aliases:['音楽','music'], join_url:'https://example.com/music/join', cancel_url:'https://example.com/music/cancel', cancel_memo:'契約した窓口を確認してください．', plans:[{name:'個人プラン（デモ）',cycle:'monthly',amount:800}] },
  { id:'book-demo', name:'読書サービス（デモ）', aliases:['読書','book'], join_url:'https://example.com/book/join', cancel_url:'https://example.com/book/cancel', cancel_memo:'パスワードの準備が必要です．', plans:[{name:'月額プラン（デモ）',cycle:'monthly',amount:500}] }
];
const FIELD_NAMES = ['name','plan_name','cycle','amount','joined_at','status','trial_ends_at','join_url','cancel_url','cancel_memo'];
const normalize = value => String(value).normalize('NFKC').toLocaleLowerCase('ja').trim();
function searchServices(keyword) {
  return SERVICES.filter(service => normalize([service.name,...service.aliases].join(' ')).includes(normalize(keyword)));
}
function validUrl(value) {
  if (!value) return true;
  if (/\s/.test(value) || value.length > 2048 || !/^https?:\/\//.test(value)) return false;
  try { const url = new URL(value); return !!url.hostname && !url.username && !url.password && url.port !== '0'; }
  catch { return false; }
}
function validTime(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
  if (!match) return false;
  const [year,month,day,hour,minute] = match.slice(1).map(Number);
  if (year < 1 || month < 1 || month > 12 || day < 1 || hour > 23 || minute > 59) return false;
  const date = new Date(0); date.setUTCFullYear(year,month-1,day); date.setUTCHours(hour,minute,0,0);
  return date.getUTCFullYear()===year && date.getUTCMonth()===month-1 && date.getUTCDate()===day;
}
function validate(raw) {
  const data = Object.fromEntries(FIELD_NAMES.map(key => [key,String(raw[key] ?? '').trim()]));
  const errors = {};
  for (const key of ['name','plan_name']) {
    if (!data[key]) errors[key] = '入力してください．';
    else if ([...data[key]].length > 100) errors[key] = '100文字以内で入力してください．';
  }
  const amount = data.amount.normalize('NFKC');
  if (!/^\d+$/.test(amount) || Number(amount) > 999999999) errors.amount = '0以上999999999以下の整数を円単位で入力してください．';
  else data.amount = Number(amount);
  if (!['monthly','yearly'].includes(data.cycle)) errors.cycle = '月額または年額を選択してください．';
  if (!['active','trial','cancelled'].includes(data.status)) errors.status = '契約状態を選択してください．';
  if (!validTime(data.joined_at)) errors.joined_at = '実在する入会日時を分単位で入力してください．';
  if (data.status === 'trial') {
    if (!validTime(data.trial_ends_at)) errors.trial_ends_at = 'トライアル終了日時を入力してください．';
    else if (validTime(data.joined_at) && data.trial_ends_at <= data.joined_at) errors.trial_ends_at = '入会日時より後の日時を入力してください．';
  } else data.trial_ends_at = '';
  for (const key of ['join_url','cancel_url']) if (!validUrl(data[key])) errors[key] = 'http://またはhttps://で始まるURLを入力してください．';
  if ([...data.cancel_memo].length > 1000) errors.cancel_memo = '1000文字以内で入力してください．';
  return {data,errors};
}
function readRecords(storage) {
  const records = JSON.parse(storage.getItem(STORAGE_KEY) || '[]');
  if (!Array.isArray(records) || records.some(item => !item || typeof item !== 'object' || typeof item.id !== 'string' || typeof item.name !== 'string' || !Number.isInteger(item.amount))) throw new Error('invalid records');
  return records;
}
globalThis.SubmaneRegistration = {validate,validUrl,validTime,searchServices,readRecords,STORAGE_KEY};

function initialize() {
  const el = id => document.getElementById(id);
  let selected = null, busy = false, records = [];
  function japaneseNow() {
    const parts = new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date());
    const values = Object.fromEntries(parts.map(part => [part.type,part.value]));
    return `${values.year}-${values.month}-${values.day}T${values.hour}:${values.minute}`;
  }
  function clearErrors() {
    FIELD_NAMES.forEach(key => { el(key).removeAttribute('aria-invalid'); el(key+'-error').textContent=''; });
    el('message').textContent='';
  }
  function applyPlan() {
    if (!selected) return;
    const plan = selected.plans[Number(el('preset').value)];
    el('plan_name').value=plan.name; el('cycle').value=plan.cycle; el('amount').value=plan.amount;
  }
  function choose(service) {
    if (busy) return;
    selected=service; clearErrors();
    ['name','join_url','cancel_url','cancel_memo'].forEach(key => { el(key).value=service[key]; });
    el('preset').replaceChildren(...service.plans.map((plan,index) => new Option(plan.name,String(index))));
    el('preset-field').hidden=false; applyPlan(); renderSearch();
    el('search-status').textContent='選択済み：'+service.name;
  }
  function renderSearch() {
    const matches=searchServices(el('search').value); el('results').replaceChildren();
    matches.forEach(service => {
      const button=document.createElement('button'); button.type='button'; button.className='service';
      button.setAttribute('aria-pressed',String(selected?.id===service.id));
      const icon=document.createElement('span'); icon.className='service-icon'; icon.textContent=service.name[0]; icon.setAttribute('aria-hidden','true');
      const text=document.createElement('span'); text.className='service-name'; text.textContent=service.name;
      const note=document.createElement('span'); note.className='service-note'; note.textContent='プラン・入会URL・退会URLを自動入力'; text.append(note);
      button.append(icon,text); button.addEventListener('click',()=>choose(service)); el('results').append(button);
    });
    el('search-status').textContent=matches.length ? `${matches.length}件のサービス` : '該当するサービスがありません．下の欄に手入力できます．';
  }
  function setTrial() {
    const trial=el('status').value==='trial'; el('trial-field').hidden=!trial;
    el('trial_ends_at').required=trial; if (!trial) el('trial_ends_at').value='';
  }
  function renderSaved() {
    el('saved-list').replaceChildren();
    records.forEach(item => {
      const row=document.createElement('div'); row.className='saved '+item.status;
      const name=document.createElement('strong'); name.textContent=item.name;
      const detail=document.createElement('span'); detail.textContent=`${item.cycle==='yearly'?'年額':'月額'} · ${item.amount.toLocaleString('ja-JP')}円 · ${{active:'契約中',trial:'無料トライアル中',cancelled:'解約済み'}[item.status] || '状態未設定'}`;
      row.append(name,detail); el('saved-list').append(row);
    });
    el('saved-status').textContent=records.length ? `${records.length}件を保存しています．` : 'まだ登録がありません．';
    el('export').disabled=!records.length;
  }
  el('search').addEventListener('input',renderSearch);
  el('preset').addEventListener('change',applyPlan);
  el('status').addEventListener('change',setTrial);
  el('manual').addEventListener('click',()=>{
    selected=null; clearErrors(); el('preset-field').hidden=true;
    ['name','plan_name','amount','join_url','cancel_url','cancel_memo'].forEach(key=>{ el(key).value=''; });
    renderSearch(); el('name').focus();
  });
  el('registration').addEventListener('submit',event=>{
    event.preventDefault(); if (busy) return; clearErrors();
    const raw=Object.fromEntries(FIELD_NAMES.map(key=>[key,el(key).value]));
    const {data,errors}=validate(raw);
    if (Object.keys(errors).length) {
      Object.entries(errors).forEach(([key,text])=>{ el(key).setAttribute('aria-invalid','true'); el(key+'-error').textContent=text; });
      el('message').textContent='入力内容を確認してください．'; el(Object.keys(errors)[0]).focus(); return;
    }
    busy=true; el('submit').disabled=true;
    try {
      const current=readRecords(localStorage);
      const id=globalThis.crypto?.randomUUID?.() || Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);
      const item={...data,id,service_id:selected?.id || '',icon:'',registered_at:new Date().toISOString(),next_payment_at:data.status==='trial'?data.trial_ends_at:null};
      localStorage.setItem(STORAGE_KEY,JSON.stringify([...current,item])); records=[...current,item]; renderSaved();
      el('success-detail').textContent=`${data.name} · ${data.cycle==='yearly'?'年額':'月額'} ${data.amount.toLocaleString('ja-JP')}円`;
      el('registration').hidden=true; el('success').hidden=false;
      el('search').disabled=true; el('manual').disabled=true; el('results').querySelectorAll('button').forEach(button=>{button.disabled=true;});
      el('success').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'center'});
    } catch {
      el('message').textContent='保存できませんでした．ブラウザの保存設定，空き容量，保存済みデータの形式を確認してください．入力内容は残っています．';
    } finally { busy=false; el('submit').disabled=false; }
  });
  el('another').addEventListener('click',()=>{
    el('registration').reset(); selected=null; clearErrors(); el('preset-field').hidden=true;
    el('joined_at').value=japaneseNow(); setTrial(); el('success').hidden=true; el('registration').hidden=false;
    el('search').disabled=false; el('manual').disabled=false; renderSearch(); el('search').focus();
  });
  el('export').addEventListener('click',()=>{
    const blob=new Blob([JSON.stringify(records,null,2)],{type:'application/json;charset=utf-8'});
    const url=URL.createObjectURL(blob); const link=document.createElement('a'); link.href=url; link.download='submane-html-subscriptions.json';
    document.body.append(link); link.click(); link.remove(); setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  el('joined_at').value=japaneseNow(); renderSearch(); setTrial();
  try { records=readRecords(localStorage); renderSaved(); }
  catch { el('saved-status').textContent='保存済みデータを読み取れません．ブラウザの保存設定またはデータ形式を確認してください．'; }
}
if (typeof document !== 'undefined') initialize();
</script>
</body>
</html>
```
