# Raspberry Pi 5 + Cloudflare Tunnel デプロイ手順

`mane_server`(Rails API)をRaspberry Pi 5上で動かし、Cloudflare Tunnelでインターネットに公開する手順。
ルーターのポート開放は不要(Tunnelが内側から外へトンネルを張るだけなので、受信側のポートを開ける必要がない)。

既存のローカル開発用Docker構成(`Dockerfile`・`docker-compose.yml`)をそのまま使う。
Raspberry Pi 5はARM64なので、Pi上で直接`docker compose build`すればビルドできる(クロスビルド不要)。

---

## 0. 前提

| 項目 | 内容 |
|---|---|
| 対象機器 | Raspberry Pi 5(64bit OS) |
| 公開方法 | Cloudflare Tunnel(`cloudflared`) |
| 必要なもの | Cloudflareに登録済みの自分のドメイン(Tunnelで名前付きルートを張るには、Cloudflareで管理しているドメインが必要) |

ドメインが無い場合は`cloudflared tunnel --url http://localhost:3000`で一時的なURL(`*.trycloudflare.com`)を発行できるが、
再起動すると毎回URLが変わるので検証用途のみ。本番運用するなら安いドメインを1つ取ってCloudflareに追加するのがおすすめ。

---

## 1. Raspberry Pi の初期設定

1. [Raspberry Pi Imager](https://www.raspberrypi.com/software/)で **Raspberry Pi OS Lite (64-bit)** をSDカード/SSDに書き込む。
   書き込み時の設定で、SSHを有効化しユーザー名・パスワードを設定しておくと楽(ヘッドレスで進められる)。
2. Piを起動し、同じLAN内のPCからSSH接続する。
   ```bash
   ssh <ユーザー名>@<PiのIPアドレス>
   ```
3. パッケージを最新化する。
   ```bash
   sudo apt update && sudo apt full-upgrade -y
   sudo reboot
   ```
4. Dockerを入れる(公式スクリプト)。
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER
   ```
   一度ログアウトして入り直す(`exit`してSSHし直す)。`docker compose version`が通ればOK。

---

## 2. アプリをPiに持ってくる

```bash
git clone <このリポジトリのURL>
cd S10N-SubscriptionManagerApp/mane_server
git checkout develop   # もしくは本番用に出したいブランチ
```

---

## 3. 本番用の設定(gitに入れないもの)

以下は**秘密情報なのでコミットしない**。Pi上で直接作る。

### 3.1 `config/master.key` を持ってくる

開発機にある`mane_server/config/master.key`をPiにコピーする(このファイルは`.gitignore`対象でリポジトリには入っていない)。

```bash
# 開発機側で実行
scp mane_server/config/master.key <ユーザー名>@<PiのIPアドレス>:~/S10N-SubscriptionManagerApp/mane_server/config/master.key
```

### 3.2 `docker-compose.prod.yml` をPi上に作る

開発用の`docker-compose.yml`に重ねて使う、本番用の差分ファイル。Pi上で新規作成する。

```yaml
# mane_server/docker-compose.prod.yml (Pi上にだけ置く。gitには入れない)
services:
  db:
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: ここに強いパスワードを決めて書く
      POSTGRES_DB: app_production
    ports: []   # 本番ではホストにDBのポートを公開しない

  web:
    environment:
      RAILS_ENV: production
      DATABASE_HOST: db
      APP_DATABASE_PASSWORD: 上と同じパスワード
      RAILS_MASTER_KEY: config/master.key を開いて中に書かれている値をそのまま貼る
    command: ["bin/rails", "server", "-e", "production", "-b", "0.0.0.0"]
    ports:
      - "3000:3000"
```

`config/database.yml`の`production:`は、Postgresのユーザー名を`app`固定で読む作りになっている
(`username: app`)。ここを変えたくなければ、上のように`POSTGRES_USER: app`にそろえるのが一番簡単。

---

## 4. ビルドして起動する

```bash
cd mane_server
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# DBを作る(primary/cache/queue/cableの4つ。db/seeds.rbのダミーデータも入れる場合はdb:seedも)
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm web bin/rails db:prepare
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm web bin/rails db:seed

# 起動
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

確認:
```bash
curl http://localhost:3000/up
```
200が返ればアプリ自体は起動できている。以降、`docker compose -f docker-compose.yml -f docker-compose.prod.yml ...`
を毎回書くのは長いので、`alias dc-prod="docker compose -f docker-compose.yml -f docker-compose.prod.yml"`
のようなaliasを`~/.bashrc`に足しておくと楽。

---

## 5. Cloudflare Tunnel を張る

### 5.1 cloudflared を入れる

```bash
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
sudo dpkg -i cloudflared.deb
cloudflared --version
```

### 5.2 Cloudflareにログインする

```bash
cloudflared tunnel login
```
表示されたURLをブラウザで開き、トンネルを紐付けたいドメインを選んで許可する
(SSH先ではなく、手元のPC/スマホのブラウザで開いてよい)。

### 5.3 トンネルを作る

```bash
cloudflared tunnel create submane-api
```
`Tunnel credentials written to /home/<ユーザー名>/.cloudflared/<TUNNEL_ID>.json`
のように出力される`TUNNEL_ID`を控えておく。

### 5.4 設定ファイルを作る

```yaml
# ~/.cloudflared/config.yml
tunnel: <控えたTUNNEL_ID>
credentials-file: /home/<ユーザー名>/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: api.自分のドメイン.com
    service: http://localhost:3000
  - service: http_status:404   # 他のホスト名へのアクセスは404にする(ingressの最後は必ずこの形)
```

### 5.5 DNSのルートを張る

```bash
cloudflared tunnel route dns submane-api api.自分のドメイン.com
```
CloudflareのDNSに`api.自分のドメイン.com`へのCNAMEレコードが自動で追加される。

### 5.6 サービスとして常駐させる(再起動しても自動で立ち上がるように)

```bash
sudo cloudflared service install
sudo systemctl enable --now cloudflared
sudo systemctl status cloudflared   # active (running) になっていればOK
```

### 5.7 確認

```bash
curl https://api.自分のドメイン.com/up
```
Pi以外の、インターネット越しの端末から200が返れば成功。

---

## 6. アプリ(submane)側を本物のURLに向ける

`submane/src/config.py`

```python
USE_DUMMY_DATA = False
API_BASE_URL = "https://api.自分のドメイン.com"   # 末尾の / は付けない
```

---

## 7. 更新するとき(2回目以降)

```bash
cd ~/S10N-SubscriptionManagerApp/mane_server
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm web bin/rails db:migrate
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

`cloudflared`はPi起動時に自動で立ち上がる(5.6のsystemd登録済みのため)ので、
アプリを更新するだけならCloudflare側は何もしなくていい。

---

## 8. 注意点・まだ決めていないこと

- **DBのバックアップ**: 今の構成はDocker volumeにPostgresのデータを置くだけなので、Piが壊れるとデータも消える。
  定期的に`pg_dump`を取って別の場所に置く仕組みは別途検討する(doc §9の「デプロイ先」未決事項と合わせて)
- **Piの固定IP/電源**: Wi-Fiが不安定だとTunnelも切れる。できれば有線LAN + 固定IPにしておく
- **`RAILS_MASTER_KEY`の管理**: `docker-compose.prod.yml`に平文で書く形にしているが、人数が増えたら
  `.env`ファイル([Composeのenv_file](https://docs.docker.com/compose/environment-variables/))に分けて
  `.gitignore`に入れる運用に変えてもよい
