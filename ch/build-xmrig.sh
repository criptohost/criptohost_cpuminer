#!/usr/bin/env bash
# CriptoHost CPUMiner — segundo motor: XMRig (GPL-3) para RandomX (Monero, Salvium, Wownero), GhostRider, Argon2.
# Gera ./xmrig; o mine.sh e o agent escolhem o motor pelo "algo" do perfil. Não toca no ./cpuminer.
#   macOS:  brew install cmake libuv openssl@3
#   Linux:  apt install cmake libuv1-dev libssl-dev build-essential   (hwloc opcional: libhwloc-dev)
#   Termux: pkg install cmake libuv openssl clang git     (só aarch64: RandomX em 32 bits é impraticável)
set -euo pipefail
cd "$(dirname "$0")/.."
D=third_party/xmrig
[ -d "$D/.git" ] || git clone --depth 1 https://github.com/xmrig/xmrig.git "$D"
FLAGS=(-DCMAKE_BUILD_TYPE=Release -DWITH_OPENCL=OFF -DWITH_CUDA=OFF)
case "$(uname -s)" in
  Darwin) FLAGS+=(-DWITH_HWLOC=OFF -DOPENSSL_ROOT_DIR="$(brew --prefix openssl@3 2>/dev/null || echo /opt/homebrew/opt/openssl@3)");;
  *)
    if [ -n "${PREFIX:-}" ] && case "$PREFIX" in *com.termux*) true;; *) false;; esac; then
      case "$(uname -m)" in aarch64) FLAGS+=(-DWITH_HWLOC=OFF -DARM_TARGET=8);;
        *) echo "✗ XMRig/RandomX precisa de Termux 64 bits (aarch64); este é $(uname -m)."; exit 1;; esac
    else
      pkg-config --exists hwloc 2>/dev/null || FLAGS+=(-DWITH_HWLOC=OFF)
    fi;;
esac
mkdir -p "$D/build" && cd "$D/build"
cmake .. "${FLAGS[@]}"
make -j"$(nproc 2>/dev/null || sysctl -n hw.ncpu)"
cp xmrig ../../../xmrig
cd ../../..
./xmrig --version | head -1
echo "✅ ./xmrig pronto — perfis: ch/conf/xmr-*.json, sal-fusionpool.json (menu do ./ch/mine.sh)"
echo "   Doação do XMRig: 1 % (mínimo do projeto upstream). RandomX rende mais com 2 GB livres (modo rápido)."
