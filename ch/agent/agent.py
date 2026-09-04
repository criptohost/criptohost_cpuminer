#!/usr/bin/env python3
"""CH Agent — dashboard web + nó de frota CriptoHost para o CPUMiner.

Faz o PC falar o contrato do CriptoHost NerdOS:
  - serve o mesmo dashboard web dos ESP32 (ch/agent/web/, espelho do data/ do NerdOS)
  - traduz a API nativa do cpuminer (127.0.0.1:4048) para GET /api/status
  - anuncia _criptohost._tcp via mDNS (aparece no Fleet das placas)
  - descobre as placas via mDNS (elas aparecem no Fleet dele)
  - gerencia o processo do miner (start/restart/config)

Uso: ./ch/agent/run.sh   (ou: python3 ch/agent/agent.py)
Dependência opcional: zeroconf (sem ela tudo funciona, menos o mDNS).
"""
import hmac, ipaddress, json, os, platform, re, secrets, shutil, signal, socket, subprocess, sys, threading, time, urllib.request, uuid
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
WEB = os.path.join(HERE, "web")
CONF = os.path.join(ROOT, "ch", "miner.conf")
MINER_API = ("127.0.0.1", 4048)
HTTP_PORT = int(os.environ.get("CH_AGENT_PORT", "8091"))
FW = "v0.2.0-cpu"
SERVICE = "_criptohost._tcp.local."

# ---------- token de acesso (nó exposto na internet) ----------
# Regra "auto": request de IP privado/loopback passa livre (LAN = confiável);
# IP público exige X-CH-Token. CH_AUTH=always força token para todos; =off desliga.
AUTH_MODE = os.environ.get("CH_AUTH", "auto")
TOKEN_FILE = os.path.join(HERE, "token")

def load_token():
    if not os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "w") as f:
            f.write(secrets.token_urlsafe(24))
        os.chmod(TOKEN_FILE, 0o600)
    return open(TOKEN_FILE).read().strip()

TOKEN = load_token()

# ---------- config (ch/miner.conf, KEY="VALUE") ----------
DEFAULTS = {"WALLET": "", "POOL_NAME": "dgb-hmpool",
            "POOL_URL": "stratum+tcp://digi.hmpool.io:3337",
            "WORKER": "CH-CPU-01", "THREADS": "0", "PASSWORD": "X"}

def load_conf():
    c = dict(DEFAULTS)
    if os.path.exists(CONF):
        for line in open(CONF):
            m = re.match(r'^(\w+)="?([^"]*)"?$', line.strip())
            if m:
                c[m.group(1)] = m.group(2)
    return c

def save_conf(c):
    with open(CONF, "w") as f:
        for k in DEFAULTS:
            f.write(f'{k}="{c.get(k, DEFAULTS[k])}"\n')

def pool_hostport(c):
    return re.sub(r"^stratum\+(tcp|ssl)://", "", c["POOL_URL"])

# ---------- hardware / rede ----------
def hardware_name():
    try:
        if "com.termux" in os.environ.get("PREFIX", ""):   # Android
            marca = subprocess.check_output(["getprop", "ro.product.manufacturer"], text=True).strip()
            modelo = subprocess.check_output(["getprop", "ro.product.model"], text=True).strip()
            if marca or modelo:
                return f"{marca} {modelo}".strip()
        if sys.platform == "darwin":
            return subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
        if sys.platform.startswith("linux"):
            for line in open("/proc/cpuinfo"):
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or platform.machine() or "CPU"

HW = hardware_name()

def mac_address():
    n = uuid.getnode()
    if (n >> 40) & 1:      # bit local/aleatório: uuid não achou MAC real
        return ""
    return ":".join(f"{(n >> i) & 0xFF:02X}" for i in range(40, -1, -8))

MAC = mac_address()

def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# ---------- processo do miner ----------
miner_proc = None
miner_lock = threading.Lock()

