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

build_hint() {
  case "${PREFIX:-}" in *com.termux*) echo "./ch/build-android.sh"; return;; esac
  [ "$(uname)" = "Darwin" ] && echo "./ch/build-macos.sh" || echo "./ch/build-linux.sh"
}

start_miner() {
  if [ ! -x ./cpuminer ]; then
    echo; echo "⚠ Binário não compilado — rode $(build_hint) primeiro."; return
  fi
  if [ -z "$WALLET" ]; then
    echo; echo "⚠ Configure a wallet antes de iniciar."; return
  fi
  save
  echo
  # -t 0 literal faria o cpuminer subir ZERO threads; omitir = todos os cores
  T_ARG=()
  [ -n "$THREADS" ] && [ "$THREADS" != "0" ] && T_ARG=(-t "$THREADS")
  exec ./cpuminer -a sha256d -o "$POOL_URL" -u "$WALLET.$WORKER" -p "$PASSWORD" \
       "${T_ARG[@]}" --api-bind 127.0.0.1:4048
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
  [1] Iniciar mineração (só terminal)
  [2] Iniciar com dashboard web (CH Agent)
  [3] Wallet    : $w
  [4] Pool      : $POOL_NAME · $POOL_URL
  [5] Worker    : $WORKER
  [6] Threads   : $t
  [7] Password  : $PASSWORD
  [0] Sair
EOF
  read -rp " Opção: " op
  case "$op" in
    1) start_miner ;;
    2) if [ ! -x ./cpuminer ]; then echo; echo "⚠ Binário não compilado — rode $(build_hint) primeiro."; else save; exec ch/agent/run.sh; fi ;;
    3) read -rp "Wallet (endereço da moeda da pool): " WALLET; save ;;
    4) pick_pool; save ;;
    5) read -rp "Worker (nome deste nó, ex. CH-CPU-01): " WORKER; save ;;
    6) read -rp "Threads (0 = todos os cores): " THREADS; save ;;
    7) read -rp "Password da pool (X ou d=0.001): " PASSWORD; save ;;
    0) exit 0 ;;
    *) echo "Opção inválida." ;;
  esac
done
