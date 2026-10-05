# サブマネ：Flet版サブスク管理アプリ

添付の開発ガイド `README2.md` に合わせ，Python 3.12 / Fletでサブスク登録画面と会員登録・ログイン画面を作成しました．まずこのREADMEで動かし，[会員登録・ログインと全体構成の説明](docs/account_guide.md)，[サブスク登録画面の説明](docs/register_guide.md) を読んでください．添付仕様は [development_spec.md](docs/development_spec.md) に内容を変えずに残しています．

## 動かす手順（Windows・Anaconda）

ZIPを展開して，`pyproject.toml` がある `submane-flet` フォルダで作業します．Anaconda Promptを使う場合，研究用の環境への依存追加を避けるため，アプリ専用のPython 3.12環境を作れます．

`Downloads` フォルダ自体にはプロジェクト設定がありません．エクスプローラーで展開先を開き，`pyproject.toml` が見えるフォルダのアドレスバーに `cmd` と入力すると，そのフォルダでコマンドプロンプトを開けます．

```bat
conda create -n submane python=3.12
conda activate submane
cd 展開先のパス\submane-flet
python -m pip install -e ".[dev]"
flet run
```

Python 3.12が通常インストールされている場合は，代わりに仮想環境を使えます．Windowsのコマンドプロンプトの例です．

```bat
cd 展開先のパス\submane-flet
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
flet run
```

macOS / Linuxでは，仮想環境を `source .venv/bin/activate` で有効にします．

起動後，「会員登録」→メールアドレスとパスワード・確認を入力→「会員登録する」→同じパスワードで「ログイン」と進みます．登録用パスワードは暫定で15〜128文字です．ログイン後は，ヘッダーの「追加」からサブスクを登録できます．アカウントアイコンからログアウトできます．

初期設定は試用モードです．メールは送信せず，同じアプリセッション内だけで登録とログインを試せます．アプリを再起動するとアカウントもサブスク情報も消えるため，再度会員登録してください．

ブラウザで開発用表示を確認する場合は `flet run --web`，Android上で開発用表示を確認する場合は `flet run --android` を使います．Androidでの方法は，端末側のFletクライアントとPCとの接続環境を準備してから試してください．

## 今回作った範囲

| ファイル | 内容 | 実装状況 |
|---|---|---|
| `src/views/register.py` | 定番サービスの名称検索・選択，自由入力，プラン，料金，入会日・時刻，トライアル終了日時，URL，メモ，登録 | 実装済み |
| `src/main.py` | 起動，共通ヘッダー・タブ，画面切り替え，ログインガード | 実装済み |
| `src/theme.py` / `src/components/` | ガイドの色・余白と，共通アイコン表示 | 実装済み |
| `src/api_client.py` | 会員登録・ログイン・ログアウト，検索・登録・取得，トークン管理 | 実装済み．本物のAPIルートは仮 |
| `src/dummy_data.py` | 試用アカウント，ユーザごとの登録情報，18件の名称候補 | 実装済み．正式な料金・アイコン・URLは未提供 |
| `src/auth_validation.py` | メール，パスワード，確認欄の入力検証 | 実装済み．登録ポリシーは暫定 |
| `src/views/home.py` | 登録後の確認，件数，4列・12件，横スワイプ，並び替え，時計・グレー表示 | 確認用の土台として実装 |
| `src/views/detail.py` | 登録情報の読み取り専用表示 | 確認用．編集・削除・外部URL遷移は未実装 |
| `src/views/account.py` | 会員登録・ログインフォーム，アカウント表示，ログアウト | 実装済み．正式APIへの接続は未確認 |
| `src/views/breakdown.py` / `deadline.py` | 画面切り替え用の入口 | 雛形．計算や一覧は未実装 |

既存のチームリポジトリは添付されていないため，今回の共通部品とホームは単独で動かすための土台です．各担当者の実装済みファイルにそのまま上書きせず，担当者と確認して統合してください．

## ダミーデータと本番API