def miner_cmd(c):
    cmd = [os.path.join(ROOT, "cpuminer"), "-a", "sha256d",
           "-o", c["POOL_URL"], "-u", f'{c["WALLET"]}.{c["WORKER"]}',
           "-p", c["PASSWORD"], "-b", f"{MINER_API[0]}:{MINER_API[1]}"]
    if c["THREADS"] not in ("", "0"):
        cmd += ["-t", c["THREADS"]]
    return cmd

def build_hint():
    if "com.termux" in os.environ.get("PREFIX", ""):
        return "./ch/build-android.sh"
    return "./ch/build-macos.sh" if sys.platform == "darwin" else "./ch/build-linux.sh"

def start_miner():
    global miner_proc
    with miner_lock:
        c = load_conf()
        binpath = os.path.join(ROOT, "cpuminer")
        if not os.path.exists(binpath):
            msg = f"Miner binary missing — run {build_hint()} and restart"
            print(f"[agent] {msg}", flush=True)
            log_event("conn", msg)
            log_error(msg)
            return False
        if not c["WALLET"]:
            log_event("conn", "Wallet not set — miner stopped (use Config)")
            return False
        if miner_proc and miner_proc.poll() is None:
            miner_proc.terminate()
            try: miner_proc.wait(5)
            except subprocess.TimeoutExpired: miner_proc.kill()
        logf = open(os.path.join(HERE, "miner.log"), "ab")
        # sessão própria + SIGHUP ignorado herdado: o miner sobrevive ao terminal
        # que iniciou o agent (restore_signals=True devolveria o SIGHUP default)
        miner_proc = subprocess.Popen(miner_cmd(c), stdout=logf, stderr=logf, cwd=ROOT,
                                      start_new_session=True, restore_signals=False)
        log_event("conn", f"Miner started on {pool_hostport(c)}")

        def reaper(p):
            rc = p.wait()
            why = f"sinal {-rc} ({signal.Signals(-rc).name})" if rc < 0 else f"exit {rc}"
            print(f"[agent] miner pid {p.pid} morreu: {why}", flush=True)
            log_event("conn", f"Miner died ({why}) — restarting in 5 s")
            time.sleep(5)
            if miner_proc is p:   # ninguém reiniciou no meio tempo
                start_miner()
        threading.Thread(target=reaper, args=(miner_proc,), daemon=True).start()
        return True

# ---------- telemetria (poll da API do cpuminer) ----------
summary = {}      # último KEY=VAL da API 4048
events, errors = [], []
miner_stats = {"best": 0.0, "jobs": 0}   # extraído do miner.log (API não expõe)

def log_error(msg):
    errors.insert(0, {"t": int(summary.get("UPTIME", 0)), "type": "reject", "msg": msg})
    del errors[48:]

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
RE_SUBMIT = re.compile(r"Submitted Diff ([0-9.eE+-]+)")
RE_JOB = re.compile(r"New (Block|Work)[ :]")
RE_REASON = re.compile(r"Reject reason: (.+)")
RE_STALE = re.compile(r"\bStale (\d+)\b")

def tail_miner_log():
    # best diff, pool jobs e motivos de rejeição vivem só no log do miner
    path = os.path.join(HERE, "miner.log")
    pos = 0
    last_stale = 0
    while True:
        try:
            with open(path, "r", errors="replace") as f:
                size = os.path.getsize(path)
                if size < pos:
                    pos = 0          # log truncado (restart manual)
                f.seek(pos)
                for line in f:
                    ln = ANSI_RE.sub("", line)
                    m = RE_SUBMIT.search(ln)
                    if m:
                        try:
                            miner_stats["best"] = max(miner_stats["best"], float(m.group(1)))
                        except ValueError:
                            pass
                        continue
                    if RE_JOB.search(ln):
                        miner_stats["jobs"] += 1
                        continue
                    m = RE_REASON.search(ln)
                    if m:
                        log_error("Pool reject reason: " + m.group(1).strip())
                        continue
                    m = RE_STALE.search(ln)
                    if m and int(m.group(1)) > last_stale:
                        last_stale = int(m.group(1))
                        log_error(f"Stale share (#{last_stale}) — submitted after a new block")
                pos = f.tell()
        except FileNotFoundError:
            pass
        except Exception:
            pass
        time.sleep(2)

