# 石井担当・全コード

ソース・テスト・HTMLを省略せず掲載しています．2026-10-05更新．

## pyproject.toml

```toml
[project]
name = "submane-ishii"
version = "0.1.0"
description = "サブマネ 石井担当機能"
requires-python = ">=3.12"
dependencies = ["flet[all]==1.0.3", "httpx==0.28.1"]

[project.optional-dependencies]
dev = ["pytest==9.1.1"]

[tool.flet]
org = "jp.ac.ibaraki.team.e1"
product = "サブマネ"
company = "Team E1"

[tool.flet.app]
path = "src"

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

## .gitignore

```text
.venv/
__pycache__/
.pytest_cache/
build/
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
& "$PSScriptRoot/.venv/Scripts/python.exe" -m pip install 'flet[all]==1.0.3' 'httpx==0.28.1' 'pytest==9.1.1'
if ($LASTEXITCODE -ne 0) { throw '依存ライブラリのインストールに失敗しました．' }
```

## src/api_client.py

```python
"""サーバ設計書v0.2対応の担当確認用APIと，独立したローカルデモ．"""
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


class ApiError(RuntimeError):
    """画面に表示できる保存・通信エラー．"""

    def __init__(self, message, *, status_code=None, code=None, details=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.details = details if isinstance(details, dict) else {}


class OfflineError(ApiError):
    """オンライン専用の登録・更新を実行できない．"""


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
            " ".join([service["name"], *service["aliases"]]))])

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

## src/components/service_icon.py

```python
"""無料トライアルと解約済みを一貫した見た目で表示する．"""
from zlib import crc32
import flet as ft
import theme


def service_icon(subscription, size=64, color_index=None):
    """解約済みは画像を含めグレー表示，トライアル中は時計を添える．"""
    cancelled = subscription.get("status") == "cancelled"
    if color_index is None:
        identity = str(subscription.get("service_id") or subscription.get("id") or subscription.get("name") or "?")
        color_index = crc32(identity.encode("utf-8"))
    color = theme.OFF_FILL if cancelled else theme.TILE_COLORS[color_index % len(theme.TILE_COLORS)]
    letter = ft.Text((subscription.get("name") or "?")[:1], size=26,
                     weight=ft.FontWeight.BOLD, color=theme.OFF_INK if cancelled else theme.SURFACE)
    visual = letter
    if subscription.get("icon"):
        visual = ft.Image(src=subscription["icon"], width=size, height=size,
                          fit=ft.BoxFit.COVER, border_radius=18, error_content=letter,
                          color=theme.OFF_FILL if cancelled else None,
                          color_blend_mode=ft.BlendMode.SATURATION if cancelled else None,
                          opacity=0.5 if cancelled else 1)
    tile = ft.Container(content=visual, width=size, height=size, bgcolor=color,
                        border_radius=18, alignment=ft.Alignment.CENTER)
    if subscription.get("status") != "trial":
        return tile
    return ft.Stack(width=size + 8, height=size + 8, controls=[
        tile,
        ft.Container(content=ft.Icon(ft.Icons.ACCESS_TIME, color=theme.SURFACE, size=16),
                     width=26, height=26, right=0, top=0, bgcolor=theme.TRIAL,
                     border_radius=13, alignment=ft.Alignment.CENTER),
    ])
```

## src/components/sort_selector.py

```python
"""一覧画面へ組み込める並び順選択部品．"""
import flet as ft
from logic.subscriptions import SORT_LABELS


def sort_selector(on_select, value="frequency", include_deadline=True):
    """解約済みを末尾にするsort_subscriptionsと合わせて使用する．"""
    return ft.Dropdown(label="並び順", value=value, on_select=on_select,
                       options=[ft.DropdownOption(key=key, text=text)
                                for key, text in SORT_LABELS.items()
                                if include_deadline or key != "deadline"])
```

## src/components/status_actions.py

```python
"""詳細画面に組み込む解約・再契約の状態変更部品．"""
from datetime import datetime
import inspect
import flet as ft
import theme
from api_client import ApiError
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
            item = await api.update_subscription(subscription["id"], patch)
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

## src/config.py

```python
"""実API接続を行う際の設定．URLは環境変数で指定する．"""
import os
from pathlib import Path

