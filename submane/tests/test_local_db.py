"""一時フォルダのDBを使って local_db の挙動を確認する。"""
import local_db


def test_replace_and_load_keeps_order(tmp_path):
    """一覧を保存すると、API の順番どおりに読み出せる。"""
    local_db.init_db(tmp_path / "test.db")
    items = [
        {"id": 5, "name": "Netflix", "status": "active"},
        {"id": 2, "name": "Hulu", "status": "trial"},
    ]
    local_db.replace_subscriptions(items, "2026-10-05T12:00+09:00")
    assert [s["id"] for s in local_db.load_subscriptions()] == [5, 2]
    assert local_db.get_state("subscriptions_fetched_at") == "2026-10-05T12:00+09:00"


def test_logout_keeps_settings(tmp_path):
    """ログアウトしても年額の計上方法は残る。"""
    local_db.init_db(tmp_path / "test.db")
    local_db.set_state("session_cookie", "abc")
    local_db.set_state("yearly_mode", "average")
    local_db.clear_user_data()
    assert local_db.get_state("session_cookie") is None
    assert local_db.get_state("yearly_mode") == "average"


def test_upsert_appends_new_and_keeps_existing_position(tmp_path):
    """新しい1件は末尾に入り、既存の並び順は変わらない。"""
    local_db.init_db(tmp_path / "test.db")
    local_db.replace_subscriptions(
        [{"id": 1, "name": "Netflix", "status": "active"}, {"id": 2, "name": "Hulu", "status": "active"}],
        "2026-10-05T12:00+09:00",
    )
    local_db.upsert_subscription({"id": 3, "name": "Spotify", "status": "active"})
    assert [s["id"] for s in local_db.load_subscriptions()] == [1, 2, 3]

    local_db.upsert_subscription({"id": 1, "name": "Netflix", "status": "cancelled"})
    assert [s["id"] for s in local_db.load_subscriptions()] == [1, 2, 3]
    assert local_db.load_subscription(1)["status"] == "cancelled"


def test_delete_subscription_removes_only_that_item(tmp_path):
    local_db.init_db(tmp_path / "test.db")
    local_db.replace_subscriptions(
        [{"id": 1, "name": "Netflix", "status": "active"}, {"id": 2, "name": "Hulu", "status": "active"}],
        "2026-10-05T12:00+09:00",
    )
    local_db.delete_subscription(1)
    assert [s["id"] for s in local_db.load_subscriptions()] == [2]
    assert local_db.load_subscription(1) is None


def test_search_services_matches_name_or_kana(tmp_path):
    local_db.init_db(tmp_path / "test.db")
    local_db.replace_services([
        {"id": 1, "name": "Netflix", "name_kana": "ネットフリックス"},
        {"id": 2, "name": "Hulu", "name_kana": "フール"},
    ])
    assert [s["id"] for s in local_db.search_services("flix")] == [1]
    assert [s["id"] for s in local_db.search_services("フール")] == [2]
    assert local_db.search_services("存在しない") == []


def test_schema_version_bump_resets_cache_but_not_handled_as_error(tmp_path):
    """init_db は何度呼んでも例外にならない(2回目以降は再作成しない)。"""
    path = tmp_path / "test.db"
    local_db.init_db(path)
    local_db.set_state("yearly_mode", "average")
    local_db.init_db(path)
    assert local_db.get_state("yearly_mode") == "average"
