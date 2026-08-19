#!/usr/bin/env bash
# Espelha o dashboard do criptohost_nerdos (data/) para o agent (ch/agent/web/).
# Rode após qualquer mudança de UI no NerdOS para manter os dois iguais.
set -euo pipefail
SRC="${1:-$(dirname "$0")/../../../criptohost_nerdos/data}"
DST="$(dirname "$0")/web"
[ -d "$SRC" ] || { echo "Fonte não encontrada: $SRC (passe o caminho do data/ como argumento)"; exit 1; }
rm -rf "$DST"
cp -R "$SRC" "$DST"
echo "✅ web/ sincronizado de $SRC"