USE_DUMMY_DATA = os.getenv("SUBMANE_USE_DUMMY_DATA", "true").lower() == "true"
API_BASE_URL = os.getenv("SUBMANE_API_BASE_URL", "").rstrip("/")
DATA_FILE = Path(os.getenv(
    "SUBMANE_DATA_FILE",
    str(Path(os.getenv("FLET_APP_STORAGE_DATA", str(Path(__file__).resolve().parents[1] / "data")))
        / "subscriptions.json"),
))
```

## src/dummy_data.py

```python
"""定番サービスの仮マスタ．料金とURLは実サービスの現行情報ではない．"""
SERVICES = [
    {"id": "video-demo", "name": "動画サービス（デモ）", "aliases": ["動画", "video"],
     "join_url": "https://example.com/video/join", "cancel_url": "https://example.com/video/cancel",
     "cancel_memo": "退会手続きにはメールアドレスとパスワードの準備が必要です．",
     "plans": [{"name": "月額プラン（デモ）", "cycle": "monthly", "amount": 1000},
               {"name": "年額プラン（デモ）", "cycle": "yearly", "amount": 10000}]},
    {"id": "music-demo", "name": "音楽サービス（デモ）", "aliases": ["音楽", "music"],
     "join_url": "https://example.com/music/join", "cancel_url": "https://example.com/music/cancel",
     "cancel_memo": "契約した窓口を確認してください．",
     "plans": [{"name": "個人プラン（デモ）", "cycle": "monthly", "amount": 800}]},
    {"id": "book-demo", "name": "読書サービス（デモ）", "aliases": ["読書", "book"],
     "join_url": "https://example.com/book/join", "cancel_url": "https://example.com/book/cancel",
     "cancel_memo": "パスワードの準備が必要です．",
     "plans": [{"name": "月額プラン（デモ）", "cycle": "monthly", "amount": 500}]},
]
```

## src/logic/__init__.py

```python
"""石井担当の入力検証，並び替え，状態変更．"""
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
```

## src/theme.py

```python
"""home.htmlに合わせた共通デザイン定数．"""
GROUND = "#F3F5F4"
SURFACE = "#FFFFFF"
INK = "#14201C"
INK_SUB = "#4A5552"
LINE = "#D3D8D6"
ACCENT = "#0E6B5C"
ACCENT_SOFT = "#E0EFE9"
TRIAL = "#B45309"
OFF_FILL = "#D3D8D6"
OFF_INK = "#5A6360"
ERROR = "#B3261E"
GUTTER = 24
FONT = "Zen Kaku Gothic New"
TILE_COLORS = ("#7A2E3A", "#2F5D50", "#1F3A5F", "#8A4B14")
```

## src/views/__init__.py

```python
"""登録画面と状態変更の動作確認画面．"""
```

## src/views/preview.py

```python
"""担当機能を単独で確認する一覧と状態変更画面．チームのhome/detailとは別．"""
import flet as ft
import theme
from components.service_icon import service_icon
from components.sort_selector import sort_selector
from components.status_actions import status_actions
from logic.subscriptions import CYCLE_LABELS, STATUS_LABELS, sort_subscriptions


