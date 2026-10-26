# 石井担当：最新版の統合とスマホUI

2026-10-19更新．作業ブランチは `ishii`．`origin/develop` の `9490148` を取り込み，ダウンロード内の最新版を基に画面配置とロゴを整えました．

## 今回の変更

- ホームは3列・1ページ12件．サービス名を2行で表示し，料金・契約状態を添えました．追加ボタンはホーム右上へまとめ，左右スワイプと44pxのページ移動ボタンを用意しました．
- 背景は淡いグレー，カードは白，主操作は深緑に統一しました．共通ヘッダー・下部タブ・画面の余白にも適用しています．
- 登録画面は「サービスを選ぶ」「契約内容」「入会・退会の情報」の3区画．料金欄は全幅とし，登録ボタンをスクロール領域の外に置きました．検索結果にもロゴを表示します．
- 19サービスの画像をアプリとAPIサーバの両方へ同梱しました．画像の縦横比と色を保ち，契約状態は外側のバッジと文言で示します．通信時はAPI画像を優先し，読めない場合は同梱画像，未登録サービスは頭文字に切り替えます．
- 最新developのCookie認証・SQLiteキャッシュと，既存の石井担当の入力検証・検索・登録・解約／再契約・並び替えを接続しました．サーバの計算結果の日時・IDと入力エラー詳細を引き継ぎます．
- 画像の原本・出典は `src/assets/icons/sources.json`，説明は `docs/mobile_ui.md` に記録しています．

## 起動

依存関係は最新developと同じFlet 1.0.4です．初回は `./setup.ps1` を実行し，続いて `./run.ps1` を実行します．既存の仮想環境は `pip install -r requirements.txt` で更新してください．

```powershell
cd 'C:/Users/Yuto/Downloads/S10N-SubscriptionManagerApp-develop/submane'
$env:SUBMANE_USE_DUMMY_DATA = 'true'
& 'C:/Users/Yuto/ICTⅡ/.venv-ui/Scripts/python.exe' ./src/main.py
```

このPCの検証用環境はPython 3.14，Flet 1.0.4です．従来の `.venv` は変更せず，別の `.venv-ui` を用意しました．

API接続時は起動前に設定します．URLは `/api/v1` を含めず，サーバのホストまでを指定してください．

```powershell
$env:SUBMANE_USE_DUMMY_DATA = 'false'
$env:SUBMANE_API_BASE_URL = 'https://実際のAPIホスト'
```

未指定時はダミーで起動します．ダミーの登録データはアプリ終了時に消えます．実APIのロゴパス変更を既存DBへ反映する際は，API担当が通常のマスタ更新手順で `mane_server/db/seeds/services.yml` を反映してください．画像本体は `mane_server/public/icons` に配置済みです．

## 確認と残り

アプリ側の操作・API契約・キャッシュ・画像整合性・320/390/430pxを想定したコントロール構成をpytestで確認しています．Webサーバと静的画像のHTTP応答も確認対象です．ブラウザの目視，Android実機，稼働中のRails/PostgreSQLとの結合は未確認です．実サービスの金額やURLの調査・API公開は担当者と確認してください．

HTMLの `docs/register.html` は従来の独立デモであり，今回のFletアプリの画面とは同期しません．ソースコード全文は `docs/complete_code.md` に保存しています．

## Webプレビューの依存関係

Flet 1.0.4のWebサーバはFastAPI 0.146.0では `openapi_prefix` 引数のエラーになりました．検証済みの0.142.2を開発用依存関係に固定しています．FastAPI側は0.145.0でこの引数を削除しています（[公式リリースノート](https://fastapi.tiangolo.com/release-notes/#01450)）．これはFletのWebプレビュー用であり，Rails APIの構成には影響しません．
