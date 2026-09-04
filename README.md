<div align="center">

# ⛏️ CriptoHost CPUMiner

**O computador que você já tem — Windows, Linux ou Mac — minerando SHA-256 na mesma frota das suas plaquinhas.**

🇧🇷 Português · [🇺🇸 English](README.en.md)

[![license](https://img.shields.io/badge/license-GPL--2.0-blue)](COPYING)
[![upstream](https://img.shields.io/badge/fork%20de-cpuminer--opt%20v26.1-8b5cf6)](https://github.com/JayDDee/cpuminer-opt)

*Um produto [Cripto Host](https://cripto.host) — "Miner de um jeito fácil"*

</div>

---

## 🧭 O que é isso?

O CriptoHost CPUMiner é o irmão de mesa do [CriptoHost NerdOS](https://github.com/criptohost/criptohost_nerdos): um **minerador SHA-256d de CPU** em modo CLI para Windows, Linux e macOS, com menu interativo, o **mesmo dashboard web** das placas ESP32 e integração automática ao Fleet. Fork do [cpuminer-opt](https://github.com/JayDDee/cpuminer-opt) do JayDDee — o minerador de CPU mais rápido da categoria (instruções SHA-NI no x86, extensões SHA2/NEON no ARM).

> ⚠️ **Enquadramento honesto**: hobby e educação. Um Apple M2 faz ~165 MH/s; um ASIC faz 200 TH/s — 1,2 milhão de vezes mais. O log do próprio miner estima ~3.400 anos para achar um bloco DGB sozinho. O valor está em aprender Stratum, vardiff e otimização de CPU vendo shares aceitos em segundos.

## ✨ O que ele faz

- 🖥️ **Multi-plataforma** — Windows, Linux, macOS (Intel e Apple Silicon) e até [Android](https://github.com/criptohost/criptohost_mobile)
- ⚡ **Caminho rápido da sua CPU** — SHA-NI/AVX2 no x86, crypto ARMv8 no Apple Silicon e ARM — detectado automaticamente
- 🧙 **CLI interativo** — menu para wallet, pool, worker, threads e password, com persistência (`./ch/mine.sh`)
- 📊 **Mesmo dashboard das placas** — CH Agent serve a UI na porta 8091: hashrate, shares, best difficulty, log de erros com motivo real
- 🕸️ **Entra no Fleet automaticamente** — mDNS `_criptohost._tcp`; sem multicast (datacenter/Android), lista de peers por IP
- 🔁 **Lista de peers replicada** — edite a lista em qualquer nó (PC ou placa) e todos os outros sincronizam sozinhos em ~1 min; nó novo recebe a frota inteira no primeiro ciclo
- 🔐 **Token de acesso para nós expostos** — requests de IP público exigem `X-CH-Token` (gerado sozinho, impresso no start); na LAN nada muda. `CH_AUTH=always|off` ajusta
- 🔭 **Descobre mineradores de terceiros** — Bitaxe, NerdQAxe/NerdOctaxe (família AxeOS) e ASICs Antminer (firmware stock ou Braiins OS, via API CGMiner na porta 4028) aparecem no Fleet em cartão âmbar com hashrate, temperatura, pool e versão
- 🗺️ **Órbita da rede + edição de peers pela tela** — mapa vivo da frota e editor do `ch/peers.conf` direto no Fleet
- 🔄 **Atualização pela interface** — botão "Update node" no dashboard faz git pull, recompila se o core mudou e reinicia miner+agent sozinho (essencial para Android e servidores remotos)
- 🔁 **Supervisão** — o agent religa o miner se ele cair e loga o motivo

## 🖼️ Telas

Capturas reais de um Apple M2 minerando a ~165 MH/s, com o Fleet enxergando placas ESP32 e Android.

| | Desktop | Mobile |
|---|---|---|
| **Home** | ![Home](docs/screenshots/mac-home-desktop.png) | <img src="docs/screenshots/mac-home-mobile.png" width="260"> |
| **Fleet** | ![Fleet](docs/screenshots/mac-fleet-desktop.png) | <img src="docs/screenshots/mac-fleet-mobile.png" width="260"> |
| **Config** | ![Config](docs/screenshots/mac-config-desktop.png) | <img src="docs/screenshots/mac-config-mobile.png" width="260"> |

## 🚀 Comece em 5 minutos

**Você vai precisar de:** um computador e uma carteira da moeda (DigiByte recomendado).

### 🍎 macOS

```bash
xcode-select --install
brew install autoconf automake jansson openssl@3 curl
git clone https://github.com/criptohost/criptohost_cpuminer && cd criptohost_cpuminer
./ch/build-macos.sh
./ch/mine.sh
```

### 🐧 Linux (Debian/Ubuntu)

```bash
sudo apt-get update && sudo apt-get install -y build-essential automake libssl-dev libcurl4-openssl-dev libjansson-dev libgmp-dev zlib1g-dev
git clone https://github.com/criptohost/criptohost_cpuminer && cd criptohost_cpuminer
./ch/build-linux.sh
./ch/mine.sh
```

### 🤖 Android (Termux, sem loja)

```bash
curl -fsSL https://raw.githubusercontent.com/criptohost/criptohost_mobile/main/setup-termux.sh | bash
```

### 🪟 Windows

Use o executável pré-compilado das [Releases do upstream](https://github.com/JayDDee/cpuminer-opt/releases) com nossos perfis (`cpuminer-avx2-sha.exe -c ch\conf\dgb-hmpool.json`), ou compile via MSYS2 (`INSTALL_WINDOWS`).

### O menu

```
 CriptoHost CPUMiner — configuração
 ──────────────────────────────────────
  [1] Iniciar mineração (só terminal)
  [2] Iniciar com dashboard web (CH Agent)   ← recomendado
  [3] Wallet   [4] Pool   [5] Worker   [6] Threads   [7] Password
```

Escolha **[2]**, abra `http://localhost:8091` e veja os shares chegando. 🎉

## 🕸️ A frota (e os irmãos do ecossistema)

O CH Agent faz o PC falar o contrato CriptoHost (`_criptohost._tcp` + `GET /api/status`) — ele aparece no Fleet das placas e as placas aparecem no dele.

| Repositório | O que minera | Hashrate típico |
|---|---|---|
| [criptohost_nerdos](https://github.com/criptohost/criptohost_nerdos) | ESP32 (DevKit V1, S3, T-Display) | ~350 kH/s |
| **criptohost_cpuminer** (este) | Windows, Linux e macOS (CPU) | 20–165 MH/s |
| [criptohost_mobile](https://github.com/criptohost/criptohost_mobile) | Android via Termux (iOS = painel) | ~47 MH/s |

**Rede sem mDNS** (datacenter, Android): edite a lista de peers pela tela Fleet (ou `ch/peers.conf`), um `ip[:porta] [token]` por linha — o Fleet soma esses nós aos descobertos, e a lista **replica sozinha para a frota inteira** (revisão mais nova vence). O `token` dá acesso a nós expostos na internet: cada agent gera o seu no primeiro start e imprime o link `http://IP:8091/?token=…` — de IP público, a API só responde com ele.

## 🔌 API

Duas camadas: a API nativa do cpuminer (`127.0.0.1:4048`, formato `KEY=VAL`) e o **CH Agent** traduzindo para o contrato do ecossistema:

```bash
curl http://localhost:8091/api/status   # mesmo JSON das placas ESP32
```

O agent ainda extrai do log do miner o que a API nativa não expõe: best difficulty, pool jobs e motivos de rejeição (aba Errors do dashboard).

## ⛏️ Pools e moedas

Default **DigiByte na hmpool** (`digi.hmpool.io:3337`, password `X`). Perfis prontos em `ch/conf/`: DGB, BTC (lottery), XEC, BCH. Dica de vardiff: a pool ajusta a dificuldade para ~1 share/30 s por worker — um PC rápido recebe shares "mais pesados", não mais shares; **no PPLNS o crédito é dificuldade × shares**, então nada se perde.

## ❓ Perguntas honestas

**Vou ganhar dinheiro?** Não — veja o enquadramento lá em cima. **Posso rodar num servidor de produção?** Pode, mas limite as threads (`[6]` no menu) para sobrar CPU para a aplicação. **Meu antivírus reclamou.** Falso-positivo clássico de mineradores; o código é aberto para auditoria (nota herdada do upstream).

## 🧑‍💻 Para desenvolvedores

- `ch/` é a camada Cripto Host (menu, agent, perfis, builds); o core de mineração do upstream fica intacto — patches mínimos documentados nos commits (dois deles candidatos a PR upstream: fix de build no Clang/C23 e um buffer overflow no `api.c`).
- Branch `main` = camada CH · branch `upstream` = espelho limpo do cpuminer-opt para rebase.
- Dashboard: espelho de `criptohost_nerdos/data` em `ch/agent/web/` — sincronize com `./ch/agent/sync-web.sh`.

## 📜 Licença, marca e créditos

- **Código**: [GPL-2.0](COPYING), herdada do [cpuminer-opt](https://github.com/JayDDee/cpuminer-opt) — crédito integral a JayDDee e aos autores históricos (pooler, tpruvot, Jeff Garzik et al.). A doação BTC do upstream permanece no banner não-CH.
- **Marca**: código livre, marca protegida — [BRANDING.md](https://github.com/criptohost/criptohost_nerdos/blob/main/BRANDING.md) do ecossistema.

## 💬 Contato

Dúvidas, ideias ou parceria: **fale@cripto.host** · Issues e PRs são bem-vindos.

---

<div align="center">

*Small power. Big learning.* 💜

</div>
