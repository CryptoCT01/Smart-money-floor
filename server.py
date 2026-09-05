#!/usr/bin/env python3
"""Smart Money Floor — BNB Agent Studio marketplace.

Stdlib only. python3 server.py  →  http://127.0.0.1:8090
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from urllib.parse import parse_qs, urlparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from agents import anchor, helmsman, jobs, marlin, pulse, reef, swordfish  # noqa: E402
from execution.swap import execute_swap  # noqa: E402
import runtime  # noqa: E402
from signals import (  # noqa: E402
    get_altana,
    get_chart,
    get_prices,
    get_protocols,
    get_scan,
    get_scanner,
    get_security,
    get_venus_account,
    get_wallet,
    get_yields,
)
from signals.pancake_quote import quote as pancake_quote  # noqa: E402
from signals.paper import get_record  # noqa: E402
PUBLIC_URL = ""

AGENT_WALLET = (os.environ.get("AGENT_WALLET") or "").strip()  # never hardcode a personal wallet in the public tree
HIRE_LOCK = threading.Lock()
HIRE: dict = {
    "address": "",
    "agent": None,
    "capUsd": 0.0,
    "duration": None,
    "hiredAt": None,
}

PORT = 8090
STARTED = datetime.now(timezone.utc)
FEED: list[dict] = []
FEED_LOCK = threading.Lock()
_PACK_LOCK = threading.Lock()
_PACK: dict | None = None
_PACK_AT = 0.0
PACK_TTL = 18.0
_FEED_FINGERPRINT = ""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def push_feed(msg: str, kind: str = "info") -> None:
    item = {"ts": utc_now(), "msg": msg, "kind": kind}
    with FEED_LOCK:
        FEED.insert(0, item)
        del FEED[40:]


def _meaningful_feed(prices: dict, yields: dict, scan: dict, security: dict, proto: dict) -> None:
    global _FEED_FINGERPRINT
    wbnb = (prices.get("wbnb") or {}).get("priceUsd")
    ch = (prices.get("wbnb") or {}).get("priceChange24h")
    fp = f"{round(float(wbnb or 0), 2)}|{round(float(ch or 0), 2)}|{(scan.get('totals') or {}).get('agents')}|{proto.get('venusBscTvl')}"
    if fp == _FEED_FINGERPRINT:
        return
    _FEED_FINGERPRINT = fp
    if wbnb:
        push_feed(f"WBNB ${wbnb:,.2f}  {ch:+.2f}% 24h" if ch is not None else f"WBNB ${wbnb:,.2f}", "ok")
    venus = (yields.get("venus") or [])[:1]
    if venus:
        p = venus[0]
        push_feed(f"Venus {p.get('symbol')}  APR {float(p.get('apy') or 0):.2f}%  TVL ${float(p.get('tvlUsd') or 0)/1e6:.1f}M", "ok")
    pancake = (yields.get("pancake") or [])[:1]
    if pancake:
        p = pancake[0]
        push_feed(f"Pancake {p.get('symbol')}  APR {float(p.get('apy') or 0):.2f}%", "ok")
    bsc = scan.get("bsc") or {}
    if bsc.get("agents"):
        push_feed(f"8004scan BSC  {bsc['agents']:,} registered agents  avg {(bsc.get('avgScore') or 0):.0f}", "ok")
    elif (scan.get("totals") or {}).get("agents"):
        t = scan["totals"]
        push_feed(f"8004scan  {t['agents']:,} agents  {t.get('feedbacks', 0):,} feedbacks", "ok")
    flagged = [t for t in (security.get("tokens") or []) if t.get("ok") and (t.get("honeypot") or not t.get("safe"))]
    if flagged:
        push_feed("GoPlus flag · " + ", ".join(t["symbol"] for t in flagged[:4]), "warn")
    else:
        n = sum(1 for t in (security.get("tokens") or []) if t.get("safe"))
        if n:
            push_feed(f"GoPlus  {n} majors clear of honeypot / high tax", "ok")
    if proto.get("venusBscTvl"):
        push_feed(f"Venus BSC TVL ${proto['venusBscTvl']/1e9:.2f}B", "ok")


def pack_floor() -> dict:
    global _PACK, _PACK_AT
    now = time.time()
    with _PACK_LOCK:
        if _PACK and now - _PACK_AT < PACK_TTL:
            return _PACK
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=8) as pool:
        f_px = pool.submit(get_prices)
        f_yd = pool.submit(get_yields)
        f_sc = pool.submit(get_scan)
        f_se = pool.submit(get_security)
        f_pr = pool.submit(get_protocols)
        f_al = pool.submit(get_altana)
        f_sn = pool.submit(get_scanner)
        prices = f_px.result()
        yields = f_yd.result()
        scan = f_sc.result()
        security = f_se.result()
        proto = f_pr.result()
        altana = f_al.result()
        scanner = f_sn.result()
    extra = {
        "security": security,
        "protocols": proto,
        "scan": scan,
        "altana": altana,
        "scanner": scanner,
    }
    agents = [
        swordfish.snapshot(prices, yields, extra),
        marlin.snapshot(prices, yields, extra),
        anchor.snapshot(prices, yields, extra),
        reef.snapshot(prices, yields, extra),
        pulse.snapshot(prices, yields, extra),
        helmsman.snapshot(prices, yields, extra),
    ]
    for a in agents:
        a["price"] = {"hireUsd": 0, "capUsd": 100, "note": "Hire is free. Spend cap is the only size you can SWAP."}
    elapsed_ms = int((time.time() - t0) * 1000)
    live = sum(1 for a in agents if a.get("live"))
    payload = {
        "ok": True,
        "ts": utc_now(),
        "elapsedMs": elapsed_ms,
        "agents": agents,
        "prices": prices,
        "yields": {
            "ok": yields.get("ok"),
            "count": yields.get("count"),
            "top": yields.get("top"),
            "pancake": (yields.get("pancake") or [])[:16],
            "venus": (yields.get("venus") or [])[:16],
            "lista": (yields.get("lista") or [])[:6],
            "pools": (yields.get("pools") or [])[:20],
        },
        "scan": scan,
        "security": security,
        "protocols": proto,
        "liveAgents": live,
        "agentWallet": AGENT_WALLET,
        "hire": dict(HIRE),
        "runtime": runtime.snapshot(),
        "altana": {"ok": altana.get("ok"), "count": altana.get("count"), "skills": (altana.get("skills") or [])[:10], "docs": altana.get("docs")},
        "scanner": scanner,
        "publicUrl": PUBLIC_URL,
        "categories": ["Grid Trading", "Rebalancing", "Yield Optimisation", "Health Factor", "Floor Captain"],
    }
    _meaningful_feed(prices, yields, scan, security, proto)
    with _PACK_LOCK:
        _PACK = payload
        _PACK_AT = time.time()
    return payload


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[{utc_now()}] {self.address_string()} {fmt % args}\n")

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            dash = ROOT / "marketplace" / "dashboard.html"
            data = dash.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/api/health":
            self._json(
                {
                    "ok": True,
                    "service": "smart-money-floor",
                    "port": PORT,
                    "started": STARTED.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "now": utc_now(),
                }
            )
            return
        if path == "/api/signals/prices":
            self._json(get_prices())
            return
        if path == "/api/signals/yields":
            self._json(get_yields())
            return
        if path == "/api/scan":
            self._json(get_scan())
            return
        if path == "/api/security":
            self._json(get_security())
            return
        if path in ("/api/agents", "/api/floor"):
            try:
                self._json(pack_floor())
            except Exception as exc:  # noqa: BLE001
                push_feed(f"floor failed: {exc}", "err")
                self._json({"ok": False, "error": str(exc), "ts": utc_now()}, 500)
            return
        if path == "/api/feed":
            with FEED_LOCK:
                items = list(FEED)
            self._json({"ok": True, "items": items})
            return
        if path.startswith("/api/chart"):
            q = parse_qs(urlparse(self.path).query)
            sym = (q.get("symbol") or ["WBNB"])[0]
            try:
                self._json(get_chart(sym))
            except Exception as exc:  # noqa: BLE001
                self._json({"ok": False, "error": str(exc), "points": []}, 500)
            return
        if path in ("/api/wallet", "/api/venus"):
            q = parse_qs(urlparse(self.path).query)
            addr = (q.get("address") or [HIRE.get("address") or AGENT_WALLET])[0]
            try:
                if path == "/api/wallet":
                    w = get_wallet(addr)
                    prices = get_prices()
                    px = {t["symbol"]: t.get("priceUsd") for t in (prices.get("tokens") or [])}
                    px["BNB"] = (prices.get("wbnb") or {}).get("priceUsd")
                    total = 0.0
                    for it in w.get("items") or []:
                        p = px.get(it["sym"]) or (px.get("WBNB") if it["sym"] == "BNB" else 0) or 0
                        it["usd"] = round(float(it["bal"]) * float(p), 4)
                        it["px"] = p
                        total += it["usd"]
                    w["totalUsd"] = round(total, 2)
                    self._json(w)
                else:
                    self._json(get_venus_account(addr))
            except Exception as exc:  # noqa: BLE001
                self._json({"ok": False, "error": str(exc)}, 500)
            return
        if path == "/api/session":
            self._json({"ok": True, "hire": dict(HIRE), "agentWallet": AGENT_WALLET, "runtime": runtime.snapshot(), "publicUrl": PUBLIC_URL})
            return
        if path == "/api/runtime":
            self._json({"ok": True, **runtime.snapshot()})
            return
        if path == "/api/altana":
            self._json(get_altana())
            return
        if path == "/api/scanner":
            self._json(get_scanner())
            return
        if path == "/api/job":
            q = parse_qs(urlparse(self.path).query)
            aid = (q.get("agent") or [HIRE.get("agent") or ""])[0]
            try:
                self._json({"ok": True, **jobs.run(aid, dict(HIRE))})
            except jobs.HireRequired as exc:
                self._json({"ok": False, "error": str(exc)}, 400)
            except Exception as exc:  # noqa: BLE001
                self._json({"ok": False, "error": str(exc)}, 500)
            return
        if path == "/api/record":
            self._json(get_record(float(HIRE.get("capUsd") or 100)))
            return
        if path == "/api/quote":
            q = parse_qs(urlparse(self.path).query)
            src = (q.get("from") or ["BNB"])[0]
            dst = (q.get("to") or ["CAKE"])[0]
            try:
                amt = float((q.get("amount") or ["0.02"])[0])
            except (TypeError, ValueError):
                amt = 0.02
            self._json(pancake_quote(src=src, dst=dst, amount=amt, prices=get_prices(), security=get_security()))
            return
        if path in ("/report", "/api/report"):
            p = ROOT / "report" / "advantage.html"
            if path == "/api/report":
                j = ROOT / "report" / "advantage.json"
                if j.exists():
                    self._json(json.loads(j.read_text()))
                    return
                self._json({"ok": False, "error": "run report/generate.py"}, 404)
                return
            if p.exists():
                data = p.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self._json({"ok": False, "error": "report not generated"}, 404)
            return
        return super().do_GET()

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        body = self._read_json()
        if path == "/api/hire":
            addr = str(body.get("address") or "").strip()
            agent = str(body.get("agent") or "").strip()
            try:
                cap = float(body.get("capUsd") or 0)
            except (TypeError, ValueError):
                cap = 0
            cap = max(0.0, min(cap, 100.0))
            with HIRE_LOCK:
                if addr.startswith("0x") and len(addr) == 42:
                    HIRE["address"] = addr
                HIRE["agent"] = agent or HIRE.get("agent")
                HIRE["capUsd"] = cap
                HIRE["duration"] = body.get("duration") or "24 hours"
                HIRE["hiredAt"] = utc_now()
            push_feed(f"hired {HIRE.get('agent')} · cap ${cap:.0f} · {(HIRE.get('address') or '')[:8]}…", "ok")
            runtime.mark_hire(HIRE.get("agent"), True)
            self._json({"ok": True, "hire": dict(HIRE), "runtime": runtime.snapshot()})
            return
        if path == "/api/stop":
            with HIRE_LOCK:
                old = HIRE.get("agent")
                HIRE["agent"] = None
                HIRE["capUsd"] = 0.0
                HIRE["duration"] = None
                HIRE["hiredAt"] = None
            if old:
                runtime.mark_hire(old, False)
                push_feed(f"stopped {old}", "warn")
            self._json({"ok": True, "hire": dict(HIRE), "runtime": runtime.snapshot()})
            return
        if path == "/api/bind":
            addr = str(body.get("address") or "").strip()
            if not (addr.startswith("0x") and len(addr) == 42):
                self._json({"ok": False, "error": "bad address"}, 400)
                return
            with HIRE_LOCK:
                HIRE["address"] = addr
            push_feed(f"wallet bound {addr[:8]}…{addr[-4:]}", "ok")
            self._json({"ok": True, "hire": dict(HIRE)})
            return
        if path == "/api/swap":
            src = str(body.get("from") or "")
            dst = str(body.get("to") or "")
            try:
                amt = float(body.get("amount") or 0)
            except (TypeError, ValueError):
                amt = 0
            prices = get_prices()
            pxmap = {t["symbol"]: float(t.get("priceUsd") or 0) for t in (prices.get("tokens") or [])}
            pxmap["BNB"] = float((prices.get("wbnb") or {}).get("priceUsd") or 0)
            key = "WBNB" if src.upper() in ("BNB", "WBNB") else src.upper()
            px = pxmap.get(key) or pxmap.get(src.upper()) or 0
            with HIRE_LOCK:
                cap = float(HIRE.get("capUsd") or 0)
                hired = HIRE.get("agent")
            if hired not in ("swordfish", "marlin"):
                self._json({"ok": False, "executed": False, "error": "hire Swordfish or Marlin first"}, 400)
                return
            result = execute_swap(src=src, dst=dst, amount=amt, cap_usd=cap, px_src=px)
            push_feed(
                ("swap ok " + (result.get("summary") or "")[:80]) if result.get("executed") else ("swap blocked: " + (result.get("error") or "")),
                "ok" if result.get("executed") else "warn",
            )
            self._json(result, 200 if result.get("ok") else 400)
            return
        self._json({"ok": False, "error": "not found"}, 404)


def main() -> None:
    global PUBLIC_URL
    url_file = ROOT / "public_url.txt"
    if url_file.exists():
        PUBLIC_URL = url_file.read_text().strip()
    push_feed("Smart Money Floor live · 6 agents ticking · Helmsman captain · 8004scan · Pancake · Venus · GoPlus · Altana skills", "ok")
    runtime.start_loop(pack_floor, lambda: dict(HIRE), push_feed, 8.0)
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Smart Money Floor  →  http://127.0.0.1:{PORT}", flush=True)
    if PUBLIC_URL:
        print(f"public  →  {PUBLIC_URL}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye", flush=True)


if __name__ == "__main__":
    main()
