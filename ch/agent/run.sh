#!/usr/bin/env bash
# CH Agent — sobe dashboard web + mDNS + miner. Cria venv local com zeroconf na 1ª vez.
set -euo pipefail
cd "$(dirname "$0")"
[ -d web ] || ./sync-web.sh
if [ ! -d .venv ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install -q zeroconf || echo "⚠ zeroconf falhou — mDNS desligado, dashboard funciona"
fi
exec ./.venv/bin/python3 agent.py
