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
