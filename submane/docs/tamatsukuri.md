# 玉造の担当メモ(ホーム・内訳・共通部品)

玉造が作った部分の設計と、他の担当者が画面を作るときに知っておくべきことをまとめます。

## 1. 作ったもの

| ファイル | 内容 |
|---|---|
| `pyproject.toml` | 依存ライブラリ(flet 1.0.3、flet-charts 1.0.3、httpx 0.28.1)とビルド設定 |
| `src/main.py` | 起動、ルートに応じた画面の組み立て、ヘッダーとタブの取り付け |
| `src/navigation.py` | 画面の切り替え用の関数(README にないファイル。下の 3. を参照) |
| `src/config.py` | ダミーデータの切り替え、APIのURL |
| `src/theme.py` | 色・フォント・余白、`theme.text()`、`theme.yen()` |
| `src/api_client.py` / `src/dummy_data.py` | APIの呼び出しとダミーデータ |
| `src/components/app_header.py` / `tab_bar.py` | ヘッダー、下部タブ |
| `src/components/service_icon.py` | サービスのアイコン(トライアルの時計、解約済みのグレー) |
| `src/components/feedback.py` | 0件・エラー時の案内表示、主要ボタン(README にないファイル) |
| `src/views/home.py` | ホーム画面 |
| `src/views/breakdown.py` | 内訳画面 |
| `src/logic/dates.py` / `payments.py` / `ordering.py` | 次回支払日、支払い見込み、並び替え |
| `tests/test_dates.py` / `test_payments.py` | 上の計算のテスト(17件) |
| `src/views/account.py` / `register.py` / `detail.py` / `deadline.py` | **仮置き**。「準備中」と出すだけなので、各担当が書き換える |

README の「3. ディレクトリ構成」に対して増えたのは `navigation.py`、`components/feedback.py`、`logic/ordering.py` の3つです。

## 2. Flet のどの機能を使うか(README 13章で任された分)

| やりたいこと | 使うもの | 補足 |
|---|---|---|
| ホームの横スワイプ | `ft.PageView` | 1ページ12件。点のタップは `pager.go_to_page()` |
| 内訳の円グラフ | `flet_charts.PieChart` | `flet-charts` パッケージ。`import flet_charts as fch` |
| URLをブラウザで開く | `ft.UrlLauncher().launch_url()` | `navigation.open_url(page, url)` にまとめてある |
| 画面の切り替え | `page.push_route()` と `page.views` | `navigation.go()` にまとめてある。端末の「戻る」にも対応 |

## 3. 画面を作る人へ

### 画面ファイルの形

`views/` の自分のファイルを書き換えます。関数名と引数は変えないでください(`main.py` が呼びます)。

```python
import flet as ft

import api_client
import navigation
import theme
from components import feedback


def deadline_view(page: ft.Page) -> ft.Control:
    """期限画面の中身を返す。"""
    try:
        subs = api_client.list_subscriptions()
    except api_client.ApiError as err:
        return feedback.error_panel(page, str(err))   # 案内と「もう一度読み込む」ボタン

    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,   # 子を横幅いっぱいに広げる
        controls=[...],
    )
```

- ヘッダーと下部タブは付けない(中身だけ返す)
- 画面はルートが変わるたびに作り直される。登録や編集のあとは `navigation.go()` で移動すれば、移動先は最新のデータで表示される
- 画面の関数の中で例外が出てもアプリは止まらず、エラー案内が出る(原因はコンソールに表示)

### 画面の切り替え(`navigation.py`)

```python
navigation.go(page, navigation.REGISTER)    # HOME / BREAKDOWN / DEADLINE / REGISTER / ACCOUNT
navigation.go_detail(page, sub["id"])       # 詳細画面へ
navigation.go_back(page)                    # 最後に開いていたタブ画面へ戻る
navigation.get_sub_id(page)                 # 詳細画面で、表示するサブスクのID(文字列)を受け取る
navigation.open_url(page, sub["cancel_url"])  # 端末のブラウザで開く
navigation.reload(page)                     # 今の画面を作り直す
```

担当ごとのメモ:

- **西内(ログイン)**: `api_client.sign_up()` / `log_in()` が成功したら `navigation.go(page, navigation.HOME)` を呼ぶ。未ログインのときは、どのルートでも `main.py` がアカウント画面に切り替える。ログイン前の見た目を確認するには `config.DUMMY_START_LOGGED_IN = False` にする
- **石井(登録)**: 登録が終わったら `navigation.go_back(page)`。並び替えは `logic/ordering.py` にあり、ホームで使っているので、仕様を変えるときは一緒に直す
- **小湊(詳細・期限)**: 次回支払日は `logic/dates.next_payment_at(sub)`。内訳の計算が `dates.py` に依存しているので先に作ってある。中身の確認とテストの追加をお願いしたい

