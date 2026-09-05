"""Hired work products. A job only runs if that agent is hired through the marketplace."""
from __future__ import annotations

from typing import Any

from signals.defillama import get_yields
from signals.dexscreener import get_prices
from signals.pancake_quote import quote as pancake_quote
from signals.paper import get_record
from signals.protocols import get_protocols
from signals.security import get_security

from . import anchor, helmsman, marlin, pulse, reef, swordfish

LABOUR_USD_PER_HOUR = 50.0


class HireRequired(RuntimeError):
    pass


def _require(hire: dict | None, agent_id: str) -> dict:
    hire = hire or {}
    if hire.get("agent") != agent_id:
        raise HireRequired(f"hire {agent_id} through the marketplace first")
    return hire


def _extra(prices, yields, security, proto) -> dict:
    return {"security": security, "protocols": proto}


def swordfish_job(hire: dict | None = None) -> dict[str, Any]:
    hire = _require(hire, "swordfish")
    prices = get_prices()
    security = get_security()
    yields = get_yields()
    snap = swordfish.snapshot(prices, yields, _extra(prices, yields, security, {}))
    q = pancake_quote(src="BNB", dst="CAKE", amount=0.02, prices=prices, security=security)
    rec = (get_record(float(hire.get("capUsd") or 100)).get("swordfish") or {})
    flags = [t for t in (security.get("tokens") or []) if t.get("ok") and (t.get("honeypot") or not t.get("safe"))]
    safe = [t for t in (security.get("tokens") or []) if t.get("safe")]
    return {
        "agent": "swordfish",
        "category": "trading / security",
        "hired": True,
        "price": {"hireUsd": 0, "capUsd": float(hire.get("capUsd") or 0)},
        "headline": "GoPlus-gated BSC tape + Pancake quote (no tx)",
        "output": {
            "tape": snap.get("metrics"),
            "wbnb": (prices or {}).get("wbnb"),
            "goplusFlags": [t.get("symbol") for t in flags],
            "goplusClear": [t.get("symbol") for t in safe],
            "pancakeQuote": q,
            "paperRecord": {
                "winRatePct": rec.get("winRatePct"),
                "window": rec.get("window"),
                "maxDrawdownPct": rec.get("maxDrawdownPct"),
                "roundtrips": rec.get("roundtrips"),
                "label": rec.get("label"),
            },
        },
        "quality": {
            "fields": ["tape", "goplusFlags", "pancakeQuote", "paperRecord"],
            "actionable": bool(q.get("ok")) and not q.get("blocked"),
            "safetyGate": True,
            "fundsMoved": False,
        },
    }


def marlin_job(hire: dict | None = None) -> dict[str, Any]:
    hire = _require(hire, "marlin")
    prices = get_prices()
    yields = get_yields()
    proto = get_protocols()
    snap = marlin.snapshot(prices, yields, {"protocols": proto})
    tokens = {t.get("symbol"): t for t in ((prices or {}).get("tokens") or [])}
    cake = tokens.get("CAKE") or {}
    px = float(cake.get("priceUsd") or 0)
    metrics = {m["label"]: m.get("value") for m in (snap.get("metrics") or [])}
    lo, hi, grids = metrics.get("Lower"), metrics.get("Upper"), int(metrics.get("Grids") or 12)
    levels = []
    if px and lo and hi and grids:
        step = (hi - lo) / grids
        cap = float(hire.get("capUsd") or 100)
        usd_each = cap / grids
        for i in range(grids):
            level_px = lo + step * (i + 0.5)
            side = "buy" if level_px < px else "sell"
            levels.append({
                "n": i + 1,
                "px": round(level_px, 6),
                "side": side,
                "usd": round(usd_each, 4),
                "cake": round(usd_each / level_px, 6) if level_px else None,
            })
    rec = (get_record(float(hire.get("capUsd") or 100)).get("marlin") or {})
    return {
        "agent": "marlin",
        "category": "grid trading · PancakeSwap",
        "hired": True,
        "price": {"hireUsd": 0, "capUsd": float(hire.get("capUsd") or 0)},
        "headline": f"{len(levels)}-level CAKE/WBNB Pancake grid sized to cap — orders not placed",
        "output": {
            "spot": px,
            "band": {"lower": lo, "upper": hi, "grids": grids},
            "levels": levels,
            "pancakeTvl": snap.get("pancakeTvl"),
            "paperRecord": {
                "winRatePct": rec.get("winRatePct"),
                "window": rec.get("window"),
                "maxDrawdownPct": rec.get("maxDrawdownPct"),
                "roundtrips": rec.get("roundtrips"),
                "pnlUsd": rec.get("pnlUsd"),
                "label": rec.get("label"),
            },
        },
        "quality": {
            "fields": ["spot", "band", "levels", "paperRecord"],
            "actionable": len(levels) == 12,
            "safetyGate": True,
            "fundsMoved": False,
        },
    }


