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
POOL_NAME="dgb-fusionpool"
POOL_URL="stratum+tcp://dgb.fusionpool.pro:3333"
WORKER="CH-CPU-$(hostname -s | tr '[:lower:]' '[:upper:]' | tr -cd 'A-Z0-9' | cut -c1-8)"
THREADS="0"        # 0 = todos os cores
PASSWORD="X"
ALGO="sha256d"     # vem do perfil ("algo" no ch/conf/*.json); rx/*, gr, argon2/*, cn* usam o XMRig
[ -f "$CONF" ] && . "$CONF"
ALGO="${ALGO:-sha256d}"   # miner.conf antigo (sem ALGO) continua = sha256d

save() {
  cat > "$CONF" << EOF
WALLET="$WALLET"
POOL_NAME="$POOL_NAME"
POOL_URL="$POOL_URL"
WORKER="$WORKER"
THREADS="$THREADS"
PASSWORD="$PASSWORD"
ALGO="$ALGO"
EOF
}

profiles() { ls "$CONF_DIR/conf" | sed 's/\.json$//'; }

pool_url_of()  { python3 -c "import json;print(json.load(open('$CONF_DIR/conf/$1.json'))['url'])" 2>/dev/null; }
pool_algo_of() { python3 -c "import json;print(json.load(open('$CONF_DIR/conf/$1.json')).get('algo','sha256d'))" 2>/dev/null; }
pool_pass_of() { python3 -c "import json;print(json.load(open('$CONF_DIR/conf/$1.json')).get('pass','x'))" 2>/dev/null; }

# motor por algoritmo: sha256d/yespower/yescrypt/... = cpuminer-opt; rx/*, gr, argon2/*, cn* = XMRig
engine_of() { case "$1" in rx/*|gr|argon2/*|cn*|ghostrider) echo xmrig;; *) echo cpuminer;; esac; }

pick_pool() {
  echo
  echo "Perfis disponíveis:"
  local i=1; local names=()
  while IFS= read -r p; do
    names+=("$p")
    printf "  [%d] %-24s %-12s %s\n" "$i" "$p" "$(pool_algo_of "$p")" "$(pool_url_of "$p")"
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
    ALGO="$(pool_algo_of "$POOL_NAME")"
    PASSWORD="$(pool_pass_of "$POOL_NAME")"   # ex.: zpool exige c=MOEDA
  else
    echo "Opção inválida."
  fi
}

build_hint() {
  case "${PREFIX:-}" in *com.termux*) echo "./ch/build-android.sh"; return;; esac
  [ "$(uname)" = "Darwin" ] && echo "./ch/build-macos.sh" || echo "./ch/build-linux.sh"
}

start_miner() {
  local eng; eng="$(engine_of "$ALGO")"
  if [ ! -x "./$eng" ]; then
    echo; echo "⚠ Binário ./$eng não compilado — rode $(build_hint)$([ "$eng" = xmrig ] && echo " e ./ch/build-xmrig.sh") primeiro."; return
  fi
  if [ -z "$WALLET" ]; then
    echo; echo "⚠ Configure a wallet antes de iniciar."; return
  fi
  save
  echo
  # -t 0 literal faria o cpuminer subir ZERO threads; omitir = todos os cores
  T_ARG=()
  [ -n "$THREADS" ] && [ "$THREADS" != "0" ] && T_ARG=(-t "$THREADS")
  if [ "$eng" = xmrig ]; then
    # XMRig: API HTTP na 4049 (o agent lê /2/summary); doação mínima do projeto = 1 %
    exec ./xmrig -a "$ALGO" -o "$POOL_URL" -u "$WALLET.$WORKER" -p "$PASSWORD" \
         "${T_ARG[@]}" --http-host 127.0.0.1 --http-port 4049 --donate-level 1
  fi
  exec ./cpuminer -a "$ALGO" -o "$POOL_URL" -u "$WALLET.$WORKER" -p "$PASSWORD" \
       "${T_ARG[@]}" --api-bind 127.0.0.1:4048
}

# ---- modo direto (retrocompatível): ./ch/mine.sh <perfil> <wallet> [worker] ----
if [ $# -ge 2 ]; then
  POOL_NAME="$1"; WALLET="$2"; WORKER="${3:-$WORKER}"
  url="$(pool_url_of "$POOL_NAME")" || true
  [ -n "${url:-}" ] || { echo "Perfil desconhecido: $POOL_NAME"; profiles; exit 1; }
  POOL_URL="$url"; ALGO="$(pool_algo_of "$POOL_NAME")"; PASSWORD="$(pool_pass_of "$POOL_NAME")"
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
  [4] Pool      : $POOL_NAME · $POOL_URL · $ALGO ($(engine_of "$ALGO"))
  [5] Worker    : $WORKER
  [6] Threads   : $t
  [7] Password  : $PASSWORD
  [0] Sair
EOF
  read -rp " Opção: " op
  case "$op" in
    1) start_miner ;;
    2) if [ ! -x "./$(engine_of "$ALGO")" ]; then echo; echo "⚠ Binário ./$(engine_of "$ALGO") não compilado — rode $(build_hint) primeiro."; else save; exec ch/agent/run.sh; fi ;;
    3) read -rp "Wallet (endereço da moeda da pool): " WALLET; save ;;
    4) pick_pool; save ;;
    5) read -rp "Worker (nome deste nó, ex. CH-CPU-01): " WORKER; save ;;
    6) read -rp "Threads (0 = todos os cores): " THREADS; save ;;
    7) read -rp "Password da pool (X ou d=0.001): " PASSWORD; save ;;
    0) exit 0 ;;
    *) echo "Opção inválida." ;;
  esac
done
