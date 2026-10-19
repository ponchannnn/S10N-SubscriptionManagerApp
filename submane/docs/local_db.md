# サブマネ 端末内ローカルDB 実装メモ

| 項目 | 内容 |
|---|---|
| 対象 | `src/local_db.py` と、それを呼ぶ `src/api_client.py` の該当部分 |
| 元の設計書 | `docs/client_db.md`(池田 瑞基 作, v0.2) |
| 位置づけ | 元の設計書をベースに、develop ブランチの現状(ダミーデータ中心、`src/logic/` で日付・金額を計算する方針)に合わせて実装したもの |

画面担当の人は、**§4(画面から見た使い方)だけ読めば十分**です(元の設計書と同じ考え方)。

---

## 1. 元の設計書との違い

`docs/client_db.md` が書かれた時点から、以下の点が実際には変わっています。「md通りにすると都合が合わない」部分なので、ここに理由を残します。

| # | 元の設計(`client_db.md`) | 実装 | 理由 |
|---|---|---|---|
| 1 | 次回支払日・支払い見込みはAPIが計算し、そのまま保存・表示する(`src/logic/` は作らない) | `logic/dates.py` / `logic/payments.py` でアプリ側が計算する | README 7章の決定が「アプリ側で計算する」に変わった(small/kominato・tamatsukuriの実装時点)。計算はキャッシュしたサブスク一覧から毎回その場で出せるので、`summary_cache` テーブルと `get_summary()` / `save_summary()` / `load_summary()` は**作っていない**。内訳画面はオフラインでも `subscriptions_cache` を使って同じ計算をやり直せば十分 |
| 2 | `subscriptions_cache` に `next_payment_at` 列を持つ | 持たない(`id` / `position` / `status` / `data` のみ) | 次回支払日は①の理由で保存せず都度計算するため、列として持つと「本日時点で計算した値」が古くなり続けるだけで使い道がない |
| 3 | 起動時に `GET /me` でCookieの有効性を確認し、401ならログイン画面へ | 確認しない。保存したCookieが**あるかどうか**だけで `is_logged_in()` を決める | サーバ側の `/me` 相当のエンドポイントがまだ無い。401が返ってきたときの `clear_user_data()` は実装済みなので、実際に無効なCookieで通信したタイミングで検知される |
| 4 | 例外は `ApiError` と `OfflineError` の2種類 | 同じ2種類だが、`OfflineError` は `ApiError` のサブクラスにした | 既存の画面(`register.py`・`status_actions.py`・`breakdown.py`など)はすべて `except ApiError` で書かれているため、サブクラスにすることで既存コードを直さずに済ませた |
| 5 | `src/config.py` に `FLET_APP_STORAGE_DATA` 等の記載なし(`local_db.py` 側で読む想定) | そのまま `local_db.py` 内で `os.getenv("FLET_APP_STORAGE_DATA")` を読む | 設計書どおり。`config.py` に項目を増やす必要はなかった |

上記以外(テーブルの役割、`app_state` のキー、`api_client.py` の関数とキャッシュの対応)は元の設計書どおりです。

---

## 2. ローカルDBの役割(変更なし)

| 役割 | 内容 |
|---|---|
| ① ログイン状態を残す | セッションCookieを保存し、アプリを再起動しても再ログインしなくて済むようにする |
| ② 前回の表示を残す | 通信できないとき・起動直後に、前回取得した一覧・詳細を表示する |
| ③ 設定を残す | 年額プランの計上方法(`billing` / `average`)など、端末ごとの設定 |

- 登録・編集・解約・削除は**オンラインのときだけ**行う。通信できないときはエラーを出し、端末に溜めて後で送る仕組みは作らない
- `USE_DUMMY_DATA = True`(今のデフォルト)の間は、`local_db.py` はログイン状態・設定の読み書き以外には使われない。一覧・サービスのキャッシュが実際に効くのは、本物のAPIに繋いだ(`USE_DUMMY_DATA = False` にした)あと

## 3. 使う技術

| 項目 | 内容 |
|---|---|
| DB | SQLite(Python標準の `sqlite3`) |
| ファイルの場所 | 環境変数 `FLET_APP_STORAGE_DATA` のフォルダの `submane.db`。未設定のとき(`flet run` のPCなど)は `~/.submane/submane.db` |
| 接続 | 関数を呼ぶたびに開いて閉じる(接続を使い回さない) |
| スキーマの更新 | `PRAGMA user_version` で版を管理し、起動時に版が変わっていればテーブルを作り直す(キャッシュなので消えても困らない) |

## 4. テーブル定義

