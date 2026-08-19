/* CriptoHost NerdOS — app.js (todas as páginas; roteia por body[data-page]) */
(function () {
  "use strict";
  var page = document.body.dataset.page;
  var $ = function (id) { return document.getElementById(id); };
  var set = function (id, v) { var el = $(id); if (el) el.textContent = v; };

  function fmtUptime(s) {
    var d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600),
        m = Math.floor(s % 3600 / 60), ss = s % 60;
    return d + "d " + String(h).padStart(2, "0") + ":" + String(m).padStart(2, "0") + ":" + String(ss).padStart(2, "0");
  }

  function statusPill(status) {
    var pill = $("statuspill");
    if (!pill) return;
    pill.textContent = status === "mining" ? "Mining" : status === "connecting" ? "Connecting" : status;
    pill.className = "ch-pill " + (status === "mining" || status === "connecting" ? "ch-pill--mining" : "ch-pill--offline");
  }

  function mdnsHost(workerOrSt) {
    var host = "";
    if (workerOrSt && typeof workerOrSt === "object")
      host = workerOrSt.hostname || "";
    if (!host) {
      var src = (workerOrSt && typeof workerOrSt === "object") ? workerOrSt.worker : workerOrSt;
      host = String(src || "criptohost").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    }
    if (host.length > 31) host = host.slice(0, 31);
    return (host || "criptohost") + ".local";
  }

  function miningSymbol(pool) {
    var parts = String(pool || "").split(":");
    var host = parts[0].toLowerCase();
    var port = +(parts[1] || 0);
    if (host.indexOf("letsmine") >= 0) {
      if (port === 3335) return "DGB";
      if (port === 3334 || port === 3434) return "BCH";
      if (port === 3333 || port === 3433) return "XEC";
      if (port === 3332 || port === 3432) return "BTC";
      if (port === 3347) return "PPC";
    }
    if (host.indexOf("digi") >= 0 || host.indexOf("hmpool") >= 0) return "DGB";
    if (host.indexOf("xec") >= 0) return "XEC";
    if (host.indexOf("bch") >= 0) return "BCH";
    if (host.indexOf("peercoin") >= 0 || host.indexOf("ppc") >= 0) return "PPC";
    return "BTC";
  }

  var miningSym = "DGB";

  // Média esperada por placa (escopo O1): DevKit ≥350, S3 ≥300, C3/C6 ≥250 kH/s.
  // Nó CPU não tem tabela — o alvo é o pico da própria sessão.
  var sessionPeakKhs = 0;
  function hashTargetKhs(st) {
    if (isCpuNode(st)) {
      sessionPeakKhs = Math.max(sessionPeakKhs, st.hashrate_khs);
      return sessionPeakKhs || 1;
    }
    var hw = st.hardware || "";
    if (/C3|C6/i.test(hw)) return 250;
    if (/S3/i.test(hw)) return 300;
    return 350;
  }

  var cfgWallet = "";

  function poolDashboardUrl(pool, wallet) {
    var parts = String(pool || "").split(":");
    var host = parts[0].toLowerCase();
    var port = +(parts[1] || 0);
    var addr = String(wallet || "").split(".")[0];
    if (!host) return "#";
    if (host.indexOf("hmpool") >= 0) {
      var base = host.indexOf("digi") >= 0 ? "https://digi.hmpool.io" : "https://hmpool.io";
      return addr ? base + "/miner.html?address=" + encodeURIComponent(addr) : base + "/miner.html";
    }
    if (host.indexOf("nerdminers.org") >= 0)
      return addr ? "https://nerdminers.org/?address=" + encodeURIComponent(addr) : "https://nerdminers.org";
    if (host.indexOf("nerdminer.io") >= 0)
      return addr ? "https://nerdminer.io/?address=" + encodeURIComponent(addr) : "https://nerdminer.io";
    if (host.indexOf("public-pool.io") >= 0)
      return addr ? "https://web.public-pool.io/#/" + encodeURIComponent(addr) : "https://web.public-pool.io";
    if (host.indexOf("letsmine") >= 0) {
      var coin = port === 3335 ? "dgb" : port === 3334 || port === 3434 ? "bch"
        : port === 3333 || port === 3433 ? "xec" : port === 3347 ? "ppc"
        : port === 3332 || port === 3432 ? "btc" : "";
      return coin ? "https://www.letsmine.it/coin/" + coin : "https://www.letsmine.it";
    }
    if (host.indexOf("pyblock") >= 0) return "https://pool.pyblock.xyz";
    if (host.indexOf("sethforprivacy") >= 0) return "https://pool.sethforprivacy.com";
    if (host.indexOf("solomining.de") >= 0) return "https://pool.solomining.de";
    if (host.indexOf("mining-dutch.nl") >= 0)
      return "https://www.mining-dutch.nl";
    return "https://" + host + (addr ? "/?address=" + encodeURIComponent(addr) : "");
  }

  function poolLink(pool, wallet) {
    var a = $("pool-link");
    if (!a || !pool) return;
    if (wallet != null) cfgWallet = wallet;
    a.href = poolDashboardUrl(pool, cfgWallet || wallet);
  }

  function ensurePoolNav(pool) {
    if (cfgWallet) { poolLink(pool, cfgWallet); return; }
    fetch("/api/config").then(function (r) { return r.json(); }).then(function (c) {
      cfgWallet = c.wallet || "";
      poolLink(pool || (c.pool + ":" + c.port), cfgWallet);
    }).catch(function () { if (pool) poolLink(pool, ""); });
  }

  // Escala automática: contrato fala kH/s; exibição sobe de unidade no milhar
  function fmtHash(khs) {
    if (khs >= 1e9) return { v: (khs / 1e9).toFixed(2), u: "TH/s" };
    if (khs >= 1e6) return { v: (khs / 1e6).toFixed(2), u: "GH/s" };
    if (khs >= 1e3) return { v: (khs / 1e3).toFixed(2), u: "MH/s" };
    return { v: khs.toFixed(1), u: "kH/s" };
  }
  function fmtHashStr(khs) { var f = fmtHash(khs); return f.v + " " + f.u; }

  function isCpuNode(st) { return st.platform === "cpu" || /-cpu\b/.test(st.fw || ""); }

  // Nó CPU: esconde o que não se aplica (OTA na nav, aba Wi-Fi no Config)
  var chromeAdapted = false;
  function adaptPlatform(st) {
    if (chromeAdapted || !isCpuNode(st)) return;
    chromeAdapted = true;
    document.querySelectorAll('.ch-nav-pills a[href="/ota.html"]').forEach(function (a) { a.remove(); });
    document.querySelectorAll('[data-cfg="wifi"]').forEach(function (t) { t.remove(); });
    var wifiCard = document.querySelector(".ch-wifi");
    if (wifiCard) wifiCard.classList.add("is-na");
  }

  function tempClass(t) { return t < 65 ? "temp-ok" : t < 85 ? "temp-warn" : "temp-hot"; }

  // ---------- HOME ----------
  var tempHist = [];        // sparkline: últimos ~40 pontos (≈3 min)
  var lastAccepted = -1, lastAcceptedAt = null;
  var lastUptime = 0, lastEvs = [], lastErrs = [], logTab = "all";

  function renderStatus(st) {
    statusPill(st.status);
    miningSym = miningSymbol(st.pool);
    highlightMiningChip();
    ensurePoolNav(st.pool);
    lastUptime = st.uptime_s || 0;
    adaptPlatform(st);
    var fh = fmtHash(st.hashrate_khs);
    set("hashrate", fh.v);
    set("hashrate-unit", fh.u);

    // Ring fill caps at the target; the % label can exceed 100 when the device outruns it.
    var target = hashTargetKhs(st);
    var ratio = st.hashrate_khs / target;
    var ring = $("ring");
    if (ring) {
      var C = 452.4, frac = Math.min(1, ratio);
      ring.style.strokeDashoffset = (C * (1 - frac)).toFixed(1);
      if (ring.parentElement) ring.parentElement.classList.toggle("is-over", ratio > 1);
    }
    var pct = $("ring-pct");
    if (pct) {
      pct.textContent = Math.round(ratio * 100) + "%";
      pct.style.color = ratio > 1 ? "var(--ch-pink)" : "";
    }
    set("ring-base", isCpuNode(st) ? "vs session peak (" + fmtHashStr(target) + ")"
                                    : "vs " + fmtHashStr(target) + " target");

    var line = $("status-line");
    if (line) {
      line.textContent = st.status + " · " + st.hardware;
      line.className = "ch-status-line " + (st.status === "mining" ? "ch-badge--mining" : "ch-badge--offline");
    }

    set("sh-accepted", st.shares.accepted);
    var tot = st.shares.accepted + st.shares.rejected;
    set("sh-eff", tot ? (st.shares.accepted / tot * 100).toFixed(1) + "%" : "—");

    // last share: cronômetro desde a última mudança em accepted
    if (st.shares.accepted !== lastAccepted) {
      if (lastAccepted >= 0) lastAcceptedAt = Date.now();
      lastAccepted = st.shares.accepted;
    }
    tickLastShare();

    // stream
    set("st-found", st.shares.found);
    set("st-sent", st.shares.sent);
    set("st-pending", st.shares.pending);
    set("st-accepted", st.shares.accepted);
    set("st-rejected", st.shares.rejected);

    // wi-fi (rssi 0 = nó cabeado/CPU: sem rádio a medir)
    if (!st.rssi_dbm) {
      set("rssi", "—");
      set("wifi-q", isCpuNode(st) ? "wired / n/a" : "");
      var bars0 = $("wifibars");
      if (bars0) [].forEach.call(bars0.children, function (b) { b.className = ""; });
    } else {
      set("rssi", st.rssi_dbm);
      var q = st.rssi_dbm >= -50 ? 5 : st.rssi_dbm >= -60 ? 4 : st.rssi_dbm >= -67 ? 3 : st.rssi_dbm >= -75 ? 2 : 1;
      set("wifi-q", ["", "Weak", "Fair", "OK", "Good", "Excellent"][q]);
      var bars = $("wifibars");
      if (bars) [].forEach.call(bars.children, function (b, i) { b.className = i < q ? "on" : ""; });
    }

    // temperatura + sparkline (0 = sensor não exposto, ex. macOS sem root)
    if (!st.temp_c) {
      set("temp", "—");
      return renderStatusTail(st);
    }
    set("temp", st.temp_c.toFixed(1));
    tempHist.push(st.temp_c);
    if (tempHist.length > 40) tempHist.shift();
    var sp = $("spark-line");
    if (sp && tempHist.length > 1) {
      var mn = Math.min.apply(null, tempHist) - 1, mx = Math.max.apply(null, tempHist) + 1;
      sp.setAttribute("points", tempHist.map(function (t, i) {
        return (i / (tempHist.length - 1) * 200).toFixed(1) + "," + (38 - (t - mn) / (mx - mn) * 36).toFixed(1);
      }).join(" "));
    }
    renderStatusTail(st);
  }

  function renderStatusTail(st) {
    set("uptime", fmtUptime(st.uptime_s));
    set("bestdiff", st.best_difficulty);
    set("templates", st.templates);
    set("valids", st.valid_blocks);
    set("pool-conn", st.status === "mining" ? "Mining" : st.status);
    set("fw", st.fw);

    set("w-worker", st.worker);
    set("w-pool", st.pool);
    set("w-hw", st.hardware);
    set("w-ip", st.ip);
    set("w-host", mdnsHost(st));
    set("w-status", st.status);
    set("w-mac", st.mac || "—");
    set("wifi-host", mdnsHost(st));
  }

  function isLogError(e) {
    if (e.type === "reject") return true;
    if (e.type === "conn" && /fail|error|lost|timeout/i.test(e.msg)) return true;
    return false;
  }

  function errKey(e) {
    return (e.t || 0) + "\0" + (e.type || "") + "\0" + (e.msg || "");
  }

  function mergeErrsFrom(evs) {
    var have = {};
    lastErrs.forEach(function (e) { have[errKey(e)] = true; });
    (evs || []).filter(isLogError).forEach(function (e) {
      var k = errKey(e);
      if (!have[k]) { lastErrs.unshift(e); have[k] = true; }
    });
    if (lastErrs.length > 48) lastErrs.length = 48;
  }

  function fmtWhen(e) {
    var ago = Math.max(0, lastUptime - (e.t || 0));
    var d = new Date(Date.now() - ago * 1000);
    return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }

  function lineHtml(e) {
    return '<div class="' + e.type + '"><time datetime="">' + fmtWhen(e) + "</time>" + e.msg + "</div>";
  }

  function paintLogs() {
    var all = $("log"), err = $("log-err"), n = $("log-err-n");
    if (all) all.innerHTML = lastEvs.length ? lastEvs.map(lineHtml).join("") : '<div class="empty">No events yet.</div>';
    if (err) err.innerHTML = lastErrs.length ? lastErrs.map(lineHtml).join("") : '<div class="empty">No errors recorded.</div>';
    if (n) { n.textContent = lastErrs.length; n.hidden = !lastErrs.length; }
    if (all) all.hidden = logTab !== "all";
    if (err) err.hidden = logTab !== "err";
  }

  function renderEvents(evs, errs) {
    lastEvs = evs || [];
    if (Array.isArray(errs)) lastErrs = errs;
    else mergeErrsFrom(lastEvs);
    paintLogs();

    var track = $("stream-track");
    if (track) {
      var dots = lastEvs.filter(function (e) { return ["share", "accept", "reject"].indexOf(e.type) >= 0; }).slice(0, 12);
      track.innerHTML = dots.map(function (e, i) {
        var left = 6 + (i / Math.max(1, dots.length - 1)) * 88;
        return '<i class="' + e.type + '" style="left:' + left.toFixed(1) + '%;animation-delay:' + (i * 0.2) + 's"></i>';
      }).join("");
    }
  }

  function tickLastShare() {
    set("last-share", lastAcceptedAt ? Math.round((Date.now() - lastAcceptedAt) / 1000) + " s" : "—");
  }

  function initHome() {
    function poll() {
      fetch("/api/status").then(function (r) { return r.json(); }).then(renderStatus).catch(function () {});
      fetch("/api/events").then(function (r) { return r.json(); }).then(function (evs) {
        return fetch("/api/errors").then(function (r) { return r.ok ? r.json() : null; })
          .catch(function () { return null; })
          .then(function (errs) { renderEvents(evs, errs); });
      }).catch(function () {});
    }
    try {
      var ws = new WebSocket("ws://" + location.host + "/ws");
      ws.onmessage = function (m) {
        var d = JSON.parse(m.data);
        if (d.status) { renderStatus(d.status); renderEvents(d.events || [], d.errors); }
        else renderStatus(d);
      };
      ws.onerror = ws.onclose = function () { setInterval(poll, 5000); };
    } catch (e) { setInterval(poll, 5000); }
    poll();
    marketCard();
    wireActions();
    setInterval(tickLastShare, 1000);
    document.querySelectorAll(".ch-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        logTab = tab.getAttribute("data-log") || "all";
        document.querySelectorAll(".ch-tab").forEach(function (t) {
          var on = t === tab;
          t.classList.toggle("is-on", on);
          t.setAttribute("aria-selected", on ? "true" : "false");
        });
        paintLogs();
      });
    });
    fetch("/api/config").then(function (r) { return r.json(); }).then(function (c) {
      cfgWallet = c.wallet || "";
      var w = String(c.wallet).split(".")[0];
      set("w-wallet", w.length > 14 ? w.slice(0, 8) + "…" + w.slice(-4) : w);
    }).catch(function () {});
  }

  // Preços via CoinGecko direto do browser (poupa heap do ESP32), cache 5 min
  var MKT_COINS = [
    { id: "bitcoin", sym: "BTC" },
    { id: "bitcoin-cash", sym: "BCH" },
    { id: "peercoin", sym: "PPC" },
    { id: "digibyte", sym: "DGB" },
    { id: "ecash", sym: "XEC" }
  ];

  function fmtUsd(n) {
    if (n == null) return "—";
    if (n >= 1000) return "$" + n.toLocaleString("en-US", { maximumFractionDigits: 0 });
    if (n >= 1) return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (n >= 0.01) return "$" + n.toFixed(4);
    return "$" + n.toFixed(6);
  }

  function highlightMiningChip() {
    var box = $("mkt-chips");
    if (!box) return;
    [].forEach.call(box.children, function (el) {
      var sym = el.getAttribute("data-sym");
      var on = sym === miningSym;
      el.classList.toggle("is-mining", on);
      var tag = el.querySelector(".sym");
      if (tag) tag.textContent = on ? sym + " · mining" : sym;
    });
  }

  function marketCard() {
    var KEY = "ch-market-v2", TTL = 5 * 60 * 1000;
    var ids = MKT_COINS.map(function (c) { return c.id; }).join(",");
    function render(d, ts) {
      var box = $("mkt-chips");
      if (!box) return;
      var rows = MKT_COINS.map(function (c) {
        var q = d[c.id] || {};
        return { id: c.id, sym: c.sym, usd: q.usd, chg: q.usd_24h_change };
      }).filter(function (r) { return r.usd != null; })
        .sort(function (a, b) { return b.usd - a.usd; });
      box.innerHTML = rows.map(function (r) {
        var chg = r.chg == null ? "" : ((r.chg >= 0 ? "▲ " : "▼ ") + Math.abs(r.chg).toFixed(2) + "%");
        var dir = r.chg == null ? "" : (r.chg >= 0 ? "up" : "down");
        return '<div class="ch-chip" data-sym="' + r.sym + '">' +
          '<div class="sym">' + r.sym + "</div>" +
          '<div class="val">' + fmtUsd(r.usd) + "</div>" +
          '<div class="chg ' + dir + '">' + chg + "</div></div>";
      }).join("");
      highlightMiningChip();
      set("mkt-age", "● market updated " + Math.round((Date.now() - ts) / 60000) + "m ago");
    }
    var c = null;
    try { c = JSON.parse(localStorage.getItem(KEY)); } catch (e) {}
    if (c && Date.now() - c.ts < TTL) { render(c.d, c.ts); }
    else {
      fetch("https://api.coingecko.com/api/v3/simple/price?ids=" + ids + "&vs_currencies=usd&include_24hr_change=true")
        .then(function (r) { return r.json(); })
        .then(function (d) {
          localStorage.setItem(KEY, JSON.stringify({ d: d, ts: Date.now() }));
          render(d, Date.now());
        })
        .catch(function () { if (c) render(c.d, c.ts); });
    }
    setTimeout(marketCard, TTL);
  }

  function wireActions() {
    var br = $("btn-restart"), bf = $("btn-factory");
    if (br) br.addEventListener("click", function () {
      if (confirm("Restart this device?")) fetch("/api/restart", { method: "POST" });
    });
    if (bf) bf.addEventListener("click", function () {
      // confirmação dupla (M2-08)
      if (!confirm("Factory reset: this erases Wi-Fi and configuration. Continue?")) return;
      if (!confirm("Are you sure? The device will return to the CriptoHostNerdOS-XXXX setup network.")) return;
      fetch("/api/factory-reset", { method: "POST" });
    });
  }

  // ---------- FLEET ----------
  function initFleet() {
    function card(st, ip) {
      var host = st.hostname || String(st.worker || "").toLowerCase().replace(/[^a-z0-9]+/g, "-");
      return '<article class="ch-card ch-devcard">' +
        "<h3>" + st.worker +
        ' <span class="' + (st.status === "mining" ? "ch-badge--mining" : "ch-badge--offline") + '" style="font-size:0.72rem;font-weight:700">● ' +
        (st.status === "mining" ? "Online" : st.status) + "</span></h3>" +
        '<div class="host">' + host + ".local</div>" +
        '<div class="ip">' + st.ip + "</div>" +
        '<div class="ch-devstrip">' +
        "<div><span>Hashrate</span>" + fmtHashStr(st.hashrate_khs) + "</div>" +
        (st.temp_c ? '<div class="' + tempClass(st.temp_c) + '"><span>Temp</span>' + st.temp_c.toFixed(0) + " °C</div>"
                   : "<div><span>Temp</span>—</div>") +
        "<div><span>Wi-Fi</span>" + (st.rssi_dbm ? st.rssi_dbm + " dBm" : "—") + "</div>" +
        "<div><span>Status</span>" + st.status + "</div>" +
        "</div>" +
        '<div class="meta"><span>Pool</span><b>' + st.pool + "</b></div>" +
        '<div class="meta"><span>MAC</span><b>' + (st.mac || "—") + "</b></div>" +
        '<div class="meta"><span>Version</span><b>' + st.fw + " · " + st.hardware + "</b></div>" +
        '<div class="ch-actions">' +
        '<a class="ch-btn ch-btn--ghost" href="http://' + ip + '/config.html">Config</a>' +
        (isCpuNode(st) ? "" : '<a class="ch-btn ch-btn--ghost" href="http://' + ip + '/ota.html">OTA</a>') +
        '<button type="button" class="ch-btn ch-btn--danger" data-act="restart" data-ip="' + ip + '">Restart</button>' +
        "</div></article>";
    }

    function refresh() {
      fetch("/api/fleet").then(function (r) { return r.json(); }).then(function (fleet) {
        statusPill(fleet.self.status);
        adaptPlatform(fleet.self);
        ensurePoolNav(fleet.self.pool);
        var nodes = [{ st: fleet.self, ip: location.host }];
        var peers = fleet.peers.filter(function (p) { return p.worker !== fleet.self.worker; });
        Promise.all(peers.map(function (p) {
          return fetch("http://" + p.ip + ":" + p.port + "/api/status", { signal: AbortSignal.timeout(4000) })
            .then(function (r) { return r.json(); })
            .then(function (st) { return { st: st, ip: (p.port && p.port != 80) ? p.ip + ":" + p.port : p.ip }; })
            .catch(function () { return null; });
        })).then(function (res) {
          res.filter(Boolean).forEach(function (n) { nodes.push(n); });
          $("fleet-cards").innerHTML = nodes.map(function (n) { return card(n.st, n.ip); }).join("");
          set("agg-online", nodes.length);
          var aggF = fmtHash(nodes.reduce(function (a, n) { return a + n.st.hashrate_khs; }, 0));
          set("agg-hash", aggF.v);
          set("agg-hash-unit", aggF.u);
          var withTemp = nodes.filter(function (n) { return n.st.temp_c > 0; });
          set("agg-temp", withTemp.length
            ? (withTemp.reduce(function (a, n) { return a + n.st.temp_c; }, 0) / withTemp.length).toFixed(1) : "—");
          set("scanline", "Scan complete — " + nodes.length + " device(s). Sorted by worker name; new scan every 10 s.");
        });
      }).catch(function () {});
    }

    document.addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-act]");
      if (!b) return;
      var act = b.dataset.act, ip = b.dataset.ip;
      if (act === "restart" && !confirm("Restart " + ip + "?")) return;
      fetch("http://" + ip + "/api/" + act, { method: "POST" }).catch(function () {});
    });
    var rescan = $("btn-rescan");
    if (rescan) rescan.addEventListener("click", function () {
      set("scanline", "Scanning the network via mDNS _criptohost._tcp…");
      refresh();
    });

    refresh();
    setInterval(refresh, 10000);
  }

  // ---------- CONFIG ----------
  function initConfig() {
    fetch("/api/config").then(function (r) { return r.json(); }).then(function (c) {
      $("pool").value = c.pool;
      $("port").value = c.port;
      $("wallet").value = c.wallet;
      $("password").value = c.password;
      if ($("timezone")) $("timezone").value = c.timezone;
      cfgWallet = c.wallet || "";
      poolLink(c.pool + ":" + c.port, cfgWallet);
    });
    var cfgWorker = "", cfgHost = "";
    fetch("/api/status").then(function (r) { return r.json(); }).then(function (st) {
      statusPill(st.status);
      adaptPlatform(st);
      cfgWorker = st.worker || "";
      cfgHost = st.hostname || "";
    }).catch(function () {});
    fetch("/api/wifi").then(function (r) { return r.json(); }).then(function (w) {
      if ($("wifi-ssid") && w.ssid) $("wifi-ssid").value = w.ssid;
      var now = w.ssid ? (w.ssid + (w.rssi != null ? " · " + w.rssi + " dBm" : "")) : "not connected";
      set("wifi-now", now);
    }).catch(function () {});

    document.querySelectorAll("[data-cfg]").forEach(function (tab) {
      tab.addEventListener("click", function () {
        var which = tab.getAttribute("data-cfg");
        document.querySelectorAll("[data-cfg]").forEach(function (t) {
          var on = t === tab;
          t.classList.toggle("is-on", on);
          t.setAttribute("aria-selected", on ? "true" : "false");
        });
        $("cfg-form").hidden = which !== "pool";
        $("wifi-form").hidden = which !== "wifi";
      });
    });

    $("profile").addEventListener("change", function () {
      if (!this.value) return;
      var p = this.value.split("|");
      $("pool").value = p[0];
      $("port").value = p[1];
    });

    $("cfg-form").addEventListener("submit", function (ev) {
      ev.preventDefault();
      set("cfg-msg", "Saving…");
      fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pool: $("pool").value.trim(),
          port: +$("port").value,
          wallet: $("wallet").value.trim(),
          password: $("password").value,
          timezone: +$("timezone").value
        })
      }).then(function (r) { return r.json(); }).then(function (d) {
        set("cfg-msg", d.ok ? "Saved. Restarting — wait ~20 s and reload." : (d.error || "error"));
      }).catch(function () { set("cfg-msg", "Failed to save."); });
    });

    $("wifi-pick").addEventListener("change", function () {
      if (this.value) $("wifi-ssid").value = this.value;
    });

    $("btn-wifi-scan").addEventListener("click", function () {
      var btn = $("btn-wifi-scan");
      btn.disabled = true;
      set("wifi-msg", "Scanning nearby networks…");
      fetch("/api/wifi/scan").then(function () {
        return new Promise(function (resolve) { setTimeout(resolve, 3500); });
      }).then(function () { return fetch("/api/wifi/scan"); })
        .then(function (r) { return r.json(); })
        .then(function (list) {
          var sel = $("wifi-pick");
          sel.innerHTML = '<option value="">— pick a network —</option>';
          (list || []).forEach(function (n) {
            var opt = document.createElement("option");
            opt.value = n.ssid;
            opt.textContent = n.ssid + "  " + n.rssi + " dBm" + (n.open ? "  open" : "");
            sel.appendChild(opt);
          });
          set("wifi-msg", list && list.length ? list.length + " network(s) found." : "No networks found. Type the SSID.");
        })
        .catch(function () { set("wifi-msg", "Scan failed. Type the SSID."); })
        .then(function () { btn.disabled = false; });
    });

    $("wifi-form").addEventListener("submit", function (ev) {
      ev.preventDefault();
      var ssid = $("wifi-ssid").value.trim();
      var pass = $("wifi-pass").value;
      if (!ssid) { set("wifi-msg", "SSID is required."); return; }
      if (pass.length && pass.length < 8) { set("wifi-msg", "Password must be empty (open) or at least 8 characters."); return; }
      set("wifi-msg", "Saving Wi-Fi… the dashboard will drop when the radio switches.");
      fetch("/api/wifi", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ssid: ssid, password: pass })
      }).then(function (r) { return r.json(); }).then(function (d) {
        set("wifi-msg", d.ok
          ? "Saved. Restarting — join the new network and open http://" + (cfgHost ? cfgHost + ".local" : mdnsHost(cfgWorker || "criptohost"))
          : (d.error || "error"));
      }).catch(function () { set("wifi-msg", "Failed to save. If the radio already moved, look for CriptoHostNerdOS-XXXX."); });
    });
  }

  // ---------- OTA ----------
  function initOta() {
    fetch("/api/config").then(function (r) { return r.json(); }).then(function (c) {
      set("fw-hw", c.hardware);
      set("fw-cur", c.fw);
      cfgWallet = c.wallet || "";
      poolLink(c.pool + ":" + c.port, cfgWallet);
    });
    fetch("/api/status").then(function (r) { return r.json(); }).then(function (st) { statusPill(st.status); }).catch(function () {});

    var drop = $("ota-drop"), file = $("ota-file"), fname = $("ota-filename");
    var picked = null;
    function showFile(f) {
      picked = f || null;
      if (fname) fname.textContent = f ? f.name : "Drop the .bin here or click to choose";
    }
    if (file) file.addEventListener("change", function () { showFile(this.files[0]); });
    if (drop) {
      ["dragenter", "dragover"].forEach(function (ev) {
        drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add("is-drag"); });
      });
      ["dragleave", "drop"].forEach(function (ev) {
        drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove("is-drag"); });
      });
      drop.addEventListener("drop", function (e) {
        var f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
        if (!f) return;
        showFile(f);
      });
    }

    var otaXhr = null;
    function resetOtaBar() {
      $("ota-bar").style.width = "0%";
    }
    function failOta(msg) {
      otaXhr = null;
      $("ota-btn").disabled = false;
      set("ota-msg", msg);
    }
    function sleep(ms) {
      return new Promise(function (resolve) { setTimeout(resolve, ms); });
    }
    function waitOtaReady(tries) {
      if (tries <= 0) return Promise.resolve(false);
      return fetch("/api/ota/status").then(function (r) { return r.json(); }).then(function (s) {
        if (s.error) throw new Error(s.error);
        if (s.ready) return true;
        var left = Math.ceil(tries * 0.4);
        set("ota-msg", "Preparing flash… " + left + "s left. Keep this page open.");
        return sleep(400).then(function () { return waitOtaReady(tries - 1); });
      });
    }
    function startUpload(f) {
      var fd = new FormData();
      fd.append("firmware", f, f.name);
      var xhr = new XMLHttpRequest();
      otaXhr = xhr;
      xhr.open("POST", "/api/ota");
      xhr.timeout = 10 * 60 * 1000;
      xhr.upload.onprogress = function (e) {
        if (e.lengthComputable) {
          var pct = Math.round(e.loaded / e.total * 100);
          $("ota-bar").style.width = pct + "%";
          set("ota-msg", "Uploading… " + pct + "% — keep this page open.");
        }
      };
      xhr.onload = function () {
        if (xhr.status === 200) {
          $("ota-bar").style.width = "100%";
          set("ota-msg", "Update applied. Restarting — reload in ~30 s.");
          setTimeout(function () { location.href = "/"; }, 30000);
        } else {
          var msg = "Update failed";
          try { msg = JSON.parse(xhr.responseText).error || msg; } catch (e) {}
          resetOtaBar();
          failOta(msg + " — device stays on the current firmware. You can retry.");
        }
      };
      xhr.onerror = xhr.ontimeout = xhr.onabort = function () {
        resetOtaBar();
        failOta("Connection lost during upload. Mining will resume — wait a few seconds and try again.");
      };
      xhr.send(fd);
    }

    $("ota-form").addEventListener("submit", function (ev) {
      ev.preventDefault();
      var f = picked || (file && file.files[0]);
      if (!f) return;
      if (!/\.bin$/i.test(f.name)) { set("ota-msg", "Select a .bin file"); return; }
      if (otaXhr) { try { otaXhr.abort(); } catch (e) {} otaXhr = null; }
      resetOtaBar();
      $("ota-btn").disabled = true;
      set("ota-msg", "Pausing miner…");
      fetch("/api/ota/prepare", { method: "POST" }).then(function (r) {
        if (r.status === 404) {
          resetOtaBar();
          failOta("This firmware cannot OTA while mining. Flash once over USB.");
          return null;
        }
        if (!r.ok) {
          return r.json().then(function (d) {
            throw new Error(d.error || "prepare failed");
          }, function () { throw new Error("prepare failed"); });
        }
        return waitOtaReady(40);
      }).then(function (ready) {
        if (ready == null) return;
        if (!ready) {
          resetOtaBar();
          failOta("Flash prepare timed out. Erase and USB-flash the factory image once, then OTA works.");
          return;
        }
        startUpload(f);
      }).catch(function (e) {
        resetOtaBar();
        failOta((e && e.message) ? e.message : "Could not start OTA. USB-flash the factory image once.");
      });
    });
  }

  if (page === "home") initHome();
  else if (page === "fleet") initFleet();
  else if (page === "config") initConfig();
  else if (page === "ota") initOta();
})();
