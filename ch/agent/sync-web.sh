#!/usr/bin/env bash
# Espelha o dashboard do criptohost_nerdos (data/) para o agent (ch/agent/web/).
# Fontes, em ordem: argumento > repo vizinho ../criptohost_nerdos > GitHub (main).
set -euo pipefail
cd "$(dirname "$0")"
DST="web"
SRC="${1:-../../../criptohost_nerdos/data}"

if [ ! -d "$SRC" ]; then
  echo "Repo local não encontrado — baixando dashboard do GitHub (criptohost/criptohost_nerdos)…"
  TMP=$(mktemp -d)
  curl -fsSL https://github.com/criptohost/criptohost_nerdos/archive/refs/heads/main.tar.gz \
    | tar -xz -C "$TMP" --strip-components=1 "criptohost_nerdos-main/data" 2>/dev/null \
    || { echo "Falha ao baixar do GitHub — verifique a rede"; rm -rf "$TMP"; exit 1; }
  SRC="$TMP/data"
fi

rm -rf "$DST"
cp -R "$SRC" "$DST"
[ -n "${TMP:-}" ] && rm -rf "$TMP"
echo "✅ web/ sincronizado de $SRC"