def log_event(typ, msg):
    events.insert(0, {"t": int(summary.get("UPTIME", 0)), "type": typ, "msg": msg})
    del events[24:]

def poll_miner():
    global summary
    last = {"ACC": 0, "REJ": 0, "SOL": 0, "mining": False}
    while True:
        try:
            s = socket.create_connection(MINER_API, timeout=2)
            s.sendall(b"summary\n")
            s.shutdown(socket.SHUT_WR)   # cpuminer responde após EOF do cliente
            data = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
            s.close()
            data = data.decode(errors="replace")
            kv = dict(p.split("=", 1) for p in data.rstrip("|").split(";") if "=" in p)
            summary = kv
            acc, rej, sol = int(kv.get("ACC", 0)), int(kv.get("REJ", 0)), int(kv.get("SOL", 0))
            if acc > last["ACC"]: log_event("accept", f"Share accepted by pool (#{acc})")
            if rej > last["REJ"]:
                log_event("reject", f"Share rejected by pool (#{rej})")
                log_error(f"Share rejected by pool (#{rej}) — see reason above if reported")
            if sol > last["SOL"]: log_event("block", "VALID BLOCK FOUND!")
            if not last["mining"]:
                log_event("conn", "Mining — miner API connected")
            last = {"ACC": acc, "REJ": rej, "SOL": sol, "mining": True}
        except Exception:
            if last["mining"]:
                log_event("conn", "Miner API unreachable — reconnecting")
            summary = {}
            last["mining"] = False
        time.sleep(5)

def status_json():
    c = load_conf()
    khs = float(summary.get("KHS", 0) or 0)
    acc = int(summary.get("ACC", 0) or 0)
    rej = int(summary.get("REJ", 0) or 0)
    mining = bool(summary) and khs > 0
    worker = c["WORKER"] or "CH-CPU-01"
    return {
        "worker": worker,
        "hostname": re.sub(r"[^a-z0-9]+", "-", worker.lower()).strip("-"),
        "ip": lan_ip(),
        "hardware": HW,
        "fw": FW,
        "platform": "cpu",
        "mac": MAC,
        "status": "mining" if mining else ("idle" if summary else "offline"),
        "hashrate_khs": round(khs, 1),
        "temp_c": float(summary.get("TEMP", 0) or 0),
        "rssi_dbm": 0,   # ponytail: PC cabeado/desktop — sem RSSI real
        "uptime_s": int(float(summary.get("UPTIME", 0) or 0)),
        "pool": pool_hostport(c),
        "shares": {"found": acc + rej, "sent": acc + rej, "accepted": acc,
                   "rejected": rej, "pending": 0},
        "best_difficulty": round(miner_stats["best"], 4),   # do miner.log
        "templates": miner_stats["jobs"],                    # jobs/new work recebidos
        "valid_blocks": int(summary.get("SOL", 0) or 0),
    }

# ---------- lista de peers replicada (gossip) ----------
# ch/peers.conf é um documento único replicado pela frota inteira: cada linha é
# 'ip[:porta] [token]' (porta default 80; token = acesso a nó exposto). ch/peers.rev
# guarda a revisão — editou em qualquer nó, a revisão maior vence e propaga.
PEERS_FILE = os.path.join(ROOT, "ch", "peers.conf")
REV_FILE = os.path.join(ROOT, "ch", "peers.rev")
peers_lock = threading.Lock()

PEER_LINE = re.compile(r"^[A-Za-z0-9._-]+(:\d{1,5})?( [A-Za-z0-9_-]+)?$")

def peers_content():
    return open(PEERS_FILE).read() if os.path.exists(PEERS_FILE) else ""

def peers_rev():
    try:
        return int(open(REV_FILE).read().strip())
    except (OSError, ValueError):
        return 0

def peers_validate(content):
    """Retorna a primeira linha inválida, ou None se tudo ok."""
    if len(content) > 8192:
        return "peers list too large"
    for ln in content.splitlines():
        ln = ln.split("#")[0].strip()
        if ln and not PEER_LINE.match(ln):
            return ln
    return None

