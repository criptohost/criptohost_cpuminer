#!/usr/bin/env bash
# CriptoHost CPUMiner — build macOS (Apple Silicon e Intel)
# Requisitos: xcode-select --install && brew install autoconf automake jansson openssl@3 curl
set -euo pipefail
cd "$(dirname "$0")/.."

ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
  # M1=armv8.4 · M2/M3=armv8.6 · M4=armv9.2 — armv8.4 roda em todos (crypto+sha3)
  MARCH="-march=armv8.4-a+crypto+sha3 -flax-vector-conversions"
else
  MARCH="-march=native"
fi

./autogen.sh
CFLAGS="-O3 $MARCH -DCH_BUILD -Wno-deprecated-declarations \
  -I$(brew --prefix openssl@3)/include -I$(brew --prefix jansson)/include" \
LDFLAGS="-L$(brew --prefix openssl@3)/lib -L$(brew --prefix jansson)/lib" \
./configure --with-curl
make -j"$(sysctl -n hw.ncpu)"

echo
./cpuminer --version | head -5
echo "✅ Build OK — teste: ./cpuminer -a sha256d --benchmark --time-limit=10"
