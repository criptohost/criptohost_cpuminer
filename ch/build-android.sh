#!/data/data/com.termux/files/usr/bin/bash
# CriptoHost CPUMiner — build Android (Termux, aarch64)
# Requisitos: Termux instalado via F-Droid ou APK do GitHub (fora da Play Store).
#   pkg update && pkg install -y git clang make autoconf automake libtool \
#       binutils openssl libcurl libjansson zlib python
set -euo pipefail
cd "$(dirname "$0")/.."

[ -n "${PREFIX:-}" ] && case "$PREFIX" in *com.termux*) : ;; *) echo "⚠ Rode dentro do Termux"; exit 1;; esac

# cpuminer-opt só compila em 64 bits (x86_64+SSE2 ou aarch64+NEON). Termux 32 bits (armv7l/armv8l) —
# comum em TV box — falha com "use of undeclared identifier 'v128u32_t'" em simd-utils/intrlv.h.
ARCH=$(uname -m)
case "$ARCH" in
  aarch64|x86_64) : ;;
  *)
    ABIS=$(getprop ro.product.cpu.abilist 2>/dev/null || true)
    echo "✗ Termux em 32 bits ($ARCH): o minerador precisa de 64 bits (aarch64)."
    case "$ABIS" in
      *arm64-v8a*) echo "  O aparelho é 64 bits ($ABIS), mas o Termux instalado é a versão 32 bits."
                   echo "  Desinstale o Termux e instale o APK arm64-v8a (F-Droid escolhe o certo; no GitHub pegue termux-app_*_arm64-v8a.apk).";;
      *)           echo "  O Android deste aparelho é só 32 bits (abilist: ${ABIS:-?}). Não há como rodar o minerador nele.";;
    esac
    exit 1;;
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