def peers_save(content, rev):
    with peers_lock:
        with open(PEERS_FILE, "w") as f:
            f.write(content if content.endswith("\n") or not content else content + "\n")
        with open(REV_FILE, "w") as f:
            f.write(str(rev))

def static_peers():
    out = []
    for line in peers_content().splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        hostport, _, tok = line.partition(" ")
        host, _, port = hostport.partition(":")
        out.append({"worker": f"peer-{host}", "fw": "?", "hardware": "?",
                    "ip": host, "port": int(port or 80), "token": tok.strip()})
    return out

def peers_http(ip, port, tok, data=None, timeout=4):
    """GET/POST /api/peers de um vizinho, com token quando a linha dele tem."""
    req = urllib.request.Request(
        f"http://{ip}:{port}/api/peers",
        data=json.dumps(data).encode() if data is not None else None,
        headers={"X-CH-Token": tok} if tok else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def peers_sync_loop():
    """Gossip: revisão maior vence. Pull do vizinho mais novo; push para o mais
    velho (push cobre VPS, que não alcança a rede de casa para puxar)."""
    while True:
        time.sleep(60)
        my_ip = lan_ip()
        targets = {(p["ip"], p["port"], p.get("token", "")) for p in static_peers()}
        targets |= {(p["ip"], p["port"], "") for p in peers.values()}
        for ip, port, tok in sorted(targets):
            if ip == my_ip and port == HTTP_PORT:
                continue
            try:
                theirs = peers_http(ip, port, tok)
                trev = int(theirs.get("rev", 0) or 0)
                mine = peers_rev()
                if trev > mine and "content" in theirs:
                    content = str(theirs["content"])
                    if peers_validate(content) is None:
                        peers_save(content, trev)
                        log_event("conn", f"Fleet list updated from {ip} (rev {trev})")
                elif mine > trev:
                    peers_http(ip, port, tok, data={"content": peers_content(), "rev": mine})
            except Exception:
                pass

# ---------- self-update (git pull pela interface) ----------
update_state = {"running": False, "log": [], "done": None}

def _up_log(msg):
    update_state["log"].append(msg)
    del update_state["log"][:-30]
    log_event("conn", msg)

def run_update():
    def sh(cmd, timeout=1800):
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    try:
        _up_log("Update started — pulling from GitHub…")
        rc, head_before = sh(["git", "rev-parse", "HEAD"])
        rc, out = sh(["git", "pull", "--ff-only"], timeout=300)
        if rc != 0:
            _up_log("git pull failed: " + out[-200:])
            update_state["done"] = "error"
            return
        if "Already up to date" in out or "Already up-to-date" in out:
            _up_log("Node is already up to date.")
            update_state["done"] = "up-to-date"
            return
        rc, changed = sh(["git", "diff", "--name-only", head_before.strip(), "HEAD"])
        files = [f for f in changed.splitlines() if f.strip()]
        _up_log(f"Updated {len(files)} file(s).")
        core = [f for f in files
                if not f.startswith(("ch/agent/web/", "docs/", "ch/conf/"))
                and re.search(r"\.(c|h|S|am|ac|cpp)$|^Makefile|configure", f)]
        if core:
            _up_log("Mining core changed — rebuilding (this can take several minutes)…")
            script = build_hint().lstrip("./")
            rc, bout = sh(["bash", script], timeout=3600)
            if rc != 0:
                _up_log("Build failed — keeping the current binary. " + bout[-200:])
                update_state["done"] = "error"
                return
            _up_log("Build OK.")
        _up_log("Restarting node (agent + miner)…")
        update_state["done"] = "restarting"
        time.sleep(1.5)   # deixa a UI ler o estado
        try:
            if miner_proc and miner_proc.poll() is None:
                miner_proc.terminate()   # o novo agent sobe um miner limpo
                miner_proc.wait(5)
        except Exception:
            pass
        if zc_state:
            try:
                zc_state["zc"].unregister_service(zc_state["info"])
                zc_state["zc"].close()
            except Exception:
                pass
        os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)])
    except Exception as e:
        _up_log(f"Update error: {e.__class__.__name__}: {e}")
        update_state["done"] = "error"
    finally:
        if update_state["done"] != "restarting":
            update_state["running"] = False

