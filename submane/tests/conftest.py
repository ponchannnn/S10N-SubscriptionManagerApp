"""api_client・local_db はテスト間で共有される状態を持つので，テストごとに初期化する。"""
import copy

import pytest

import api_client
import config
import dummy_data
import local_db


@pytest.fixture(autouse=True)
def reset_dummy_store(tmp_path, monkeypatch):
    """local_db を一時フォルダのDBで初期化し、api_client のダミー一覧・ログイン状態を初期値に戻す。

    config.USE_DUMMY_DATA/API_BASE_URL は本物のAPIに繋ぐ設定に変えて開発することもあるので、
    テストはそのときの config.py の内容に関わらず常にダミーモードを前提にする
    (本物のAPIを使う挙動を確認したいテストは、そのテスト自身で上書きする)。
    """
    monkeypatch.setattr(config, "USE_DUMMY_DATA", True)
    local_db.init_db(tmp_path / "test.db")
    api_client._dummy_subs = copy.deepcopy(dummy_data.SUBSCRIPTIONS)
    api_client._logged_in = True
    api_client._client = None
    api_client._session_restored = False
    yield
