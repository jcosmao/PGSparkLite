#!/bin/sh
# Optional: create a local CA (first run) and a per-host certificate with SAN,
# if you ever want certificates browsers fully trust. Not used by default:
# the proxy serves the shared *.lan certificate (certs/lan.crt).
# Usage (on the box): new-cert.sh spark.lan
set -eu

HOST=${1:?usage: $0 <host name>}
DIR=/storage/proxy
CA=$DIR/ca
CERTS=$DIR/certs
OPENSSL="/storage/.kodi/addons/service.system.docker/bin/docker run --rm -v $DIR:$DIR -w $DIR alpine/openssl"

mkdir -p "$CA" "$CERTS"

if [ ! -f "$CA/ca.key" ]; then
    $OPENSSL req -x509 -new -nodes -newkey rsa:4096 -sha256 -days 3650 \
        -subj "/CN=Home LAN CA" \
        -keyout "$CA/ca.key" -out "$CA/ca.crt"
    chmod 600 "$CA/ca.key"
    echo "Created local CA: $CA/ca.crt (install it on your devices)"
fi

cat > "$CERTS/$HOST.ext" <<EXT
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:$HOST
EXT

$OPENSSL req -new -nodes -newkey rsa:2048 -subj "/CN=$HOST" \
    -keyout "$CERTS/$HOST.key" -out "$CERTS/$HOST.csr"
# 825 days: maximum validity accepted by Apple/Chrome for server certs
$OPENSSL x509 -req -in "$CERTS/$HOST.csr" -CA "$CA/ca.crt" -CAkey "$CA/ca.key" \
    -CAcreateserial -days 825 -sha256 -extfile "$CERTS/$HOST.ext" -out "$CERTS/$HOST.crt"
rm -f "$CERTS/$HOST.csr" "$CERTS/$HOST.ext"
chmod 600 "$CERTS/$HOST.key"
echo "Certificate for $HOST: $CERTS/$HOST.crt"
