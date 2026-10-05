# 石井担当：設計とチームの共通コードへの統合

更新README2.mdとスクラム文書のプロジェクト計画ver.2（9/28）を参照しています．旧計画では担当が異なるため，ver.2を優先します．登録画面は10/5〜10/12，名称検索・定番サービス選択は10/13〜10/18，解約・再契約とグレーアウトは10/19〜10/24，並び替えは10/25〜10/28が計画期間です．

## そのまま移せる担当コード

| ファイル | 内容 |
|---|---|
| src/views/register.py | サブスク登録画面 |
| src/logic/subscriptions.py | 入力検証・状態変更・並び替え |
| src/components/status_actions.py | 詳細画面に追加する解約・再契約の操作 |
| src/components/sort_selector.py | ホームなどの並び順選択 |
| src/components/service_icon.py | グレーアウトと時計の表示，共通部品担当と統合 |
| tests/ | 担当ロジックの検証 |

main.py，views/preview.pyは動作確認用です．チームのmain.py，home.py，detail.pyを置き換える必要はありません．theme.py，config.py，api_client.py，dummy_data.pyは共通コードが未完成の間に使う仮実装です．正式な共通コードができたら，必要なインターフェースを担当者と合わせてください．

## 登録画面

register_viewはpageだけを渡しても生成できます．共通APIと保存後の遷移を渡す例です．

```python
from views.register import register_view

content = register_view(
    page,
    api=api,
    on_saved=lambda item: page.navigate('/'),
    on_back=lambda: page.navigate('/'),
)
```

共通APIにはasyncメソッド `search_services(keyword)` と `create_subscription(data)` が必要です．保存後のon_savedは同期・asyncのいずれも使用できます．

## ホームの並び替えとアイコン

```python
from logic.subscriptions import sort_subscriptions
from components.service_icon import service_icon

ordered = sort_subscriptions(subscriptions, 'frequency')
icons = [service_icon(item, color_index=index) for index, item in enumerate(ordered)]
```

orderはfrequency，registered，deadlineです．登録順はregistered_atを優先し，ない場合はAPIから受け取った順序を維持します．どの順序でも解約済みを末尾にします．期限順はnext_payment_at，トライアルで未取得ならtrial_ends_atを使用します．通常契約で日時がない場合は他の契約中データの後ろに置きます．この部品は次回支払日を計算しません．

## 詳細の状態変更

```python
from components.status_actions import status_actions

controls = status_actions(page, subscription, api, on_changed=refresh_detail)
```

共通APIにはasyncメソッド `update_subscription(id, patch)` が必要です．on_changedには保存後の辞書を渡します．成功後にホーム・期限・内訳を再取得してください．公式URLを開いただけでは状態は変えません．再契約では入会日時を更新してnext_payment_atをNoneにします．API側は更新後の新しい日付を返す仕様にしてください．

## 仮API契約

正式な仕様ではありません．接続先・認証・フィールド名・応答構造をAPI担当と確認してから利用してください．

| メソッド | パス（仮） | 応答（仮） |
|---|---|---|
| GET | services?q=名称 | サービス辞書の配列 |
| GET | subscriptions | サブスク辞書の配列 |
| GET | subscriptions/{id} | サブスク辞書 |
| POST | subscriptions | 作成後のサブスク辞書 |
| PATCH | subscriptions/{id} | 更新後のサブスク辞書 |

サービス辞書はid，name，icon（任意），join_url，cancel_url，cancel_memo，plansを持ち，plansはname，cycle，amountの辞書配列です．サブスクの必須項目はREADME2.mdに合わせてname，plan_name，cycle，amount，joined_at，statusです．追加項目はservice_id（任意），trial_ends_at，registered_atです．joined_atとtrial_ends_atは日本時間の `YYYY-MM-DDTHH:MM`，next_payment_atとregistered_atはISO 8601を想定しています．画面にパスワードそのものは持ちません．

