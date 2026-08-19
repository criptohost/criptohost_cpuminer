# CriptoHost CPUMiner

**Minerador SHA-256 de CPU para Windows, Linux e macOS — CLI/texto.**
O irmão de mesa do [CriptoHost NerdOS](https://github.com/criptohost/criptohost-nerdos): mesma filosofia (aprender minerando, lottery/PPLNS), ordens de grandeza mais hashrate.

Um produto [Cripto Host](https://cripto.host) · *"Miner de um jeito fácil"*

Fork de [JayDDee/cpuminer-opt](https://github.com/JayDDee/cpuminer-opt) (GPL-2.0) — todo o crédito do núcleo de mineração ao upstream.

---

## ⚠️ Aviso honesto

Projeto de **hobby, educação e comunidade**. Um M2 faz ~130 MH/s de SHA-256d; um único ASIC moderno faz 200 **T**H/s — 1,5 milhão de vezes mais. Em BTC a chance de bloco é ~zero; em DGB com pool PPLNS low-diff você vê shares aceitos e aprende o protocolo. O valor está em entender Stratum, dificuldade e otimização de CPU (SHA-NI/NEON) — não em renda.

## Por que este fork

| Critério | cpuminer-opt (upstream) |
|---|---|
| Licença | GPL-2.0 ✓ |
| Mantido | ✓ (v26.1, jan/2026) |
| Plataformas | Linux, Windows, macOS, BSD — x86_64 **e** aarch64 (Apple Silicon, Raspberry Pi) |
| SHA-256d | Otimizado com SHA-NI (x86) e extensões SHA2/NEON (ARM) — o mais rápido da categoria |
| Stratum | V1 `stratum+tcp://` e `stratum+ssl://` + getblocktemplate |
| Interface | 100% CLI/texto + API JSON local (`--api-bind`) |

Benchmark validado neste fork: **Apple M2, 8 threads → 132,9 MH/s** (sha256d).

## Início rápido

### macOS

```bash
xcode-select --install
brew install autoconf automake jansson openssl@3 curl
./ch/build-macos.sh
./ch/mine.sh dgb-hmpool SUACARTEIRA CH-CPU-01
```

### Linux (Debian/Ubuntu)

```bash
sudo apt install build-essential automake libssl-dev libcurl4-openssl-dev libjansson-dev libgmp-dev zlib1g-dev
./ch/build-linux.sh
./ch/mine.sh dgb-hmpool SUACARTEIRA CH-CPU-01
```

### Windows

Use o executável pré-compilado das [Releases do upstream](https://github.com/JayDDee/cpuminer-opt/releases) (ou compile via MSYS2 — veja `INSTALL_WINDOWS`):

```bat
cpuminer-sse2.exe -c ch\conf\dgb-hmpool.json
```

(escolha o exe conforme sua CPU: `-avx2-sha` para Ryzen/Intel modernos)

## Perfis de pool prontos

```bash
./cpuminer -c ch/conf/dgb-hmpool.json      # edite SUACARTEIRA antes
```

| Perfil | Moeda | Observação |
|---|---|---|
| `dgb-hmpool` | DGB | **default** — PPLNS low-diff, shares frequentes |
| `dgb-letsmine` | DGB | letsmine.it (Brasil/US) |
| `btc-nerdminers` / `btc-public-pool` | BTC | lottery |
| `xec-mining-dutch` / `bch-mining-dutch` | XEC/BCH | requer conta |

## Telemetria local

O miner expõe uma API JSON em `127.0.0.1:4048` (`--api-bind`) com hashrate, shares e uptime — mesmo espírito do `/api/status` do NerdOS. Integração com o Fleet do NerdOS está no roadmap.

```bash
echo '{"command":"summary"}' | nc 127.0.0.1 4048
```

## Estrutura do fork

- Núcleo de mineração: **intacto** (upstream). Único patch de código: declarações explícitas em `algo-gate-api.c` para o Clang do Xcode (C23) + banner opcional `-DCH_BUILD`.
- Camada CH: `ch/` (builds, perfis, lançador) e este README.
- Upstream README: [docs/UPSTREAM-README.md](docs/UPSTREAM-README.md) · Instruções originais: `INSTALL_LINUX`, `INSTALL_WINDOWS`, `README.txt`.

## Licença e marca

- **Código**: [GPL-2.0](COPYING), herdada do cpuminer-opt. Atribuição integral a JayDDee e aos autores históricos (pooler, tpruvot, Jeff Garzik et al.).
- **Marca**: "Cripto Host" e "CriptoHost CPUMiner" são marca da Cripto Host — mesmo modelo do NerdOS ([BRANDING.md](https://github.com/criptohost/criptohost-nerdos/blob/master/BRANDING.md)): forke o código à vontade, remova a marca.
- A linha de doação BTC do upstream foi **mantida** no banner — o mérito do miner é dele.

---

*Feito com 💜 pela comunidade Cripto Host — Small power. Big learning.*
