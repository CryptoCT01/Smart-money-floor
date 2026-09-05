"""Live agent runtime. Ticks hired (and always-on watchers) with real market data only."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

STATE_LOCK = threading.Lock()
STATE: dict[str, Any] = {
    "running": False,
    "ticks": 0,
    "lastTick": None,
    "agents": {},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _blank(aid: str) -> dict[str, Any]:
    return {
        "id": aid,
        "running": False,
        "ticks": 0,
        "lastTs": None,
        "lastAction": "idle",
        "kind": "info",
        "data": {},
        "log": [],
        "startedAt": None,
    }


def snapshot() -> dict[str, Any]:
    with STATE_LOCK:
        return {
            "running": STATE["running"],
            "ticks": STATE["ticks"],
            "lastTick": STATE["lastTick"],
            "agents": {k: dict(v) for k, v in STATE["agents"].items()},
        }


def mark_hire(agent_id: str | None, hired: bool) -> None:
    with STATE_LOCK:
        if not agent_id:
            return
        row = STATE["agents"].setdefault(agent_id, _blank(agent_id))
        row["running"] = hired
        row["lastTs"] = utc_now()
        if hired:
            row["startedAt"] = utc_now()
            row["lastAction"] = "hired — live loop armed"
            row["kind"] = "ok"
            log = list(row.get("log") or [])
            log.insert(0, {"ts": utc_now(), "msg": "HIRED — watching live BSC prints", "kind": "ok"})
            row["log"] = log[:40]
        else:
            row["lastAction"] = "stopped"
            row["kind"] = "info"
            log = list(row.get("log") or [])
            log.insert(0, {"ts": utc_now(), "msg": "STOPPED by operator", "kind": "warn"})
            row["log"] = log[:40]
            row["startedAt"] = None


def _note(row: dict[str, Any], hired: bool) -> None:
    if not hired:
        return
    log = list(row.get("log") or [])
    msg = row.get("lastAction") or ""
    if log and log[0].get("msg") == msg:
        return
    log.insert(0, {"ts": utc_now(), "msg": msg, "kind": row.get("kind") or "ok"})
    row["log"] = log[:40]


def _ensure(aid: str) -> dict[str, Any]:
    row = STATE["agents"].get(aid)
    if not row:
        row = _blank(aid)
        STATE["agents"][aid] = row
    return row


def tick_once(floor: dict[str, Any], hire: dict[str, Any], push: Callable[[str, str], None]) -> dict[str, Any]:
    prices = floor.get("prices") or {}
    yields = floor.get("yields") or {}
    proto = floor.get("protocols") or {}
    hire_id = hire.get("agent")
    addr = hire.get("address") or ""
    tokens = {t.get("symbol"): t for t in (prices.get("tokens") or [])}
    cake = tokens.get("CAKE") or {}
    wbnb = prices.get("wbnb") or {}
    events: list[tuple[str, str, str]] = []

    with STATE_LOCK:
        STATE["ticks"] += 1
        STATE["lastTick"] = utc_now()
        STATE["running"] = True

        # Swordfish — live pair + security
        sf = _ensure("swordfish")
        sf["ticks"] += 1
        sf["lastTs"] = utc_now()
        ch = wbnb.get("priceChange24h")
        sf["data"] = {
            "price": wbnb.get("priceUsd"),
            "change24h": ch,
            "liq": wbnb.get("liquidityUsd"),
            "pair": wbnb.get("pair"),
        }
        sf["lastAction"] = (
            f"WBNB ${float(wbnb.get('priceUsd') or 0):,.2f} {float(ch or 0):+.2f}% · {wbnb.get('pair') or 'BSC'}"
            if wbnb.get("priceUsd")
            else "waiting DexScreener"
        )
        sf["kind"] = "ok" if wbnb.get("priceUsd") else "warn"
        if hire_id == "swordfish":
            events.append(("swordfish", sf["lastAction"], "ok"))

        # Marlin — real grid from CAKE realized range
        ml = _ensure("marlin")
        ml["ticks"] += 1
        ml["lastTs"] = utc_now()
        px = float(cake.get("priceUsd") or 0)
        ch_abs = abs(float(cake.get("priceChange24h") or 4))
        half = max(0.03, min(0.08, ch_abs / 100 * 1.4))
        lo, hi = (px * (1 - half), px * (1 + half)) if px else (None, None)
        prev = (ml.get("data") or {}).get("spot")
        crossed = None
        if prev and px:
            if px < float(prev) and lo and px <= lo * 1.002:
                crossed = "BUY"
            elif px > float(prev) and hi and px >= hi * 0.998:
                crossed = "SELL"
        ml["data"] = {"spot": px or None, "lower": lo, "upper": hi, "grids": 12 if px else 0, "crossed": crossed}
        if crossed:
            ml["lastAction"] = f"CAKE {crossed} grid hit · spot ${px:.4f} band {lo:.4f}–{hi:.4f}"
            ml["kind"] = "ok"
            events.append(("marlin", ml["lastAction"], "ok"))
        else:
            ml["lastAction"] = (
                f"CAKE ${px:.4f} · 12 grids ±{half*100:.1f}%" if px else "waiting CAKE"
            )
            ml["kind"] = "ok" if px else "warn"
        if hire_id == "marlin" and not crossed:
            events.append(("marlin", ml["lastAction"], "ok"))

        # Anchor — live Pancake pool vs IL / forecast
        an = _ensure("anchor")
        an["ticks"] += 1
        an["lastTs"] = utc_now()
        pancake = (yields.get("pancake") or [None])[0]
        an["data"] = pancake or {}
        if pancake:
            an["lastAction"] = (
                f"{pancake.get('symbol')} APR {float(pancake.get('apy') or 0):.2f}% · "
                f"IL {pancake.get('ilRisk') or '—'} · {pancake.get('predicted') or '—'}"
            )
            an["kind"] = "warn" if str(pancake.get("ilRisk") or "").lower() == "yes" else "ok"
        else:
            an["lastAction"] = "no Pancake pool ≥ $1M in live set"
            an["kind"] = "warn"
        if hire_id == "anchor":
            events.append(("anchor", an["lastAction"], an["kind"]))

        # Reef — live yield pick
        rf = _ensure("reef")
        rf["ticks"] += 1
        rf["lastTs"] = utc_now()
        pools = yields.get("pools") or []
        ranked = [
            p for p in pools
            if float(p.get("tvlUsd") or 0) >= 1_000_000 and 0 < float(p.get("apy") or 0) <= 400
        ]
        ranked.sort(key=lambda p: float(p.get("apy") or 0), reverse=True)
        top = ranked[0] if ranked else None
        prev_sym = (rf.get("data") or {}).get("symbol")
        rotated = bool(top and prev_sym and prev_sym != top.get("symbol"))
        rf["data"] = top or {}
        if top:
            rf["lastAction"] = (
                ("ROTATE → " if rotated else "HOLD ")
                + f"{top.get('project')} {top.get('symbol')} {float(top.get('apy') or 0):.2f}% "
                + f"TVL ${float(top.get('tvlUsd') or 0)/1e6:.1f}M"
            )
            rf["kind"] = "ok"
        else:
            rf["lastAction"] = "no qualifying yield"
            rf["kind"] = "warn"
        if hire_id == "reef" or rotated:
            events.append(("reef", rf["lastAction"], rf["kind"]))

        # Pulse — protocol + optional account
        pu = _ensure("pulse")
        pu["ticks"] += 1
        pu["lastTs"] = utc_now()
        tvl = proto.get("venusBscTvl")
        borrowed = proto.get("venusBscBorrowed")
        pu["data"] = {"tvl": tvl, "borrowed": borrowed, "address": addr or None}
        pu["lastAction"] = (
            f"Venus BSC TVL ${float(tvl)/1e9:.2f}B · borrowed ${float(borrowed)/1e9:.2f}B"
            if tvl
            else "Venus TVL unavailable"
        )
        pu["kind"] = "ok" if tvl else "warn"
        if hire_id == "pulse":
            events.append(("pulse", pu["lastAction"], pu["kind"]))

        # Helmsman — recompute live brief; log primary recommendation (no fake fills)
        hm = _ensure("helmsman")
        hm["ticks"] += 1
        hm["lastTs"] = utc_now()
        try:
            from skills.smart_money_brief import build_brief

            brief = build_brief(
                {
                    "prices": prices,
                    "yields": yields,
                    "scanner": floor.get("scanner") or {},
                    "security": floor.get("security") or {},
                    "scan": floor.get("scan") or {},
                    "protocols": proto,
                }
            )
            prim = brief.get("primary") or {}
            hm["data"] = {
                "primary": prim.get("agent"),
                "label": prim.get("label"),
                "reason": prim.get("reason"),
                "confidence": prim.get("confidence"),
                "actions": brief.get("actions") or [],
                "yieldTopApr": (brief.get("metrics") or {}).get("yieldTopApr"),
                "climber1h": (brief.get("metrics") or {}).get("climber1h"),
                "goplus": (brief.get("metrics") or {}).get("goplus"),
                "bscAgents": (brief.get("metrics") or {}).get("bscAgents"),
            }
            if prim.get("agent"):
                hm["lastAction"] = (
                    f"PRIMARY → {prim.get('agent')} · {prim.get('reason') or ''}"
                )[:220]
                hm["kind"] = "ok"
            else:
                hm["lastAction"] = "brief waiting on live inputs"
                hm["kind"] = "warn"
        except Exception as exc:  # noqa: BLE001
            hm["lastAction"] = f"brief error: {exc}"
            hm["kind"] = "err"
            hm["data"] = {}
        if hire_id == "helmsman":
            events.append(("helmsman", hm["lastAction"], hm.get("kind") or "ok"))

        _note(sf, hire_id == "swordfish")
        _note(ml, hire_id == "marlin")
        _note(an, hire_id == "anchor")
        _note(rf, hire_id == "reef")
        _note(pu, hire_id == "pulse")
        _note(hm, hire_id == "helmsman")

    for aid, msg, kind in events[:4]:
        push(f"{aid} · {msg}", kind)
    return snapshot()


def start_loop(get_floor: Callable[[], dict], get_hire: Callable[[], dict], push: Callable[[str, str], None], interval: float = 20.0) -> None:
    def _run() -> None:
        while True:
            try:
                tick_once(get_floor(), get_hire(), push)
            except Exception as exc:  # noqa: BLE001
                push(f"runtime error: {exc}", "err")
            time.sleep(interval)

    t = threading.Thread(target=_run, daemon=True, name="smf-runtime")
    t.start()