# ---------- mineradores de terceiros (AxeOS: Bitaxe, NerdQAxe/NerdOctaxe…) ----------
foreign = {}        # ip -> status normalizado (contrato CH + platform="foreign")
http_hosts = set()  # candidatos vistos no browse _http._tcp

def probe_foreign(ip, port=80):
    """Família AxeOS responde GET /api/system/info — normaliza para o contrato CH."""
    try:
        with urllib.request.urlopen(f"http://{ip}:{port}/api/system/info", timeout=3) as r:
            d = json.load(r)
    except Exception:
        return None
    if not isinstance(d, dict) or ("hashRate" not in d and "ASICModel" not in d):
        return None
    ghs = float(d.get("hashRate", 0) or 0)
    acc = int(d.get("sharesAccepted", 0) or 0)
    rej = int(d.get("sharesRejected", 0) or 0)
    blob = json.dumps(d).lower()
    vendor = ("NerdOctaxe" if "octaxe" in blob else
              "NerdQAxe" if "qaxe" in blob or "nerdaxe" in blob else "Bitaxe/AxeOS")
    return {
        "worker": d.get("hostname") or f"axeos-{ip.replace('.', '-')}",
        "hostname": (d.get("hostname") or "").lower(),
        "ip": ip, "port": port,
        "platform": "foreign", "vendor": vendor,
        "hardware": d.get("ASICModel") or d.get("deviceModel") or "ASIC",
        "fw": str(d.get("version", "")),
        "status": "mining" if ghs > 0 else "idle",
        "hashrate_khs": round(ghs * 1e6, 1),   # AxeOS reporta GH/s
        "temp_c": float(d.get("temp", 0) or 0),
        "rssi_dbm": int(d.get("wifiRSSI", 0) or 0),
        "uptime_s": int(d.get("uptimeSeconds", 0) or 0),
        "pool": f'{d.get("stratumURL", "")}:{d.get("stratumPort", "")}'.strip(":"),
        "mac": d.get("macAddr") or d.get("macAddress") or "",
        "coin": "BTC",
        "shares": {"found": acc + rej, "sent": acc + rej,
                   "accepted": acc, "rejected": rej, "pending": 0},
        "best_difficulty": d.get("bestDiff", 0),
        "templates": 0, "valid_blocks": 0,
    }

def cgminer_cmd(ip, cmd, port=4028, timeout=3):
    """API CGMiner/BMMiner (Antminer stock, Braiins OS, cgminer/bfgminer)."""
    s = socket.create_connection((ip, port), timeout=timeout)
    try:
        s.sendall(json.dumps({"command": cmd}).encode())
        s.shutdown(socket.SHUT_WR)
        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
    finally:
        s.close()
    txt = data.rstrip(b"\x00").decode("utf8", "replace")
    # firmware stock emite JSON malformado no stats ("}{" entre objetos)
    return json.loads(txt.replace("}{", "},{"))

