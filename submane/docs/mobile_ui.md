# スマホUIとサービス画像

2026-10-19更新．保存先はishiiブランチです．

UIの主な変更と起動手順は [ishii.md](ishii.md) を参照してください．画像を色変更・切り抜きせず，白い領域内に縦横比を保って表示します．トライアルは時計，解約済みはチェックの別バッジで表現します．

## 同梱画像の出典

App Storeの公式アプリアイコン16件，Adobe配布のCreative Cloud SVG1件，Simple IconsのAmazon Prime・iCloud SVG2件を使用しています．YouTube Premium・Kindle Unlimited等では，プラン専用ではなく対応アプリのアイコンを使っています．iCloud+にはiCloudのシンボルを使っています．Simple Iconsの2件は第三者が管理する画像です．画像を追加したこと自体は，利用許諾を取得したことを意味しません．今回は授業内表示というユーザーの前提で組み込んでいます．

| サービス | ファイル | 出典 |
|---|---|---|
| Netflix | `netflix.png` | [公式アプリのアイコン](https://apps.apple.com/jp/app/netflix/id363590051?uo=4) |
| Spotify | `spotify.png` | [公式アプリのアイコン](https://apps.apple.com/jp/app/spotify-%E9%9F%B3%E6%A5%BD%E3%81%A8%E3%83%9D%E3%83%83%E3%83%89%E3%82%AD%E3%83%A3%E3%82%B9%E3%83%88/id324684580?uo=4) |
| Audible | `audible.png` | [公式アプリのアイコン](https://apps.apple.com/jp/app/amazon-audible-%E3%82%AA%E3%83%BC%E3%83%87%E3%82%A3%E3%82%AA%E3%83%96%E3%83%83%E3%82%AF/id379693831?uo=4) |
| U-NEXT | `unext.png` | [公式アプリのアイコン](https://apps.apple.com/jp/app/u-next-%E6%98%A0%E7%94%BB%E3%82%84%E3%83%89%E3%83%A9%E3%83%9E-%E3%82%A2%E3%83%8B%E3%83%A1%E3%81%AA%E3%81%A9%E3%81%AE%E5%8B%95%E7%94%BB%E3%81%8C%E8%A6%8B%E6%94%BE%E9%A1%8C/id882477693?uo=4) |
| YouTube Premium | `youtube-premium.png` | [公式アプリのアイコン](https://apps.apple.com/jp/app/youtube/id544007664?uo=4) |
| Disney+ | `disney-plus.png` | [公式アプリのアイコン](https://apps.apple.com/jp/app/disney/id1446075923?uo=4) |
| FODプレミアム | `fod-premium.png` | [公式アプリのアイコン](https://apps.apple.com/jp/app/fod-%E3%83%89%E3%83%A9%E3%83%9E%E3%82%84%E3%82%A2%E3%83%8B%E3%83%A1%E3%81%AA%E3%81%A9%E3%83%86%E3%83%AC%E3%83%93%E3%81%AE%E5%8B%95%E7%94%BB%E3%81%8C%E8%A6%8B%E6%94%BE%E9%A1%8C-%E8%A6%8B%E9%80%83%E3%81%97%E9%85%8D%E4%BF%A1%E3%82%82/id945241274?uo=4) |
| DAZN | `dazn.png` | [公式アプリのアイコン](https://apps.apple.com/jp/app/dazn-%E3%83%80%E3%82%BE%E3%83%BC%E3%83%B3-%E3%82%B9%E3%83%9D%E3%83%BC%E3%83%84%E3%82%92%E3%83%A9%E3%82%A4%E3%83%96%E4%B8%AD%E7%B6%99/id1129523589?uo=4) |
| Apple Music | `apple-music.png` | [公式アプリのアイコン](https://apps.apple.com/jp/app/apple-music/id1108187390?uo=4) |
| Hulu | `hulu.png` | [公式アプリのアイコン](https://apps.apple.com/jp/app/hulu-%E3%83%95%E3%83%BC%E3%83%AB%E3%83%BC-%E4%BA%BA%E6%B0%97%E3%83%89%E3%83%A9%E3%83%9E%E3%82%84%E6%98%A0%E7%94%BB-%E3%82%A2%E3%83%8B%E3%83%A1%E3%81%AA%E3%81%A9%E3%81%8C%E8%A6%8B%E6%94%BE%E9%A1%8C/id549416492?uo=4) |
| Kindle Unlimited | `kindle-unlimited.png` | [公式アプリのアイコン](https://apps.apple.com/jp/app/amazon-kindle/id302584613?uo=4) |
| Lemino | `lemino.png` | [公式アプリのアイコン](https://apps.apple.com/jp/app/lemino-%E3%83%AC%E3%83%9F%E3%83%8E-%E9%9F%B3%E6%A5%BD%E3%83%A9%E3%82%A4%E3%83%96%E3%82%84%E3%82%B9%E3%83%9D%E3%83%BC%E3%83%84-%E3%83%89%E3%83%A9%E3%83%9E%E7%AD%89%E3%81%8C%E8%A6%8B%E6%94%BE%E9%A1%8C/id1641218070?uo=4) |
| ABEMAプレミアム | `abema-premium.png` | [公式アプリのアイコン](https://apps.apple.com/jp/app/abema-%E3%82%A2%E3%83%99%E3%83%9E-%E6%96%B0%E3%81%97%E3%81%84%E6%9C%AA%E6%9D%A5%E3%81%AEtv/id1074866833?uo=4) |
| dアニメストア | `d-anime-store.png` | [公式アプリのアイコン](https://apps.apple.com/jp/app/d%E3%82%A2%E3%83%8B%E3%83%A1%E3%82%B9%E3%83%88%E3%82%A2-%E3%82%A2%E3%83%8B%E3%83%A1%E5%8B%95%E7%94%BB%E8%A6%8B%E6%94%BE%E9%A1%8C%E3%82%A2%E3%83%97%E3%83%AA-%E3%83%9E%E3%83%AB%E3%83%81%E3%83%87%E3%83%90%E3%82%A4%E3%82%B9%E5%AF%BE%E5%BF%9C/id728214964?uo=4) |
| NHKオンデマンド | `nhk-on-demand.png` | [公式アプリのアイコン](https://apps.apple.com/jp/app/nhk%E3%82%AA%E3%83%B3%E3%83%87%E3%83%9E%E3%83%B3%E3%83%89/id606706412?uo=4) |
| ChatGPT | `chatgpt.png` | [公式アプリのアイコン](https://apps.apple.com/jp/app/chatgpt/id6448311069?uo=4) |
| Adobe CC | `adobe-cc.svg` | [サービスロゴ](https://www.adobe.com/creativecloud.html) |
| Amazonプライム | `amazon-prime.svg` | [Simple Iconsのブランド図形（公式配布ファイルではない）](https://github.com/simple-icons/simple-icons/tree/14.0.0) |
| iCloud+ | `icloud-plus.svg` | [Simple Iconsのブランド図形（公式配布ファイルではない）](https://github.com/simple-icons/simple-icons/tree/14.0.0) |

機械可読の取得元・日付・補足は `src/assets/icons/sources.json` に保存しています．アプリの `src/assets/icons/` とAPIサーバの `mane_server/public/icons/` には同一ファイルを配置しています．DBには画像データ自体ではなく既存設計の `icon_path` を保存します．SVG3件のパスはseedにも反映済みです．

## 画像表示の優先順

実APIモードではAPIの画像URL，同梱画像，頭文字の順です．ダミーモードでは同梱画像を優先するため，APIサーバなしで表示できます．サービス名の照合は全角・半角・大文字・小文字・空白を正規化しています．

## 2026-10-26：解約済みカードの表示

ホームの解約済みカードは，ロゴ・サービス名・状態の文字・チェック・枠を含む全体を無彩色にし，不透明度50％で表示します．タップによる詳細表示と再契約は引き続き利用できます．契約中とトライアル中のカードは従来の表示を使用します．

## 2026-10-26：画面遷移と入力操作

ホームの補助文と期限画面の補助文を削除しました．ホーム下部の凡例は，カードと同じ時計・チェックの部品を使い，スクロール領域の外・下部タブの直上に固定しています．

ホーム・内訳・期限のタブ切り替えは，ヘッダーと下部タブを固定し，中身を280msで左右にスライドします．タブの順序に沿って移動方向を変え，連続操作や登録・詳細への移動で古いアニメーションが残らないようにしています．

登録画面の入会日時・トライアル終了日時は，入力欄またはカレンダーボタンをタップして選択します．カレンダーの確定後に24時間表記の時刻入力を開き，時刻を確定したときだけ日本時間・分単位の入力値に反映します．途中でキャンセルした場合は元の値を保ちます．トライアルの日付は入会日以降を選び，同日の時刻の前後関係も従来の登録検証で確認します．

config.pyのAPI接続先はローカル設定として維持し，今回のコミット対象には含めません．コード全文ドキュメント内のconfig.pyも，Gitに保存されている共通設定を掲載しています．
