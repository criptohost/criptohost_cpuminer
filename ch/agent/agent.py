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
import json, os, platform, re, shutil, signal, socket, subprocess, sys, threading, time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
WEB = os.path.join(HERE, "web")
CONF = os.path.join(ROOT, "ch", "miner.conf")
MINER_API = ("127.0.0.1", 4048)
HTTP_PORT = int(os.environ.get("CH_AGENT_PORT", "8091"))
FW = "v0.1.0-cpu"
SERVICE = "_criptohost._tcp.local."

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

def start_miner():
    global miner_proc
    with miner_lock:
        c = load_conf()
        if not c["WALLET"]:
            log_event("conn", "Wallet não configurada — miner parado (use Config)")
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
        log_event("conn", f"Miner iniciado em {pool_hostport(c)}")

        def reaper(p):
            rc = p.wait()
            why = f"sinal {-rc} ({signal.Signals(-rc).name})" if rc < 0 else f"exit {rc}"
            print(f"[agent] miner pid {p.pid} morreu: {why}", flush=True)
            log_event("conn", f"Miner caiu ({why}) — reiniciando em 5s")
            time.sleep(5)
            if miner_proc is p:   # ninguém reiniciou no meio tempo
                start_miner()
        threading.Thread(target=reaper, args=(miner_proc,), daemon=True).start()
        return True

# ---------- telemetria (poll da API do cpuminer) ----------
summary = {}      # último KEY=VAL da API 4048
events, errors = [], []

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
            if acc > last["ACC"]: log_event("accept", f"Share aceito pela pool (#{acc})")
            if rej > last["REJ"]: log_event("reject", f"Share rejeitado pela pool (#{rej})")
            if sol > last["SOL"]: log_event("block", "BLOCO VALIDO ENCONTRADO!")
            if not last["mining"]:
                log_event("conn", "Minerando — API do miner conectada")
            last = {"ACC": acc, "REJ": rej, "SOL": sol, "mining": True}
        except Exception:
            if last["mining"]:
                log_event("conn", "API do miner indisponível — reconectando")
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
        "status": "mining" if mining else ("idle" if summary else "offline"),
        "hashrate_khs": round(khs, 1),
        "temp_c": float(summary.get("TEMP", 0) or 0),
        "rssi_dbm": 0,   # ponytail: PC cabeado/desktop — sem RSSI real
        "uptime_s": int(float(summary.get("UPTIME", 0) or 0)),
        "pool": pool_hostport(c),
        "shares": {"found": acc + rej, "sent": acc + rej, "accepted": acc,
                   "rejected": rej, "pending": 0},
        "best_difficulty": 0,   # a API do cpuminer não expõe best share diff
        "templates": 0,
        "valid_blocks": int(summary.get("SOL", 0) or 0),
    }

# ---------- mDNS (opcional) ----------
peers = {}
try:
    from zeroconf import Zeroconf, ServiceInfo, ServiceBrowser
    HAVE_ZC = True
except ImportError:
    HAVE_ZC = False

def mdns_setup():
    if not HAVE_ZC:
        print("[agent] zeroconf ausente — mDNS desligado (pip install zeroconf)")
        return
    zc = Zeroconf()
    c = load_conf()
    worker = c["WORKER"] or "CH-CPU-01"
    info = ServiceInfo(
        SERVICE, f"{worker}.{SERVICE}",
        addresses=[socket.inet_aton(lan_ip())], port=HTTP_PORT,
        properties={"worker": worker, "fw": FW, "hardware": HW})
    zc.register_service(info)
    print(f"[agent] mDNS: {worker} anunciado em _criptohost._tcp:{HTTP_PORT}")

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

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/api/status": return self._json(status_json())
        if p == "/api/events": return self._json(events)
        if p == "/api/errors": return self._json(errors)
        if p == "/api/fleet":
            self_st = status_json()
            plist = [x for x in peers.values() if x["worker"] != self_st["worker"]]
            return self._json({"self": self_st, "peers": plist})
        if p == "/api/config":
            c = load_conf()
            host, _, port = pool_hostport(c).partition(":")
            return self._json({"pool": host, "port": int(port or 3333),
                               "wallet": f'{c["WALLET"]}.{c["WORKER"]}',
                               "password": c["PASSWORD"], "timezone": -3,
                               "fw": FW, "hardware": HW})
        if p == "/api/wifi":
            return self._json({"ssid": "", "rssi": None})  # PC: sem gestão de Wi-Fi
        if p == "/api/ota/status":
            return self._json({"error": "OTA não se aplica ao CPUMiner — atualize via git pull"})
        return super().do_GET()

    def do_POST(self):
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
        if p == "/api/restart":
            threading.Thread(target=start_miner, daemon=True).start()
            return self._json({"ok": True, "restarting": True})
        if p == "/api/identify":
            print("\a[agent] IDENTIFY — este é o nó " + load_conf()["WORKER"], flush=True)
            log_event("conn", "Identify acionado")
            return self._json({"ok": True})
        if p == "/api/factory-reset":
            return self._json({"error": "factory reset não se aplica ao CPUMiner"}, 400)
        if p in ("/api/ota", "/api/ota/prepare"):
            return self._json({"error": "OTA não se aplica ao CPUMiner — atualize via git pull"}, 400)
        return self._json({"error": "not found"}, 404)

def main():
    if not os.path.isdir(WEB):
        sys.exit(f"[agent] {WEB} não existe — rode ch/agent/sync-web.sh primeiro")
    threading.Thread(target=poll_miner, daemon=True).start()
    mdns_setup()
    start_miner()
    srv = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    print(f"[agent] Dashboard: http://{lan_ip()}:{HTTP_PORT}  (local: http://localhost:{HTTP_PORT})")
    def bye(*_):
        if miner_proc and miner_proc.poll() is None:
            miner_proc.terminate()
        sys.exit(0)
    signal.signal(signal.SIGINT, bye)
    signal.signal(signal.SIGTERM, bye)
    srv.serve_forever()

if __name__ == "__main__":
    main()
