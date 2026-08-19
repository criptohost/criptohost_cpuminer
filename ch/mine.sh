#!/usr/bin/env bash
# CriptoHost CPUMiner — lançador rápido
# Uso: ./ch/mine.sh <perfil> <wallet> [worker]
#   perfis: dgb-hmpool (default) · dgb-letsmine · btc-nerdminers · btc-public-pool · xec-mining-dutch · bch-mining-dutch
# Ex.:  ./ch/mine.sh dgb-hmpool DAbC...xyz CH-CPU-01
set -euo pipefail
cd "$(dirname "$0")/.."

PROFILE="${1:-dgb-hmpool}"
WALLET="${2:?Uso: $0 <perfil> <wallet> [worker]}"
WORKER="${3:-CH-CPU-$(hostname -s | tr '[:lower:]' '[:upper:]' | cut -c1-8)}"
CONF="ch/conf/$PROFILE.json"
[ -f "$CONF" ] || { echo "Perfil desconhecido: $PROFILE"; ls ch/conf/ | sed 's/\.json$//'; exit 1; }

URL=$(python3 -c "import json;print(json.load(open('$CONF'))['url'])")
exec ./cpuminer -a sha256d -o "$URL" -u "$WALLET.$WORKER" -p x --api-bind 127.0.0.1:4048
