#!/usr/bin/env bash
# Install/update the nginx reverse proxy on a LibreELEC box.
# Usage: deploy/deploy-proxy.sh root@kodi.lan [cert.crt cert.key]
# The certificate (shared by every vhost) is installed as certs/lan.crt|key;
# it only needs to be given once.
set -euo pipefail

HOST=${1:?usage: $0 user@host [cert.crt cert.key]}
CRT=${2:-}
KEY=${3:-}
DIR=/storage/proxy

cd "$(dirname "$0")/proxy"

ssh "$HOST" "mkdir -p $DIR/conf.d $DIR/certs"
scp -q nginx.conf new-cert.sh "$HOST:$DIR/"
scp -q conf.d/*.conf "$HOST:$DIR/conf.d/"
scp -q proxy.service "$HOST:/storage/.config/system.d/proxy.service"

if [ -n "$CRT" ]; then
    scp -q "$CRT" "$HOST:$DIR/certs/lan.crt"
    scp -q "$KEY" "$HOST:$DIR/certs/lan.key"
    ssh "$HOST" "chmod 600 $DIR/certs/lan.key"
fi
ssh "$HOST" "[ -f $DIR/certs/lan.crt ]" || { echo "No certificate on $HOST: pass cert.crt cert.key"; exit 1; }

ssh "$HOST" "systemctl daemon-reload && systemctl enable proxy.service && systemctl restart proxy.service"
echo "Proxy deployed."
