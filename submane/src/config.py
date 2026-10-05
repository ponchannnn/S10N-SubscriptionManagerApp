"""アプリ全体の設定。APIのURLなどはここだけで管理する。"""

# True の間はAPIを呼ばず、dummy_data.py の内容で動く
USE_DUMMY_DATA = True

# APIができたら設定する(末尾の / は付けない)
API_BASE_URL = "https://<APIのURL>"

# APIの応答を待つ秒数
REQUEST_TIMEOUT = 10.0

# ダミーデータで動かすとき、最初からログイン済みとして扱うか
# (False にすると起動時に会員登録・ログイン画面が出る)
DUMMY_START_LOGGED_IN = True
