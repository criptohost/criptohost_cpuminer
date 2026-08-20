#!/data/data/com.termux/files/usr/bin/bash
# CriptoHost CPUMiner — build Android (Termux, aarch64)
# Requisitos: Termux instalado via F-Droid ou APK do GitHub (fora da Play Store).
#   pkg update && pkg install -y git clang make autoconf automake libtool \
#       binutils openssl libcurl libjansson zlib python
set -euo pipefail
cd "$(dirname "$0")/.."

[ -n "${PREFIX:-}" ] && case "$PREFIX" in *com.termux*) : ;; *) echo "⚠ Rode dentro do Termux"; exit 1;; esac

ARCH=$(uname -m)
if [ "$ARCH" = "aarch64" ]; then
  # SoCs Android (Snapdragon/Exynos/Tensor) têm as extensões crypto ARMv8
  MARCH="-march=armv8-a+crypto -flax-vector-conversions"
else
  MARCH="-march=native"   # x86 Android (emulador/Chromebook)
fi

./autogen.sh
CFLAGS="-O3 $MARCH -DCH_BUILD -Wall -I$PREFIX/include" \
LDFLAGS="-L$PREFIX/lib" \
./configure --with-curl
make -j"$(nproc)"

echo
./cpuminer --version | head -5
echo "✅ Build OK"
echo "   Minerar:            ./ch/mine.sh"
echo "   Segurar a CPU viva: termux-wake-lock (rode antes de minerar)"
echo "   ⚠ Celular esquenta: use na tomada, prefira menos threads ([6] no menu)"