def preview_list(page, items, order, on_order, on_add, on_detail, notice=""):
    """登録結果・グレーアウト・並び順の動作確認用一覧を返す．"""
    active = sum(item["status"] != "cancelled" for item in items)
    trial = sum(item["status"] == "trial" for item in items)
    rows = []
    for item in sort_subscriptions(items, order):
        cancelled = item["status"] == "cancelled"
        rows.append(ft.Container(
            bgcolor=theme.SURFACE, border_radius=16, padding=14,
            on_click=lambda e, sub_id=item["id"]: on_detail(sub_id),
            content=ft.Row(spacing=14, controls=[
                service_icon(item),
                ft.Column(expand=True, spacing=4, controls=[
                    ft.Text(item["name"], weight=ft.FontWeight.BOLD,
                            color=theme.OFF_INK if cancelled else theme.INK),
                    ft.Text(f"{CYCLE_LABELS.get(item['cycle'], item['cycle'])} · {item['amount']:,}円", color=theme.INK_SUB),
                    ft.Text(STATUS_LABELS[item["status"]], size=12,
                            color=theme.TRIAL if item["status"] == "trial" else theme.INK_SUB),
                ]), ft.Icon(ft.Icons.CHEVRON_RIGHT, color=theme.INK_SUB),
            ])))
    return ft.Column(spacing=16, controls=[
        ft.Text("石井担当の動作確認", size=26, weight=ft.FontWeight.BOLD),
        ft.Text("登録・契約状態・アイコン表示・並び替えを確認できます．", color=theme.INK_SUB),
        ft.Text(notice, color=theme.ACCENT, visible=bool(notice)),
        ft.Button("サブスクを追加", icon=ft.Icons.ADD, height=48, bgcolor=theme.ACCENT,
                  color=theme.SURFACE, on_click=lambda e: on_add()),
        ft.Text(f"契約中 {active}件 / うちトライアル {trial}件 / 解約済み {len(items)-active}件"),
        sort_selector(on_order, value=order),
        ft.Text("期限順はAPIの次回支払日時またはトライアル終了日時を使用します．日時未取得の契約は後ろに表示します．",
                color=theme.INK_SUB, size=12, visible=order == "deadline"),
        *rows,
        ft.Text("まだ登録がありません．「サブスクを追加」から登録してください．", visible=not bool(items), color=theme.INK_SUB),
    ])


def preview_status(page, item, api, on_back, on_changed):
    """詳細担当への組み込み前に状態変更部品を確認する．"""
    return ft.Column(spacing=16, controls=[
        ft.TextButton("一覧に戻る", on_click=lambda e: on_back()),
        service_icon(item, size=72),
        ft.Text(item["name"], size=26, weight=ft.FontWeight.BOLD),
        ft.Text(STATUS_LABELS[item["status"]], color=theme.INK_SUB),
        ft.Text(f"{item['plan_name']} / {CYCLE_LABELS[item['cycle']]} / {item['amount']:,}円"),
        ft.Text("入会日時：" + str(item.get("joined_at") or "未取得")),
        ft.Text("トライアル終了：" + str(item.get("trial_ends_at") or "未取得"), visible=item["status"] == "trial"),
        ft.Text("退会に必要な情報", size=16, weight=ft.FontWeight.BOLD),
        ft.Text(item.get("cancel_memo") or "未登録", color=theme.INK_SUB),
        ft.Divider(color=theme.LINE), status_actions(page, item, api, on_changed),
    ])
```

## src/views/register.py

```python
"""石井担当：定番サービス検索と手入力によるサブスク登録画面．"""
import asyncio
from datetime import datetime
import flet as ft
import theme
from api_client import ApiClient, ApiError
from logic.subscriptions import JST, CYCLE_LABELS, STATUS_LABELS, ValidationError, validate_subscription


def register_view(page, api=None, on_saved=None, on_back=None):
    """pageのみでも生成でき，共通APIと遷移コールバックを注入できる．"""
    api = api or ApiClient()
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
            services = await api.search_services(search.value or "")
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
            item = await api.create_subscription(data)
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
    return ft.Column(spacing=16, controls=[
        back_button, ft.Text("サブスクを追加", size=26, weight=ft.FontWeight.BOLD, color=theme.INK),
        ft.Text("サービスを選ぶか，契約内容を手入力してください．定番の名称・URL・退会案内を変更する場合は手入力に切り替えてください．", color=theme.INK_SUB),
        search, search_button, results,
        manual_button, plans, *fields.values(), message, save_button,
    ])
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
import asyncio
import httpx
import pytest
from api_client import ApiClient, ApiError


def test_cookie_session_is_shared_across_requests():
    async def scenario():
        seen = []
        def handler(request):
            seen.append(request)
            if request.url.path == "/api/login":
                return httpx.Response(200, json={"ok": True}, headers={"set-cookie": "session=test; Path=/; HttpOnly; Secure"})
            return httpx.Response(200, json=[])
        async with httpx.AsyncClient(base_url="https://test.example/api/", transport=httpx.MockTransport(handler)) as session:
            api = ApiClient(use_dummy=False, base_url="https://test.example/api", http_session=session)
            await api.http_session().post("login", json={"email": "demo@example.com"})
            await api.search_services("動画")
            await api.list_subscriptions()
            assert seen[1].headers["cookie"] == "session=test"
            assert seen[2].headers["cookie"] == "session=test"
            assert "authorization" not in seen[2].headers
            await api.aclose()
            assert not session.is_closed
    asyncio.run(scenario())