def probe_cgminer(ip, port=4028):
    """ASICs (Antminer S9/S19…, Braiins OS) na porta 4028 — normaliza p/ contrato CH."""
    try:
        summ = cgminer_cmd(ip, "summary")["SUMMARY"][0]
    except Exception:
        return None

    def opt(cmd, key):
        try:
            return cgminer_cmd(ip, cmd)[key]
        except Exception:
            return []

    ver = (opt("version", "VERSION") or [{}])[0]
    pools_ = opt("pools", "POOLS")
    alive = next((p for p in pools_ if p.get("Status") == "Alive"), pools_[0] if pools_ else {})
    temps = opt("temps", "TEMPS")          # Braiins OS
    devd = opt("devdetails", "DEVDETAILS")

    mhs = float(summ.get("MHS 5s") or summ.get("MHS av") or 0)
    ghs = float(summ.get("GHS 5s") or summ.get("GHS av") or 0)  # stock Antminer
    khs = mhs * 1000 if mhs else ghs * 1e6
    temp = max((float(t.get("Chip", 0) or 0) for t in temps), default=0)
    if not temp:  # stock: temp2_1..temp2_N no stats
        try:
            st0 = next(s for s in cgminer_cmd(ip, "stats")["STATS"] if any(k.startswith("temp2_") for k in s))
            temp = max(float(v) for k, v in st0.items() if k.startswith("temp2_") and v)
        except Exception:
            pass
    user = str(alive.get("User", ""))
    worker = user.split(".")[-1] if "." in user else f"asic-{ip.replace('.', '-')}"
    url = str(alive.get("URL", "")).replace("stratum+tcp://", "").replace("stratum2+tcp://", "")
    coin = next((c.upper() for c in ("dgb", "bch", "xec", "ppc") if c in url.lower()), "BTC")
    hardware = ver.get("Type") or (devd[0].get("Model") if devd else "") or "ASIC"
    vendor = "Braiins OS" if "BOSer" in ver else ("Antminer" if "antminer" in str(hardware).lower() else "CGMiner")
    return {
        "worker": worker, "hostname": worker.lower(),
        "ip": ip, "port": 80,   # UI web da máquina; a API 4028 é só do agent
        "platform": "foreign", "vendor": vendor,
        "hardware": hardware,
        "fw": str(ver.get("BOSer") or ver.get("CompileTime") or ver.get("Miner") or ""),
        "status": "mining" if khs > 0 else "idle",
        "hashrate_khs": round(khs, 1),
        "temp_c": temp, "rssi_dbm": 0,
        "uptime_s": int(summ.get("Elapsed", 0) or 0),
        "pool": url,
        "mac": "", "coin": coin,
        "shares": {"found": int(summ.get("Accepted", 0)) + int(summ.get("Rejected", 0)),
                   "sent": int(summ.get("Accepted", 0)) + int(summ.get("Rejected", 0)),
                   "accepted": int(summ.get("Accepted", 0)),
                   "rejected": int(summ.get("Rejected", 0)), "pending": 0},
        "best_difficulty": summ.get("Best Share", 0),
        "templates": 0, "valid_blocks": int(summ.get("Found Blocks", 0) or 0),
    }

def foreign_scan_loop():
    while True:
        my = lan_ip()
        ch_ips = {p["ip"] for p in peers.values()}
        cands = (http_hosts | {sp["ip"] for sp in static_peers()}) - ch_ips - {my, "127.0.0.1"}
        for ip in sorted(cands):
            info = probe_foreign(ip) or probe_cgminer(ip)
            if info:
                foreign[ip] = info
            elif ip in foreign:
                foreign.pop(ip, None)
        time.sleep(30)

# ---------- mDNS (opcional) ----------
peers = {}
try:
    from zeroconf import Zeroconf, ServiceInfo, ServiceBrowser
    HAVE_ZC = True
except ImportError:
    HAVE_ZC = False

zc_state = {}

