# 石井担当：develop統合後の状況

2026-10-05更新．作業ブランチはishii．origin/develop（e3e6e98）を取り込み，石井のAPI仕様対応・入力検証・状態変更・並び替え改善を共通構成に結合しました．取り込み前の状態はbackup/ishii-before-develop（fd836a3）に保存しています．

## 担当と進捗

| 石井の担当 | 計画ver.2の期間 | 状況 |
|---|---|---|
| 登録画面 | 10/5〜10/12 | 共通mainから開き，共通APIへ登録する構成に統合 |
| 名称検索・定番選択 | 10/13〜10/18 | 共通マスタへ接続．プラン選択・ID引き継ぎ・古い検索応答破棄に対応 |
| 解約／再契約，グレーアウト | 10/19〜10/24 | 小湊の詳細から操作し，共通ストアを更新する構成に統合 |
| 更新頻度順・解約済み末尾 | 10/25〜10/28 | ホームのorderingから担当ロジックを使用．登録順はcreated_atにも対応 |
| 結合・不具合修正 | 10/29以降，全員 | 模擬API・共通ストア・画面生成の自動テスト65件成功 |

プロダクトロードマップの作成・更新にも石井の記載があります．既存ver.2を参照し，実装進捗はこのメモへ記録しました．PowerPointの進捗反映，年表記の確認，発表資料・デモ動画の担当機能説明は残っています．

## 統合した構成

- main.py，navigation.py，home.py，breakdown.py，deadline.py，detail.py，theme.pyはdevelopの共通構成を使います．単独確認用preview.pyとsort_selector.pyは廃止しました．
- register_viewは共通api_clientを既定で使用し，成功時の案内と元タブへの遷移を行います．必要ならAPI・on_saved・on_backを注入できます．
- status_actionsは詳細から共通api_clientを受け取り，成功後に詳細を再表示します．公式サイトを開いただけでは状態を変更しません．
- logic/api_bridge.pyで同期の共通APIをasync画面から呼びます．asyncの注入APIにも対応します．
- service_iconは共通のサイズ・バッジ・footprintを保ち，画像なしの色をIDから固定できます．
- api_clientの同期関数が共通アプリのCookieとダミー一覧を管理します．ApiClientクラスは旧試作・自動テストとの互換用途として残しており，共通画面の保存先には使いません．共通のダミー登録はメモリ内で，再起動すると初期データに戻ります．

## サーバv0.2への対応

環境変数SUBMANE_API_BASE_URLはHTTPSホスト，または/api/v1まで含むURLを指定できます．サーバはユーザ確認によりまだ未完成なので，現在はダミーモードが既定です．

- サービス検索・契約一覧のラッパー付き応答を読み取ります．
- 定番登録はservice_id・plan_id，手入力はcustom_*を送信します．プラン名・金額・周期の修正を送れます．定番の名称・URL・退会案内はマスタを使い，変更時は手入力へ切り替えます．
- POSTにstatusやnext_payment_atを送らず，トライアルはtrial_ends_atで指定します．解約はPATCH status=cancelled，再契約はPATCH status=activeと新しいjoined_atです．
- 入力日時は日本時間として扱い，API送信時はオフセットを付けます．共通画面の旧trial_end_atはAPI側のtrial_ends_atと変換します．
- APIのcreated_at・next_payment_atを保持し，次回支払日は取得済みのAPI値を優先します．developにある担当者の既存の日付・金額計算はダミー用に維持しています．石井の新しい日付計算は追加していません．内訳をサーバsummaryへ接続する作業は担当者との連携が必要です．
- サーバの422エラーを入力欄へ表示します．Cookieを同一HTTPクライアントで保持し，登録失敗の自動再送やオフライン登録はしません．
- Flet1.0.3に合わせ，詳細のダイアログ操作をshow_dialog/pop_dialogへ修正しました．

## 残る結合・検証

- [x] developをishiiに取り込み，共通main・ホーム・詳細に担当機能を接続．
- [x] 共通ストアで登録・状態変更が反映されることをテスト．
- [x] Cookie，APIのパス・項目・応答，入力エラー，通信断を模擬APIで検証．
- [x] ホーム・詳細・期限・内訳がFlet1.0.3で生成できることを確認．
- [ ] submane-flet側の西内担当とsubmane/views/account.pyの仮置き画面を統合．ログインUIはまだ共通mainへつながっていません．
- [ ] API完成後，ログイン・登録・状態変更・一覧同期を実サーバで検証．
- [ ] Cookie永続化，401時のキャッシュ破棄，ローカルSQLiteキャッシュを共通担当と接続．
- [ ] 金額集計をサーバsummaryへ接続し，表示・期限・内訳の更新を確認．
- [ ] Python3.12，Android実機，画面の目視，複数端末で確認．
- [ ] ロードマップの進捗と，発表資料・デモ動画へ結果を反映．

## 起動とテスト

今回の検証環境はPython3.14.4，Flet1.0.3，flet-charts1.0.3です．起動引数--webは旧単独版のもので，共通mainでは使用しません．

```powershell
cd 'C:/Users/Yuto/ICTⅡ/S10N-SubscriptionManagerApp/submane'
& 'C:/Users/Yuto/ICTⅡ/.venv/Scripts/python.exe' ./src/main.py
& 'C:/Users/Yuto/ICTⅡ/.venv/Scripts/python.exe' -m pytest -q
```

HTMLのdocs/register.htmlは独立した登録デモです．Flet・共通APIと同期しません．src・tests・HTML・起動スクリプトのコード全文はdocs/complete_code.mdに掲載しています．
