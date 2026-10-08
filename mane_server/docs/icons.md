# サービスアイコン画像 依頼メモ

サブマネで使う、定番サービス19件分のアイコン画像をお願いしたいです。

## 欲しいもの

以下19個の画像ファイルを、**ファイル名を下の表の通りに**して用意してください。

| ファイル名 | サービス名 |
|---|---|
| `spotify.png` | Spotify |
| `audible.png` | Audible |
| `unext.png` | U-NEXT |
| `amazon-prime.png` | Amazonプライム |
| `youtube-premium.png` | YouTube Premium |
| `disney-plus.png` | Disney+ |
| `fod-premium.png` | FODプレミアム |
| `dazn.png` | DAZN |
| `apple-music.png` | Apple Music |
| `adobe-cc.png` | Adobe CC |
| `hulu.png` | Hulu |
| `kindle-unlimited.png` | Kindle Unlimited |
| `lemino.png` | Lemino |
| `abema-premium.png` | ABEMAプレミアム |
| `icloud-plus.png` | iCloud+ |
| `d-anime-store.png` | dアニメストア |
| `nhk-on-demand.png` | NHKオンデマンド |
| `chatgpt.png` | ChatGPT |

内容は各サービスの公式アイコン(ロゴマーク)でお願いします。デモ・学習目的のアプリなので、各サービスの公式サイトやアプリストアに掲載されている画像を使っていただいて大丈夫です。

## ファイルの形式

- **形式**: PNG(背景は透明)
- **サイズ**: 正方形、512×512px 推奨(最低でも256×256px)
- **見た目**: ロゴの外側に余白を作らず、画像いっぱいに描いてください(アプリ側で角を丸くする処理をするので、角丸加工は不要です)
- **ファイル名**: 上の表の通り、半角英数字とハイフンのみ(大文字小文字も表の通りに)

## 置き場所

`mane_server/public/icons/` フォルダの中に、19個のファイルをそのまま置いてください。

```
mane_server/
└── public/
    └── icons/
        ├── netflix.png
        ├── spotify.png
        ├── ...
        └── chatgpt.png
```

## 補足(確認用)

置いていただいたファイルは、サーバ起動後に `http://localhost:3000/icons/netflix.png` のようなURLでそのまま見られるようになります(`netflix`の部分をファイル名に変えて確認してください)。表示されなければファイル名か置き場所が間違っている可能性があるので教えてください。

19件すべて揃っていなくても、できたものから随時置いていただいて大丈夫です。