def mdns_setup():
    if not HAVE_ZC:
        print("[agent] zeroconf ausente — mDNS desligado (pip install zeroconf)")
        return
    try:
        zc = Zeroconf()
        c = load_conf()
        worker = c["WORKER"] or "CH-CPU-01"
        info = ServiceInfo(
            SERVICE, f"{worker}.{SERVICE}",
            addresses=[socket.inet_aton(lan_ip())], port=HTTP_PORT,
            properties={"worker": worker, "fw": FW, "hardware": HW})
        # allow_name_change: instância antiga/registro velho na rede não derruba
        # o agent — o zeroconf renomeia (ex. CH-CPU-01-2) até o TTL expirar
        zc.register_service(info, allow_name_change=True)
        zc_state.update(zc=zc, info=info)
        print(f"[agent] mDNS: {info.name.split('.')[0]} anunciado em _criptohost._tcp:{HTTP_PORT}")
    except Exception as e:
        print(f"[agent] mDNS falhou ({e.__class__.__name__}: {e}) — dashboard segue sem mDNS")
        return

    class Listener:
        def add_service(self, zc, typ, name):
            i = zc.get_service_info(typ, name)
            if not i or not i.addresses:
                return
            p = {k.decode(): v.decode() for k, v in i.properties.items() if v}
            peers[name] = {"worker": p.get("worker", name.split(".")[0]),
                           "fw": p.get("fw", "?"), "hardware": p.get("hardware", "?"),
                           "ip": socket.inet_ntoa(i.addresses[0]), "port": i.port}
        update_service = add_service
        def remove_service(self, zc, typ, name):
            peers.pop(name, None)
    ServiceBrowser(zc, SERVICE, Listener())

    class HttpListener:   # candidatos a mineradores de terceiros
        def add_service(self, zc, typ, name):
            try:
                i = zc.get_service_info(typ, name, timeout=2500)
                if i and i.addresses:
                    http_hosts.add(socket.inet_ntoa(i.addresses[0]))
            except Exception:
                pass
        update_service = add_service
        def remove_service(self, *a):
            pass
    ServiceBrowser(zc, "_http._tcp.local.", HttpListener())

# ---------- HTTP ----------
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=WEB, **k)

    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _authorized(self):
        if AUTH_MODE == "off":
            return True
        if AUTH_MODE != "always":
            try:
                if ipaddress.ip_address(self.client_address[0].split("%")[0]).is_private:
                    return True
            except ValueError:
                pass
        tok = self.headers.get("X-CH-Token", "")
        if not tok and "token=" in self.path:
            m = re.search(r"[?&]token=([A-Za-z0-9_-]+)", self.path)
            tok = m.group(1) if m else ""
        return bool(tok) and hmac.compare_digest(tok, TOKEN)

    def _gate(self):
        """/api/* de origem pública exige token; estáticos ficam livres (a tela
        de 'cole o token' precisa carregar)."""
        if not self.path.startswith("/api/") or self._authorized():
            return True
        self._json({"error": "unauthorized"}, 401)
        return False

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-CH-Token")
        self.end_headers()

    def do_GET(self):
        if not self._gate():
            return
        p = self.path.split("?")[0]
        if p == "/api/status": return self._json(status_json())
        if p == "/api/events": return self._json(events)
        if p == "/api/errors": return self._json(errors)
        if p == "/api/fleet":
            self_st = status_json()
            plist = [x for x in peers.values() if x["worker"] != self_st["worker"]]
            # peers estáticos (ch/peers.conf): redes sem mDNS — datacenter, Android.
            # A lista replicada inclui todo mundo; cada nó pula a própria entrada.
            seen = {(x["ip"], x["port"]) for x in plist}
            my = lan_ip()
            for sp in static_peers():
                if (sp["ip"], sp["port"]) in seen or (sp["ip"] == my and sp["port"] == HTTP_PORT):
                    continue
                plist.append(sp)
            return self._json({"self": self_st, "peers": plist,
                               "foreign": list(foreign.values())})
        if p == "/api/config":
            c = load_conf()
            host, _, port = pool_hostport(c).partition(":")
            return self._json({"pool": host, "port": int(port or 3333),
                               "wallet": f'{c["WALLET"]}.{c["WORKER"]}',
                               "password": c["PASSWORD"], "timezone": -3,
                               "fw": FW, "hardware": HW})
        if p == "/api/update":
            return self._json({"running": update_state["running"],
                               "done": update_state["done"],
                               "log": update_state["log"][-8:]})
        if p == "/api/peers":
            return self._json({"content": peers_content(), "rev": peers_rev(),
                               "editable": True})
        if p == "/api/wifi":
            return self._json({"ssid": "", "rssi": None})  # PC: sem gestão de Wi-Fi
        if p == "/api/ota/status":
            return self._json({"error": "OTA does not apply to the CPUMiner — update via git pull"})
        return super().do_GET()

    def do_POST(self):
        if not self._gate():
            return
        p = self.path.split("?")[0]
        n = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(n) if n else b"{}"
        if p == "/api/config":
            try:
                d = json.loads(body)
            except ValueError:
                return self._json({"error": "json invalido"}, 400)
            c = load_conf()
            wallet = str(d.get("wallet", "")).strip()
            if wallet:
                w, _, worker = wallet.partition(".")
                c["WALLET"] = w
                if worker: c["WORKER"] = worker
            if d.get("pool"):
                c["POOL_URL"] = f'stratum+tcp://{d["pool"]}:{d.get("port", 3333)}'
                c["POOL_NAME"] = "custom"
            if "password" in d: c["PASSWORD"] = str(d["password"])
            save_conf(c)
            threading.Thread(target=start_miner, daemon=True).start()
            return self._json({"ok": True, "restarting": True})
        if p == "/api/peers":
            try:
                d = json.loads(body)
                content = str(d.get("content", ""))
                rev = int(d.get("rev", 0) or 0)
            except ValueError:
                return self._json({"error": "invalid json"}, 400)
            bad = peers_validate(content)
            if bad is not None:
                return self._json({"error": f"invalid line: {bad}"}, 400)
            mine = peers_rev()
            if rev:                      # push de sync de outro nó: rev maior vence
                if rev <= mine:
                    return self._json({"ok": False, "stale": True, "rev": mine})
            else:                        # edição humana: revisão nova, monotônica
                rev = max(int(time.time()), mine + 1)
            peers_save(content, rev)
            log_event("conn", f"Fleet peers updated (rev {rev})")
            return self._json({"ok": True, "rev": rev})
        if p == "/api/update":
            if update_state["running"]:
                return self._json({"error": "update already running"}, 409)
            update_state.update(running=True, log=[], done=None)
            threading.Thread(target=run_update, daemon=True).start()
            return self._json({"ok": True, "started": True})
        if p == "/api/restart":
            threading.Thread(target=start_miner, daemon=True).start()
            return self._json({"ok": True, "restarting": True})
        if p == "/api/identify":
            print("\a[agent] IDENTIFY — este é o nó " + load_conf()["WORKER"], flush=True)
            log_event("conn", "Identify triggered")
            return self._json({"ok": True})
        if p == "/api/factory-reset":
            return self._json({"error": "Factory reset does not apply to the CPUMiner"}, 400)
        if p in ("/api/ota", "/api/ota/prepare"):
            return self._json({"error": "OTA does not apply to the CPUMiner — update via git pull"}, 400)
        return self._json({"error": "not found"}, 404)

