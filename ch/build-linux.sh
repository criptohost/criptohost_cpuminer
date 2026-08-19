#!/usr/bin/env bash
# CriptoHost CPUMiner — build Linux (x86_64 e aarch64)
# Debian/Ubuntu: sudo apt install build-essential automake libssl-dev libcurl4-openssl-dev libjansson-dev libgmp-dev zlib1g-dev
set -euo pipefail
cd "$(dirname "$0")/.."

ARCH=$(uname -m)
if [ "$ARCH" = "aarch64" ]; then
  MARCH="-march=armv8-a+crypto -flax-vector-conversions"   # Raspberry Pi 4/5 e afins
else
  MARCH="-march=native"                                    # habilita SHA-NI/AVX2 se o CPU tiver
fi

./autogen.sh
CFLAGS="-O3 $MARCH -DCH_BUILD -Wall" ./configure --with-curl
make -j"$(nproc)"

echo
./cpuminer --version | head -5
echo "✅ Build OK — teste: ./cpuminer -a sha256d --benchmark --time-limit=10"
