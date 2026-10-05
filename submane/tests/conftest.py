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