def main():
    if not os.path.isdir(WEB):
        sys.exit(f"[agent] {WEB} não existe — rode ch/agent/sync-web.sh primeiro")
    try:
        srv = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    except OSError as e:
        sys.exit(f"[agent] porta {HTTP_PORT} indisponível ({e.strerror}) — "
                 "já existe um agent rodando? (pkill -f agent.py)")
    threading.Thread(target=poll_miner, daemon=True).start()
    threading.Thread(target=tail_miner_log, daemon=True).start()
    threading.Thread(target=foreign_scan_loop, daemon=True).start()
    threading.Thread(target=peers_sync_loop, daemon=True).start()
    mdns_setup()
    start_miner()
    print(f"[agent] Dashboard: http://{lan_ip()}:{HTTP_PORT}  (local: http://localhost:{HTTP_PORT})")
    if AUTH_MODE != "off":
        print(f"[agent] Acesso remoto (IP público exige token): "
              f"http://SEU-IP:{HTTP_PORT}/?token={TOKEN}  — guarde este link")
    def bye(*_):
        if zc_state:   # remove o registro mDNS para não colidir no próximo start
            try:
                zc_state["zc"].unregister_service(zc_state["info"])
                zc_state["zc"].close()
            except Exception:
                pass
        if miner_proc and miner_proc.poll() is None:
            miner_proc.terminate()
        sys.exit(0)
    signal.signal(signal.SIGINT, bye)
    signal.signal(signal.SIGTERM, bye)
    srv.serve_forever()

if __name__ == "__main__":
    main()
