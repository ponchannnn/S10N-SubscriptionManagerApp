# クライアント↔サーバー 実接続確認メモ

`submane`(Flet, Python)から`mane_server`(Rails API)へ実際に接続して動作確認した結果と、
そのために直した内容のまとめです。ブランチは [`fix/client-api-connection`](#このブランチについて) です。

## 結論

直す前は**ほぼ動きませんでした**。`api_client.py`は`mane_server/server_db_api.md`が確定する前に
仮で書かれたパス・形のままだったため、エンドポイント・HTTPメソッド・レスポンスの形・項目名が
サーバーの実装と食い違っていました。全部直して、実際に動くサーバーに対して一通り確認済みです。

## 見つかった問題と直した内容

| # | 問題 | 直した内容 |
|---|---|---|
| 1 | エンドポイントのパスが違う(`/api/auth/register`等) | `/api/v1/signup`等、`server_db_api.md` §6のパスに合わせた |
| 2 | HTTPメソッドが違う | ログアウト: POST→DELETE、更新: PUT→PATCH |
| 3 | **レスポンスの形違い(一番深刻)** | `GET /subscriptions`は`{"subscriptions": [...], "server_time": ...}`、`GET /services`は`{"services": [...]}`と配列をラップしている。クライアントは配列そのものとして扱っていたため`TypeError`で落ちていた |
| 4 | 登録・更新時の項目名変換が未実装 | `_to_api_subscription()`が素通しだったので、サーバーが要求する「定番サービス参照(`service_id`)」と「カスタム入力(`custom_name`等)」の形に変換する処理を実装した |
| 5 | `trial_end_at`/`trial_ends_at`の表記ゆれ | サーバーのキー名は`trial_ends_at`(sあり)。読み取り側のキー名を直した(トライアル終了日が常にnullになっていた) |
| 6 | エラーメッセージがコード番号だけだった | `{"error": {"message": ...}}`(doc §5)の文言を使うようにした |

直したファイル: `submane/src/api_client.py`, `submane/tests/test_api_session.py`

## 実際にローカルで繋いで確認した手順

1. `mane_server`を起動: `cd mane_server && docker compose up -d`
2. `submane/src/config.py`の`API_BASE_URL`を一時的に`http://localhost:3000`、`USE_DUMMY_DATA`を`False`にする(**コミットはしない**。普段の開発はダミーデータのままでよい)
3. `demo@example.com` / `password123`(`db/seeds.rb`で入っているデモユーザー)でログイン→一覧取得→サービス検索→登録(定番サービス選択・カスタム入力の両方)→解約→再契約→削除→サーバーを止めてオフラインキャッシュへの切り替わりを確認→ログアウト、まで一通り確認した

## 本番で切り替えるとき

`submane/src/config.py`の2行を変える。

```python
USE_DUMMY_DATA = False
API_BASE_URL = "https://<APIの本当のURL>"   # 末尾の / は付けない
```

ローカルのRailsに繋ぐだけなら `http://localhost:3000` でよい(Railsを`docker compose up`で先に起動しておくこと)。

## まだ残っている/今回の対象外のこと

- **アイコン画像**: `mane_server/docs/icons.md`で依頼中。画像が揃うまでは`icon`のURLが404になる
- **`GET /summary`はクライアントから一度も呼んでいない**: `submane`の内訳画面(`breakdown.py`)は`logic/payments.py`で自前に計算しており、サーバーの`/summary`を呼ぶ設計になっていない。そのため、年額の計上方法の呼び方がクライアント側(`"billing"`/`"average"`、`api_client.get_yearly_mode()`)とサーバー側(`"lump"`/`"prorated"`、`server_db_api.md` §6.6)で違う名前になっているが、**クライアントが`/summary`を呼ばない限りこの食い違いは実害がない**。将来サーバーの計算に乗り換える場合は、ここの名前の変換が必要になる
- 会員登録・ログイン画面(`views/account.py`)はまだスタブのままなので、`sign_up`/`log_in`/`log_out`は画面からはまだ呼ばれていない(今回は`api_client`の関数を直接呼んで確認した)

## このブランチについて

このブランチ(`fix/client-api-connection`)は`develop`から作成しています。元は`server-db-api`ブランチ
(Railsサーバー本体の作業)の最後のコミットとして入れてしまいましたが、サーバーとクライアントで
別の変更なのでブランチを分けました。`server-db-api`はRailsサーバー側の作業のみに戻しています。

**次にやること**: このブランチを`develop`にマージする(サーバー側の作業は`server-db-api`で別途進行中)。