def anchor_job(hire: dict | None = None) -> dict[str, Any]:
    hire = _require(hire, "anchor")
    prices = get_prices()
    yields = get_yields()
    proto = get_protocols()
    snap = anchor.snapshot(prices, yields, {"protocols": proto})
    tokens = {t.get("symbol"): t for t in ((prices or {}).get("tokens") or [])}
    cake = tokens.get("CAKE") or {}
    px = float(cake.get("priceUsd") or 0)
    ch = abs(float(cake.get("priceChange24h") or 4)) / 100
    half = max(0.04, min(0.12, ch * 1.6))
    lo = px * (1 - half) if px else None
    hi = px * (1 + half) if px else None
    pools = snap.get("pools") or (yields.get("pancake") or [])
    top = pools[0] if pools else {}
    in_range = bool(px and lo and hi and lo <= px <= hi)
    plan = {
        "action": "HOLD range" if in_range else "RESET range around spot",
        "pair": "CAKE/WBNB",
        "spot": px,
        "suggestedLower": lo,
        "suggestedUpper": hi,
        "widthPct": round(half * 200, 2) if half else None,
        "inRange": in_range,
        "topPool": {
            "symbol": top.get("symbol"),
            "apy": top.get("apy"),
            "tvlUsd": top.get("tvlUsd"),
            "ilRisk": top.get("ilRisk"),
        },
        "minted": False,
        "note": "LP plan only. No V3 mint. Funds stay in the wallet.",
    }
    return {
        "agent": "anchor",
        "category": "rebalancing · PancakeSwap LPs",
        "hired": True,
        "price": {"hireUsd": 0, "capUsd": float(hire.get("capUsd") or 0)},
        "headline": f"Pancake V3 range plan · {plan['action']}",
        "output": plan,
        "quality": {
            "fields": ["action", "suggestedLower", "suggestedUpper", "inRange", "topPool"],
            "actionable": bool(lo and hi),
            "safetyGate": True,
            "fundsMoved": False,
        },
    }


def reef_job(hire: dict | None = None) -> dict[str, Any]:
    hire = _require(hire, "reef")
    prices = get_prices()
    yields = get_yields()
    snap = reef.snapshot(prices, yields, {})
    pancake = (yields.get("pancake") or [])[:8]
    pick = snap.get("pick") or {}
    return {
        "agent": "reef",
        "category": "yield · Pancake preference",
        "hired": True,
        "price": {"hireUsd": 0, "capUsd": float(hire.get("capUsd") or 0)},
        "headline": f"Top live pool {pick.get('project')} {pick.get('symbol')} — no deposit",
        "output": {
            "pick": pick,
            "pancakePools": pancake,
            "ranked": (snap.get("ranked") or [])[:8],
            "deposited": False,
        },
        "quality": {
            "fields": ["pick", "pancakePools", "ranked"],
            "actionable": bool(pick),
            "safetyGate": True,
            "fundsMoved": False,
        },
    }


def pulse_job(hire: dict | None = None) -> dict[str, Any]:
    hire = _require(hire, "pulse")
    prices = get_prices()
    yields = get_yields()
    proto = get_protocols()
    snap = pulse.snapshot(prices, yields, {"protocols": proto})
    return {
        "agent": "pulse",
        "category": "health factor",
        "hired": True,
        "price": {"hireUsd": 0, "capUsd": float(hire.get("capUsd") or 0)},
        "headline": "Venus BSC utilisation + markets — no auto repay",
        "output": {"metrics": snap.get("metrics"), "markets": snap.get("markets"), "repaid": False},
        "quality": {
            "fields": ["metrics", "markets"],
            "actionable": bool(snap.get("live")),
            "safetyGate": True,
            "fundsMoved": False,
        },
    }


def helmsman_job(hire: dict | None = None) -> dict[str, Any]:
    hire = _require(hire, "helmsman")
    prices = get_prices()
    yields = get_yields()
    extra = {"security": get_security(), "protocols": get_protocols()}
    snap = helmsman.snapshot(prices, yields, extra)
    brief = snap.get("brief") or {}
    return {
        "agent": "helmsman",
        "category": "floor captain",
        "hired": True,
        "price": {"hireUsd": 0, "capUsd": float(hire.get("capUsd") or 0)},
        "headline": (brief.get("primary") or {}).get("label") or "Live hire recommendation",
        "output": brief,
        "quality": {
            "fields": ["primary", "actions"],
            "actionable": bool((brief.get("primary") or {}).get("agent")),
            "safetyGate": True,
            "fundsMoved": False,
        },
    }


JOBS = {
    "swordfish": swordfish_job,
    "marlin": marlin_job,
    "anchor": anchor_job,
    "reef": reef_job,
    "pulse": pulse_job,
    "helmsman": helmsman_job,
}


def run(agent_id: str, hire: dict | None) -> dict[str, Any]:
    fn = JOBS.get(agent_id)
    if not fn:
        raise HireRequired(f"unknown agent {agent_id}")
    return fn(hire)


def labour_usd(seconds: float) -> float:
    return round(seconds / 3600.0 * LABOUR_USD_PER_HOUR, 4)