```sql
CREATE TABLE IF NOT EXISTS app_state (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS subscriptions_cache (
  id       INTEGER PRIMARY KEY,
  position INTEGER NOT NULL,   -- 登録順(API が返した順番)
  status   TEXT    NOT NULL,   -- active / trial / cancelled
  data     TEXT    NOT NULL    -- サブスク1件のJSON全体
);

CREATE TABLE IF NOT EXISTS services_cache (
  id        INTEGER PRIMARY KEY,
  name      TEXT NOT NULL,
  name_kana TEXT,
  data      TEXT NOT NULL      -- サービス1件のJSON全体(プラン含む)
);
```

`app_state` で使うキー:

| key | value の例 | 消すタイミング |
|---|---|---|
| `session_cookie` | APIが返したCookieの値 | ログアウト・401を受けたとき |
| `user_email` | `user@example.com` | ログアウト時 |
| `yearly_mode` | `billing`(更新月に全額) / `average`(月割り) | 消さない(端末の設定) |
| `subscriptions_fetched_at` | `2026-10-05T12:00+09:00` | ログアウト時 |

## 5. `api_client.py` との対応(画面から見た使い方)

画面は今までどおり **`api_client.py` の関数だけ**を呼ぶ。ローカルDBを使うかどうかは `api_client.py` の中で決まり、画面は意識しない。

| 関数 | 通信できたとき | 通信できないとき(`OfflineError`) |
|---|---|---|
| `list_subscriptions()` | `local_db.replace_subscriptions()` して返す | `local_db.load_subscriptions()` を返す(キャッシュが空なら例外を投げ直す) |
| `get_subscription(sub_id)` | `local_db.upsert_subscription()` して返す | `local_db.load_subscription()` を返す(無ければ例外を投げ直す) |
| `create_subscription(data)` / `update_subscription(sub_id, data)` | `local_db.upsert_subscription()` して返す | そのまま失敗(あとで送る仕組みは作らない) |
| `delete_subscription(sub_id)` | `local_db.delete_subscription()` | そのまま失敗 |
| `search_services(keyword)` | そのまま返す(キャッシュへの書き込みは `refresh_services()` が担当) | `local_db.search_services()` を返す |
| `sign_up` / `log_in` | Cookie・メールアドレスを保存し、`refresh_services()` を1回呼ぶ | エラー |
| `log_out()` | `local_db.clear_user_data()` | それでも `clear_user_data()` してログイン画面へ |

追加した関数:

| 関数 | 内容 |
|---|---|
| `is_logged_in()` | `USE_DUMMY_DATA` が `False` のときは、保存したCookieの有無も見る(§1-3のとおり `GET /me` での確認はまだしない) |
| `last_updated()` | `subscriptions_fetched_at` を返す。通信できず前回の表示を出しているときの「最終更新」表示に使える(未使用。使うかは画面担当に任せる) |
| `get_yearly_mode()` / `set_yearly_mode(mode)` | 年額の計上方法。**`views/breakdown.py` で実際に使用中**(以前は `page.session.store` でアプリを閉じるまでしか覚えていなかったが、端末に保存するよう変更した) |
| `refresh_services()` | ログイン・会員登録の直後に1回呼び、定番サービスのマスタを `local_db.replace_services()` で保存する |

## 6. テスト

`tests/test_local_db.py` で、一時フォルダのDBを使って確認している:

- 一覧を保存すると、APIの順番どおりに読み出せる(`subscriptions_fetched_at` も保存される)
- ログアウトしても `yearly_mode` などの設定は残る
- `upsert_subscription` で新しい1件が末尾に入り、既存の並び順は変わらない。既存IDの更新は位置を保ったまま内容だけ変わる
- `delete_subscription` は指定した1件だけを消す
- `search_services` は名前・読みの部分一致で検索でき、該当なしなら空リストを返す
- `init_db()` を同じパスで複数回呼んでも、2回目以降は既存データを壊さない

`api_client.py` 側のオフライン挙動(接続できないときにキャッシュへ切り替わる・キャッシュも無いときは例外を投げ直す)は `tests/test_api_session.py` の仕組み(`httpx.MockTransport` を `api_client._client` に差し替える)を使えば同様にテストできる。現時点では `USE_DUMMY_DATA = True` のままなので自動テストには含めていない。

## 7. 未決事項

| # | 項目 | 備考 |
|---|---|---|
| 1 | `FLET_APP_STORAGE_DATA` が固定したFletのバージョン(1.0.3)で使えるか | APKビルド担当が確認(元の設計書から引き継ぎ、未検証) |
| 2 | `GET /me` 相当のエンドポイントができたら、起動時のCookie有効性確認を追加するか | API側の仕様が決まったら対応(§1-3) |
| 3 | `last_updated()` を画面(ホーム・一覧系)の「最終更新」表示に使うかどうか | 画面担当に任せる。関数自体は用意済み |