### 共通部品

```python
from components.service_icon import service_icon
service_icon(sub)                       # 72px。トライアルの時計・解約済みのグレーは自動
service_icon(sub, size=44, ring_color=theme.SURFACE)   # 白いカードの上に小さく置くとき

feedback.message_panel("まだ登録がありません。", button_label="追加", on_click=...)
feedback.error_panel(page, str(err))
feedback.primary_button("保存する", on_click=...)

theme.text("見出し", size=26, weight="bold")   # weight は "regular" / "bold" / "black"
theme.yen(1500)                                 # "¥1,500"
```

文字は `ft.Text` を直接使わず `theme.text()` を使ってください。太字用のフォントファイルを切り替えているので、`ft.Text(weight=ft.FontWeight.BOLD)` だと太字がきれいに出ません。

### データの形と `api_client`

サブスク1件は README 5章の項目に `trial_end_at`(無料トライアルの終了日時)を足した辞書です。`next_payment_at` は持たせず、`logic/dates.py` で計算します。

`api_client` の関数: `is_logged_in` / `sign_up` / `log_in` / `log_out` / `list_subscriptions` / `get_subscription` / `create_subscription` / `update_subscription` / `delete_subscription` / `search_services` / `icon_url`

- ダミーデータの間も、登録・編集・削除はアプリを閉じるまで反映される
- 失敗すると `api_client.ApiError` が出る。`str(err)` はそのまま画面に出せる日本語

## 4. 設計で決めたこと

### 計算のルール(`logic/`)

README 13章の「アプリ側で計算する」に従い、アプリ側に置きました。

- 支払日の起点は入会日時。`trial_end_at` があればそちらが起点(トライアル中の次回支払日 = トライアル終了日時)
- 起点から月額は1か月ごと、年額は12か月ごと。その日がない月は末日に寄せる。起点から数えるので 1/31 → 2/28 → 3/31 とずれが積み重ならない
- 解約済みは支払日なし、支払い見込みにも含めない
- 年額の扱いは内訳画面の切り替えで選ぶ: 「年額は更新月に計上」(`MODE_BILLING`、初期値)/「年額を月割り」(`MODE_AVERAGE`、12で割って四捨五入)。選択はアプリを閉じるまで覚えている

### ホーム画面

- 1ページ = 4列 x 3行。アイコンの大きさは画面幅に合わせて48〜72pxで決まる(390pxで72px)
- タイルの色は登録順で固定(並び替えても同じサービスは同じ色)。APIからアイコンURLが来ればその画像を表示し、読み込めなければ頭文字に戻る
- 件数表示の「契約中」はトライアル中を含む

### 内訳画面

- 月は左右の矢印で切り替えられる(初期表示は今月)
- 円グラフは金額の上位6件 + 「その他」。割合が8%未満の区分にはラベルを出さない
- 一覧の行をタップすると詳細画面へ移る

### 画面の重なり方

- タブ画面(ホーム / 内訳 / 期限)は1枚だけ表示
- 登録・詳細・アカウントは、最後に開いていたタブ画面の上に重ねる。ヘッダーは「戻る」+ 画面名になる
- 端末の「戻る」とヘッダーの「戻る」は、どちらも最後に開いていたタブ画面へ戻る

## 5. まだできていないこと・確認が必要なこと

- **実機・画面での見た目は未確認**。動作確認は「画面の組み立て、画面遷移、並び替え、ページ送り、内訳の切り替え」をプログラム上で行っただけで、Flet の画面に実際に描画した確認はしていない。余白のずれや文字のはみ出しは `flet run` で見て直す必要がある
- **APIとの接続は未確認**。`api_client.py` の `ENDPOINTS`(パス)と項目名は仮。API担当の仕様書に合わせて `ENDPOINTS` と `_to_app_subscription()` を直す
- **ログイン状態の保存**。cookie は `httpx.Client` がアプリ起動中だけ保持する。アプリを閉じてもログインを保つ方法は、西内・API担当と相談して決める
- **通信中の表示**。API呼び出しは同期処理なので、応答を待つ間は画面が切り替わらない。遅いようなら読み込み中の表示を足す
- `pyproject.toml` の `org = "jp.e1"` は仮
- フォント(Zen Kaku Gothic New)は SIL Open Font License。ライセンス文を `src/assets/fonts/OFL.txt` に入れてある
