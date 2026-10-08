"""api_client・local_db はテスト間で共有される状態を持つので，テストごとに初期化する。"""
import copy

import pytest

import api_client
import dummy_data
import local_db


@pytest.fixture(autouse=True)
def reset_dummy_store(tmp_path):
    """local_db を一時フォルダのDBで初期化し、api_client のダミー一覧・ログイン状態を初期値に戻す。"""
    local_db.init_db(tmp_path / "test.db")
    api_client._dummy_subs = copy.deepcopy(dummy_data.SUBSCRIPTIONS)
    api_client._logged_in = True
    api_client._client = None
    api_client._session_restored = False
    yield