@pytest.mark.parametrize("status", [401, 403, 500])
def test_http_errors_become_api_errors(status):
    async def scenario():
        async with httpx.AsyncClient(base_url="https://test.example/", transport=httpx.MockTransport(
                lambda request: httpx.Response(status, json={"error": "details"}))) as session:
            api = ApiClient(use_dummy=False, base_url="https://test.example", http_session=session)
            with pytest.raises(ApiError):
                await api.list_subscriptions()
    asyncio.run(scenario())
```

## tests/test_storage.py

```python
"""ローカル保存の永続化とデータ破損時の保護を確認する．"""
import asyncio
import pytest
from api_client import ApiClient, ApiError
from logic.subscriptions import cancellation_patch, reactivation_patch


def test_save_cancel_reactivate_and_reload(tmp_path):
    async def scenario():
        client = ApiClient(tmp_path / "data.json", use_dummy=True)
        item = await client.create_subscription({"name": "手入力", "plan_name": "年間", "cycle": "yearly",
                    "amount": "1200", "joined_at": "2026-01-31T12:00", "status": "active",
                    "join_url": "https://example.com/join", "cancel_url": "https://example.com/cancel"})
        cancelled = await client.update_subscription(item["id"], cancellation_patch())
        assert cancelled["status"] == "cancelled"
        assert cancelled["join_url"] == item["join_url"]
        active = await client.update_subscription(item["id"], reactivation_patch(cancelled, "2026-10-05T12:00"))
        assert active["id"] == item["id"]
        reloaded = await ApiClient(tmp_path / "data.json", use_dummy=True).list_subscriptions()
        assert len(reloaded) == 1 and reloaded[0]["joined_at"] == "2026-10-05T12:00"
    asyncio.run(scenario())


def test_corrupt_file_is_not_overwritten(tmp_path):
    file = tmp_path / "data.json"
    file.write_text("broken", encoding="utf-8")
    with pytest.raises(ApiError):
        asyncio.run(ApiClient(file, use_dummy=True).list_subscriptions())
    assert file.read_text(encoding="utf-8") == "broken"


def test_search_normalizes_full_width_and_does_not_mutate_master(tmp_path):
    async def scenario():
        client = ApiClient(tmp_path / "data.json", use_dummy=True)
        values = await client.search_services("ＶＩＤＥＯ")
        assert len(values) == 1
        values[0]["name"] = "書き換え"
        assert (await client.search_services("video"))[0]["name"] != "書き換え"
    asyncio.run(scenario())
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
from views.preview import preview_list, preview_status


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
        results.controls[0].on_click(None)
        assert fields["サービス名 *"].value == "動画サービス（デモ）"
        assert fields["1回の支払額（円） *"].value == "1000"
        fields["定番サービスのプラン"].value = "1"
        fields["定番サービスのプラン"].on_select(None)
        assert fields["更新周期 *"].value == "yearly"
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
    assert isinstance(service_icon(item), ft.Container)
    assert isinstance(service_icon({**item, "status": "trial"}), ft.Stack)
    assert isinstance(service_icon({**item, "status": "cancelled", "icon": "https://example.com/icon.png"}), ft.Container)
    assert preview_list(page, [item], "frequency", lambda e: None, lambda: None, lambda i: None)
    assert preview_status(page, item, ApiClient(tmp_path / "records.json"), lambda: None, lambda i: None)


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
    assert preview_status(PageStub(), item, ApiClient(tmp_path / "records.json"), lambda: None, lambda i: None)



def test_icon_color_stays_with_subscription_when_order_changes():
    item = {"id": 42, "name": "試作", "status": "active"}
    other = {"id": 50, "name": "別契約", "status": "active"}
    initial = {value["id"]: service_icon(value).bgcolor for value in [item, other]}
    reordered = {value["id"]: service_icon(value).bgcolor for value in [other, item]}
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