初期設定の `src/config.py` は `USE_DUMMY_DATA = True` です．試用アカウントとサブスク情報はアプリの1セッション内だけで保持し，終了すると消えます．同じセッション中にログアウトして再ログインすると，自分のサブスク情報を再表示できます．別の試用ユーザとは情報を分離します．他端末との同期や永続保存は行いません．実契約や課金処理も行いません．

画面からは `context.api.create_subscription(data)` などを呼びます．`httpx` を直接呼んでいるのは `api_client.py` だけです．APIに切り替える際は，正式なルート・認証・日時書式を確認し，`api_client.py` を合わせてください．現在の `GET services`，`GET/POST subscriptions` は接続例です．

接続設定の例（Anaconda Prompt / コマンドプロンプト）:

```bat
set SUBMANE_API_BASE_URL=https://実際のAPIのURL/api
```

正式APIへ切り替えるには `USE_DUMMY_DATA = False` に変更します．現在の仮ルートは `POST /auth/signup`，`POST /auth/login`，`POST /auth/logout` です．ログインの返却値は `access_token` と `user: {id, email}` を想定し，検証後に共通APIクライアントでトークンを保持します．画面はログイン成功後だけホームへ遷移します．認証方式やメール確認の扱いが異なる場合は，共通クライアントと画面の完了表示を正式仕様に合わせます．詳細な契約例は [account_guide.md](docs/account_guide.md) に記載しています．

起動時には毎回ログインが必要です．パスワードやトークンをファイルへ保存しません．以前の `SUBMANE_API_TOKEN` による設定は使用せず，環境変数のトークンだけでログイン済みにはしません．

ガイドの項目名にそろえてあります．トライアル終了日時の `trial_ends_at` と，選択したマスタIDの `service_id` は登録画面で必要になる追加案です．正式API側での名称・扱いを確認してください．日時はガイドどおり `2026-10-05T11:00` のローカル日時を使います．タイムゾーンの扱いはAPI担当との取り決めが必要です．

次回更新日・支払い見込みの計算場所はガイドで未決定のため，今回 `src/logic/` は作っていません．`next_payment_at` はAPIが返した場合のみ表示し，ダミーでは `None` にします．

## バージョンとフォント

ガイドには固定済みの番号がなかったため，今回の動作確認版ではFlet **1.0.3**，httpx **0.28.1**，pytest **8.4.2** を固定しました．Pythonは `>=3.12,<3.13` に固定しています．チームで別の番号を決めている場合は，そちらに合わせて再確認してください．古いFletのコードと混ぜると，ボタン・ルーティングなどのAPIが異なることがあります．

`src/assets/fonts/` にZen Kaku Gothic NewのRegular書体とOFLライセンスを同梱しています．元のHTMLは `docs/home_mock.html` として見た目の参考用に置いています．アプリの起動時には使いません．

## テストとAPK

```bat
python -m pytest -q
```

今回の検証結果は **59件成功** です．会員登録・ログイン・ログアウト，誤った認証情報，不正なAPI応答，ユーザ別のサブスク分離，ログアウト後の画面制限，通信エラー，二重送信防止，既存のサブスク登録とホーム反映を確認しています．テストの画面用ページはPython側のイベントを検証するもので，Flutter画面の描画は行いません．

Fletの配信側で起動でき，画面の配信と同梱フォントの読み込みが成功することも確認しました．Android実機での見た目・操作，APKビルド，正式APIとの接続，2端末同期は未確認です．

APKを作る場合（SDK等の準備が必要）:

```bat
flet build apk --python-version 3.12
```

## 参考

- [Flet公式：インストール](https://flet.dev/docs/getting-started/installation/)
- [Flet公式：Androidへのパッケージ化](https://flet.dev/docs/publish/android/)
- [Flet公式：非同期アプリ](https://flet.dev/docs/cookbook/async-apps/)
- [Flet公式：PageView](https://flet.dev/docs/controls/pageview/)
- [Zen Kaku Gothic Newの配布元](https://github.com/google/fonts/tree/main/ofl/zenkakugothicnew)
