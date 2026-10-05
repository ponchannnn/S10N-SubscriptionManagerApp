# 石井担当：実装状況と結合メモ

2026-10-05更新．ブランチは `ishii`．スクラム文書のプロジェクト計画ver.2（9/28）を優先し，README，`Common.md`，`client_db.md`，`mane_server/server_db_api.md`（v0.2），他担当ブランチを確認しました．資料の担当・設計は開発上の参照情報として扱っています．APIサーバはユーザ確認によりまだ未完成です．

## 石井が担当する機能

| 担当 | 計画期間 | 現在の状況 |
|---|---|---|
| サブスク登録画面 | 10/5〜10/12 | Fletの定番選択・手入力・入力検証・保存を実装 |
| 名称検索・定番サービスとプラン選択 | 10/13〜10/18 | 検索，自動入力，サービス・プランID引き継ぎ，古い検索応答の破棄を実装 |
| 解約／再契約，解約済みグレーアウト | 10/19〜10/24 | 公式手続き完了確認，状態変更部品，アイコン表示を実装 |
| 更新頻度順・解約済み末尾 | 10/25〜10/28 | 更新頻度順・登録順を実装．期限順はAPI計算済み日時を利用 |
| 結合・不具合修正 | 10/29〜11/1以降，全員 | 模擬APIで担当機能のテストを実装．共通画面と実APIへの結合は残作業 |

プロダクトロードマップの作成・更新にも石井の記載があります．既存のver.2を参照し，今回の進捗はこのメモに記録しています．PowerPointのロードマップを更新する際は，残存する2025年表記と現行計画の年をチームで確認してください．発表資料・デモ動画は全員の作業として残ります．

## 担当コード

| ファイル | 用途 |
|---|---|
| src/views/register.py | 登録画面．APIと保存後の遷移を注入可能 |
| src/logic/subscriptions.py | 入力検証，状態変更パッチ，並び替え |
| src/logic/api_contract.py | サーバv0.2の登録・更新項目への変換 |
| src/components/status_actions.py | 詳細に組み込む解約・再契約操作 |
| src/components/sort_selector.py | ホームなどに組み込む並び順選択 |
| src/components/service_icon.py | 解約済みグレーアウト，トライアル時計，安定した頭文字アイコン色 |
| tests/ | ロジック，保存，画面イベント，模擬APIの結合テスト |

`main.py` と `views/preview.py` は担当機能の単独確認用です．チーム共通のmain，ホーム，詳細を置き換えず，担当部品を組み込みます．`api_client.py` は担当確認用でサーバv0.2へ対応しましたが，チームのログイン・SQLiteキャッシュは実装していません．JSON保存はダミーモードだけです．実APIモードで失敗してもJSONへ保存せず，自動再送・オフライン登録は行いません．

## API仕様への対応

接続先は `SUBMANE_API_BASE_URL=https://指定されたホスト/api/v1` のように，`/api/v1`まで含めて指定します．サービス検索は `{ "services": [...] }`，一覧は `{ "subscriptions": [...], "server_time": ... }` を読み取ります．単独確認用クライアントは旧形式の配列も読み取れます．

- 定番登録：整数の `service_id` と，候補にIDがある場合の `plan_id` を送ります．プラン名・金額・周期の手修正も送ります．名称・入退会URL・退会案内はサービスマスタを使用するため読み取り専用です．変更する場合は手入力へ切り替えます．
- 手入力登録：`custom_name`，`custom_join_url`，`custom_cancel_url`，`custom_cancel_memo` を送ります．
- 入会日時・トライアル終了日時：タイムゾーンがない入力を日本時間として扱い，送信時は `+09:00` を付けます．APIのオフセット付き日時やdatetime値も並び替えで扱えます．
- 登録時の状態：契約中／トライアル中を選択します．POSTにstatusは送らず，トライアルの場合だけtrial_ends_atを送ります．解約は登録後の詳細操作で記録します．
- 解約：`{"status": "cancelled"}` をPATCHします．再契約：`status=active` と新しい `joined_at` をPATCHします．次回支払日はサーバの応答を使用し，クライアントで計算しません．
- HTTP 422：`error.message` と `error.details` を受け取り，該当する入力欄へエラーを表示します．401はログイン確認のエラーとして扱います．
- Cookie：ログイン担当と同じhttpx.AsyncClientを注入します．外部から注入したセッションの終了は呼び出し元が担当します．ブラウザのCookieは自動共有されません．Cookie永続化と401時のキャッシュ破棄は共通層に統合する作業です．

