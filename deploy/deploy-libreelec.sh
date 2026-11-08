#!/usr/bin/env bash
# Build and (re)start PGSparkLite on a LibreELEC box.
# Usage: deploy/deploy-libreelec.sh root@kodi.lan [AMP_BT_ADDRESS]
set -euo pipefail

HOST=${1:?usage: $0 user@host [amp_bt_address]}
AMP=${2:-}
DIR=/storage/pgsparklite
DOCKER=/storage/.kodi/addons/service.system.docker/bin/docker

cd "$(dirname "$0")/.."

git archive --format=tar HEAD | ssh "$HOST" "rm -rf $DIR/src && mkdir -p $DIR/src $DIR/data && tar -x -C $DIR/src"
ssh "$HOST" "cd $DIR/src && $DOCKER build -t pgsparklite:latest ."

if [ -n "$AMP" ]; then
    ssh "$HOST" "echo AMP_BT_ADDRESS=$AMP > $DIR/pgsparklite.env"
fi

ssh "$HOST" "cp $DIR/src/deploy/pgsparklite.service /storage/.config/system.d/pgsparklite.service \
    && systemctl daemon-reload && systemctl enable pgsparklite.service && systemctl restart pgsparklite.service \
    && $DOCKER image prune -f >/dev/null"

echo "PGSparkLite deployed (behind the proxy: https://spark.lan)"