```powershell
$env:SUBMANE_USE_DUMMY_DATA = 'false'
$env:SUBMANE_API_BASE_URL = 'https://API担当から指定されたURL'
.\.venv\Scripts\python.exe .\src\main.py
```

URLやCookieをソースに直接書かず，ログイン担当と同一のhttpx.AsyncClientを共有してください．ApiClientは通信のたびにセッションを作り直さず，サーバのSet-Cookieを保持して後続リクエストに送信します．AuthorizationのBearerトークンは使用しません．ログイン担当が先に作成したAsyncClientはApiClient(http_session=client)として渡せます．ApiClientが生成したセッションでログインする場合はapi.http_session()を使用します．ログインAPIのパス・CSRF対策・セッション期限は正式仕様を待ちます．ブラウザのCookieをhttpxが自動共有するわけではありません．共有対象はアプリ内のHTTPセッションです．

仮APIはPOST失敗を自動で再送しません．正式APIで通信断時の重複登録を防ぐ場合は，API担当と冪等キーの仕様を決める必要があります．不要になったApiClientはawait api.aclose()で終了します．外部から渡したセッションは呼び出し元が終了します．

## 担当外の機能

会員登録・ログイン，次回支払日計算，円グラフと金額集計，期限画面，Androidのビルド設定完成，複数端末同期は該当担当者との統合が必要です．この実装で変更が必要なのは，ホームで並び替えとアイコン部品を使う箇所，詳細でstatus_actionsを表示する箇所，mainで登録画面へ遷移する箇所です．

2026-10-05にユーザ確認済み：正式なDB・API仕様のMarkdownは未完成です．石井担当には日付計算を追加せず，担当者の計算結果を受け取ります．READMEの計算場所の食い違いはこの方針で扱います．

## 更新READMEの確認結果

前版と比べ，HTTPS公開，Cookie／Session認証，担当者別のdocs/メモ，トライアル終了を次回支払日とすること，年額計上方式を選択可能とすること，手動での解約済み切り替え，APIからのアイコン取得，利用継続判断の見送りが追記されています．石井担当の割当は変わっていません．

スクラム文書では旧計画とver.2が同居しています．最新のver.2を優先しており，プロダクトロードマップの作成日欄には2025年表記の残存があります．資料を修正する場合は計画の内容を基準に年を確認してください．また，HTTPS公開の欄はチェック済みですが，具体的なAPI URLはまだ掲載されていません．

## 検証記録

Python 3.14.4，Flet 1.0.3で自動テスト32件が成功しました．登録画面のイベントから検索・定番選択・プラン変更・入力エラー・保存まで，状態変更の完了確認・解約・再契約，Cookieの持ち回り，HTTPエラー，JSON保存を検証しています．Web起動のHTTP 200とフォント配信も確認しました．ブラウザ接続がないため画面の目視確認は未実施で，Python 3.12，Android実機，正式APIでの検証も残っています．


## HTML版の登録画面

docs/register.htmlをブラウザで開くと，名称検索・デモサービスとプラン選択・手入力・入力検証・登録を確認できます．HTML版はブラウザのlocalStorageへ保存し，Flet版のJSONやホームの見本とは同期しません．JSONエクスポートも可能です．正式API接続は未実装です．


## Git保存時点の補足

ブランチはfeature/ishii-subscription-registrationです．チームリポジトリのsubmane/配下へ，登録画面・状態変更部品・並び替え・HTML版・テストを保存しています．共通コードは単独確認用の仮実装です．既存のCommon.md，client_db.md，home_mock.html，mane_server/server_db_api.mdは変更していません．

リポジトリにはDB・API設計書が追加されています．現状のAPIクライアントは前段で作成した仮契約であり，正式なAPIのラッパー付き応答，custom_*の入力項目，plan_id，タイムゾーン付き日時との統合が必要です．既定のダミーモードで確認してください．

このcloneでの実行例：

```powershell
cd 'C:/Users/Yuto/ICTⅡ/S10N-SubscriptionManagerApp/submane'
& 'C:/Users/Yuto/ICTⅡ/.venv/Scripts/python.exe' ./src/main.py --web
```
