#!/data/data/com.termux/files/usr/bin/bash
# CriptoHost CPUMiner — build Android (Termux, aarch64)
# Requisitos: Termux instalado via F-Droid ou APK do GitHub (fora da Play Store).
#   pkg update && pkg install -y git clang make autoconf automake libtool \
#       binutils openssl libcurl libjansson zlib python
set -euo pipefail
cd "$(dirname "$0")/.."

[ -n "${PREFIX:-}" ] && case "$PREFIX" in *com.termux*) : ;; *) echo "⚠ Rode dentro do Termux"; exit 1;; esac

ARCH=$(uname -m)
# cpuminer-opt só compila em 64 bits (x86_64+SSE2 ou aarch64+NEON). Em Termux 32 bits (armv7l/armv8l —
# TV box, celular antigo) usamos o cpuminer-multi (tpruvot, GPL-2) como motor: mesmo CLI, mesma API
# 4048, SHA-256d com NEON de 32 bits. Mais lento (~1–3 MH/s por core), mas mina.
case "$ARCH" in
  armv7l|armv8l)
    ABIS=$(getprop ro.product.cpu.abilist 2>/dev/null || true)
    echo "ℹ Termux em 32 bits ($ARCH): usando o motor cpuminer-multi."
    case "$ABIS" in *arm64-v8a*)
      echo "  Este aparelho é 64 bits ($ABIS): o Termux arm64-v8a (F-Droid) daria bem mais hashrate.";; esac
    D=third_party/cpuminer-multi
    if [ ! -d "$D" ]; then
      git clone --depth 1 -b linux https://github.com/tpruvot/cpuminer-multi.git "$D"
    fi
    ( cd "$D" && ./autogen.sh && \
      CFLAGS="-O3 -march=armv7-a -mfpu=neon -DCH_BUILD -Wall -I$PREFIX/include" LDFLAGS="-L$PREFIX/lib" \
      LIBS="-lcrypto -lz" ./configure --with-curl && make -j"$(nproc)" )  # LIBS: ld moderno não puxa libcrypto/zlib sozinho
    cp "$D/cpuminer" ./cpuminer
    echo; ./cpuminer --version | head -3
    echo "✅ Build OK (motor 32 bits: cpuminer-multi)"
    echo "   Minerar: ./ch/mine.sh   ·   Segurar a CPU viva: termux-wake-lock"
    exit 0;;
esac

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
