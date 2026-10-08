#!/bin/bash
set -e

# コンテナを再起動したときに、前回のRailsサーバーが残したpidファイルが
# 残っていると起動に失敗するので、起動前に消しておく。
if [ -f /app/tmp/pids/server.pid ]; then
  rm -f /app/tmp/pids/server.pid
fi

exec "$@"