登録順はサーバの `created_at`，旧デモの `registered_at` を使い，日時がないものは元の順序を保って後ろへ置きます．どの並び順でも解約済みを末尾にします．期限順は取得済みnext_payment_atまたはtrial_ends_atで比較し，未取得の契約は後ろへ置きます．

## 共通コードとの相違点・残作業

`origin/tamatsukuri`には共通コードとホームが存在し，Flet 1.0.3とhttpx 0.28.1は一致しています．ただし，APIは同期モジュール関数で，パスが `/api/...` の仮仕様，更新がPUT，トライアル項目が `trial_end_at` となっています．サーバv0.2は `/api/v1/...`，PATCH，`trial_ends_at`です．これらを共通層で合わせてから結合してください．他担当ブランチは今回変更していません．

`register_view(page, api=api, on_saved=callback, on_back=callback)` と `status_actions(page, subscription, api, on_changed=callback)` に注入するAPIは，asyncの `search_services`，`create_subscription`，`update_subscription` を持つ必要があります．同期関数を使用する場合は，共通層側で `asyncio.to_thread` 等のasyncラッパーを用意し，共通ApiErrorをこの画面のApiErrorへ変換してください．コールバックは同期・asyncの両方を使えます．

登録・状態変更の成功後は，共通APIで一覧・詳細・期限・内訳のキャッシュを刷新してください．ローカルDBは `client_db.md` の方針に合わせて共通担当・池田担当と接続します．石井のコードで次回支払日や支払い見込みを計算しません．

ホームでは `sort_subscriptions(items, order)` と `sort_selector` を組み込み，詳細では `status_actions` を組み込みます．アイコンは共通部品と統合してください．小湊ブランチの `src/`，西内ブランチの `submane-flet/` と，共通の `submane/src/` では配置が異なるため，統合先ディレクトリをそろえる作業も残ります．

### 結合時の受け入れ確認

- [x] 定番・手入力の登録リクエスト，ラッパー付き一覧，PATCH状態変更を模擬APIで検証．
- [x] Cookie持ち回り，入力エラー，通信断時の非保存・自動再送なしを検証．
- [x] 入力検証，JSON再読込，二重クリック，古い検索応答，null・日時値，並び替えを検証．
- [ ] 玉造の共通API・ルート・ホームへ登録／並び替えを組み込む．
- [ ] 小湊の詳細へ解約・再契約操作を組み込む．
- [ ] 西内のログインと同一セッションで登録・更新を実APIに対して確認する．
- [ ] APIの401でログイン画面へ遷移し，Cookie・ユーザキャッシュが消えることを確認する．
- [ ] 操作成功後にホーム・期限・内訳が更新されることを確認する．
- [ ] Python 3.12，Android実機，複数端末，画面の目視で確認する．
- [ ] チームの結合テスト結果をロードマップ・発表資料・デモ動画へ反映する．

## 検証環境と起動

Python 3.14.4，Flet 1.0.3．自動テスト44件が成功しています．外部サーバを使わずhttpx.MockTransportで仕様上の通信を検証しました．実API・Python 3.12・Android実機・今回の画面目視は未検証です．

```powershell
cd 'C:/Users/Yuto/ICTⅡ/S10N-SubscriptionManagerApp/submane'
& 'C:/Users/Yuto/ICTⅡ/.venv/Scripts/python.exe' ./src/main.py --web
& 'C:/Users/Yuto/ICTⅡ/.venv/Scripts/python.exe' -m pytest -q
```

`docs/register.html` は独立した登録デモです．localStorageへ保存し，FletのJSONや正式APIとは同期しません．今回のAPI対応はFlet版に反映しています．全ソース・テスト・HTMLは `docs/complete_code.md` に省略せず掲載しています．
