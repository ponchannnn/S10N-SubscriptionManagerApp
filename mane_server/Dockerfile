# syntax=docker/dockerfile:1

# サブマネAPI(Rails 8 / API mode)のローカル開発用イメージ。
# 本番用のマルチステージ最適化はせず、開発のしやすさを優先する。
FROM ruby:3.3.5-slim

# Rails/PostgreSQL/ネイティブ拡張のビルドに必要なパッケージ
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libyaml-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Gemfile/Gemfile.lockだけ先にコピーしてbundle installをキャッシュさせる
# (`rails new` 実行後は本来のGemfile/Gemfile.lockに置き換わり、再度このレイヤーが走る)
# Gemfile.lockを含めずにbundle installすると、ロックファイルと異なるバージョンのgemが
# インストールされ、後からCOPY . .でロックファイルが入った際にバージョン不一致で
# 実行時エラーになるため、両方コピーしてからbundle installする。
COPY Gemfile Gemfile.lock ./
RUN bundle install

COPY . .

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 3000

ENTRYPOINT ["entrypoint.sh"]
CMD ["rails", "server", "-b", "0.0.0.0"]
