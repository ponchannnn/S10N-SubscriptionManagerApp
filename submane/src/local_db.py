"""端末内の SQLite(ログイン状態・設定・前回取得したデータのキャッシュ)。

docs/local_db.md(元の設計: docs/client_db.md)の実装。呼ぶのは api_client.py だけにし、
画面(views/)からは直接使わない。
"""

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

SCHEMA_VERSION = 1
_db_path: Path | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_state (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS subscriptions_cache (
  id INTEGER PRIMARY KEY, position INTEGER NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS services_cache (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, name_kana TEXT, data TEXT NOT NULL);
"""

# ログアウトしても残すキー(端末の設定)
_KEEP_ON_LOGOUT = {"yearly_mode"}


def _default_path() -> Path:
    """DBファイルの場所を決める。"""
    base = os.getenv("FLET_APP_STORAGE_DATA")
    folder = Path(base) if base else Path.home() / ".submane"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "submane.db"


def init_db(path: Path | None = None) -> None:
    """起動時に1回呼ぶ。テストでは一時ファイルのパスを渡す。"""
    global _db_path
    _db_path = path or _default_path()
    with closing(sqlite3.connect(_db_path)) as con, con:
        version = con.execute("PRAGMA user_version").fetchone()[0]
        if version != SCHEMA_VERSION:
            # キャッシュなので、版が変わったら作り直す(設定は消える)
            for table in ("app_state", "subscriptions_cache", "services_cache"):
                con.execute(f"DROP TABLE IF EXISTS {table}")
        con.executescript(_SCHEMA)
        con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _connect() -> sqlite3.Connection:
    """呼ぶたびに新しい接続を開く(スレッドをまたいで使い回さない)。"""
    if _db_path is None:
        raise RuntimeError("init_db() を先に呼んでください")
    con = sqlite3.connect(_db_path)
    con.row_factory = sqlite3.Row
    return con


# ---------- ログイン状態・設定 ----------

def get_state(key: str, default: str | None = None) -> str | None:
    """app_state から値を読む。"""
    with closing(_connect()) as con:
        row = con.execute("SELECT value FROM app_state WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_state(key: str, value: str | None) -> None:
    """app_state に値を書く。None なら削除。"""
    with closing(_connect()) as con, con:
        if value is None:
            con.execute("DELETE FROM app_state WHERE key = ?", (key,))
        else:
            con.execute(
                "INSERT INTO app_state (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )


def clear_user_data() -> None:
    """ログアウト・401 のときに呼ぶ。設定以外をすべて消す。"""
    keep = ",".join("?" * len(_KEEP_ON_LOGOUT))
    with closing(_connect()) as con, con:
        con.execute(f"DELETE FROM app_state WHERE key NOT IN ({keep})", tuple(_KEEP_ON_LOGOUT))
        con.execute("DELETE FROM subscriptions_cache")
        con.execute("DELETE FROM services_cache")


# ---------- 契約 ----------

def replace_subscriptions(items: list[dict], fetched_at: str) -> None:
    """一覧を丸ごと置き換える(GET /subscriptions の結果)。"""
    with closing(_connect()) as con, con:
        con.execute("DELETE FROM subscriptions_cache")
        con.executemany(
            "INSERT INTO subscriptions_cache (id, position, status, data) VALUES (?, ?, ?, ?)",
            [(s["id"], i, s["status"], json.dumps(s, ensure_ascii=False))
             for i, s in enumerate(items)],
        )
        # set_state() は別接続を開くため、同じトランザクション内では直接書く
        con.execute(
            "INSERT INTO app_state (key, value) VALUES ('subscriptions_fetched_at', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (fetched_at,),
        )


def upsert_subscription(item: dict) -> None:
    """登録・編集が成功したあと、その1件だけ反映する。"""
    with closing(_connect()) as con, con:
        row = con.execute("SELECT position FROM subscriptions_cache WHERE id = ?", (item["id"],)).fetchone()
        if row:
            position = row["position"]
        else:
            position = con.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM subscriptions_cache").fetchone()[0]
        con.execute(
            "INSERT OR REPLACE INTO subscriptions_cache (id, position, status, data) VALUES (?, ?, ?, ?)",
            (item["id"], position, item["status"], json.dumps(item, ensure_ascii=False)),
        )


def delete_subscription(sub_id) -> None:
    """削除が成功したあと、その1件を消す。"""
    with closing(_connect()) as con, con:
        con.execute("DELETE FROM subscriptions_cache WHERE id = ?", (sub_id,))


def load_subscriptions() -> list[dict]:
    """前回取得した一覧(登録順)。"""
    with closing(_connect()) as con:
        rows = con.execute("SELECT data FROM subscriptions_cache ORDER BY position").fetchall()
    return [json.loads(r["data"]) for r in rows]


def load_subscription(sub_id) -> dict | None:
    """前回取得した1件。"""
    with closing(_connect()) as con:
        row = con.execute("SELECT data FROM subscriptions_cache WHERE id = ?", (sub_id,)).fetchone()
    return json.loads(row["data"]) if row else None


# ---------- 定番サービス ----------

def replace_services(items: list[dict]) -> None:
    """マスタを丸ごと置き換える(GET /services の q なしの結果)。"""
    with closing(_connect()) as con, con:
        con.execute("DELETE FROM services_cache")
        con.executemany(
            "INSERT INTO services_cache (id, name, name_kana, data) VALUES (?, ?, ?, ?)",
            [(s["id"], s["name"], s.get("name_kana"), json.dumps(s, ensure_ascii=False)) for s in items],
        )


def search_services(keyword: str) -> list[dict]:
    """オフライン時の名称検索(名前・読みの部分一致)。"""
    like = f"%{keyword}%"
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT data FROM services_cache WHERE name LIKE ? OR name_kana LIKE ? ORDER BY name",
            (like, like),
        ).fetchall()
    return [json.loads(r["data"]) for r in rows]
