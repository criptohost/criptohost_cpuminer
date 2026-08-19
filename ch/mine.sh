#!/usr/bin/env bash
# CriptoHost CPUMiner — CLI interativo
#
# Interativo:      ./ch/mine.sh            (menu: editar wallet/pool/worker/threads e iniciar)
# Direto (script): ./ch/mine.sh <perfil> <wallet> [worker]
#
# A configuração fica em ch/miner.conf (KEY=VALUE, fora do git).
set -euo pipefail
cd "$(dirname "$0")/.."
CONF_DIR="ch"
CONF="$CONF_DIR/miner.conf"

# ---- defaults + persistência ----
WALLET=""
POOL_NAME="dgb-hmpool"
POOL_URL="stratum+tcp://digi.hmpool.io:3337"
WORKER="CH-CPU-$(hostname -s | tr '[:lower:]' '[:upper:]' | tr -cd 'A-Z0-9' | cut -c1-8)"
THREADS="0"        # 0 = todos os cores
PASSWORD="X"
[ -f "$CONF" ] && . "$CONF"

save() {
  cat > "$CONF" << EOF
WALLET="$WALLET"
POOL_NAME="$POOL_NAME"
POOL_URL="$POOL_URL"
WORKER="$WORKER"
THREADS="$THREADS"
PASSWORD="$PASSWORD"
EOF
}

profiles() { ls "$CONF_DIR/conf" | sed 's/\.json$//'; }

pool_url_of() { python3 -c "import json;print(json.load(open('$CONF_DIR/conf/$1.json'))['url'])" 2>/dev/null; }

pick_pool() {
  echo
  echo "Perfis disponíveis:"
  local i=1; local names=()
  while IFS= read -r p; do
    names+=("$p")
    printf "  [%d] %-18s %s\n" "$i" "$p" "$(pool_url_of "$p")"
    i=$((i+1))
  done < <(profiles)
  printf "  [%d] URL personalizada (stratum+tcp://host:porta)\n" "$i"
  read -rp "Escolha: " n
  if [ "$n" = "$i" ]; then
    read -rp "URL da pool: " POOL_URL
    POOL_NAME="custom"
  elif [ "$n" -ge 1 ] 2>/dev/null && [ "$n" -lt "$i" ]; then
    POOL_NAME="${names[$((n-1))]}"
    POOL_URL="$(pool_url_of "$POOL_NAME")"
  else
    echo "Opção inválida."
  fi
}

start_miner() {
  if [ -z "$WALLET" ]; then
    echo; echo "⚠ Configure a wallet antes de iniciar."; return
  fi
  save
  echo
  exec ./cpuminer -a sha256d -o "$POOL_URL" -u "$WALLET.$WORKER" -p "$PASSWORD" \
       -t "$THREADS" --api-bind 127.0.0.1:4048
}

# ---- modo direto (retrocompatível): ./ch/mine.sh <perfil> <wallet> [worker] ----
if [ $# -ge 2 ]; then
  POOL_NAME="$1"; WALLET="$2"; WORKER="${3:-$WORKER}"
  url="$(pool_url_of "$POOL_NAME")" || true
  [ -n "${url:-}" ] || { echo "Perfil desconhecido: $POOL_NAME"; profiles; exit 1; }
  POOL_URL="$url"
  start_miner
fi

# ---- modo interativo ----
while true; do
  t=$([ "$THREADS" = "0" ] && echo "auto (todos os cores)" || echo "$THREADS")
  w=$([ -n "$WALLET" ] && echo "$WALLET" || echo "(não configurada)")
  cat << EOF

 CriptoHost CPUMiner — configuração
 ──────────────────────────────────────────────────
  [1] Iniciar mineração
  [2] Wallet    : $w
  [3] Pool      : $POOL_NAME · $POOL_URL
  [4] Worker    : $WORKER
  [5] Threads   : $t
  [6] Password  : $PASSWORD
  [0] Sair
EOF
  read -rp " Opção: " op
  case "$op" in
    1) start_miner ;;
    2) read -rp "Wallet (endereço da moeda da pool): " WALLET; save ;;
    3) pick_pool; save ;;
    4) read -rp "Worker (nome deste nó, ex. CH-CPU-01): " WORKER; save ;;
    5) read -rp "Threads (0 = todos os cores): " THREADS; save ;;
    6) read -rp "Password da pool (x ou d=0.001): " PASSWORD; save ;;
    0) exit 0 ;;
    *) echo "Opção inválida." ;;
  esac
done
