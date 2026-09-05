"""Reef — Yield optimisation. Live DeFiLlama BSC ranking, no invented APRs."""
from __future__ import annotations

from typing import Any


def _safe(pools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for p in pools or []:
        apy = float(p.get("apy") or 0)
        tvl = float(p.get("tvlUsd") or 0)
        if tvl < 1_000_000 or apy <= 0 or apy > 400:
            continue
        if str(p.get("ilRisk") or "").lower() == "yes" and apy < 8:
            continue
        out.append(p)
    out.sort(key=lambda x: float(x.get("apy") or 0), reverse=True)
    return out


def snapshot(prices: dict, yields: dict, extra: dict | None = None) -> dict[str, Any]:
    extra = extra or {}
    ranked = _safe((yields or {}).get("pools") or [])
    # Prefer diversified: pancake / lista / venus first if competitive
    named = []
    for needle in ("lista", "venus", "pancake"):
        for p in ranked:
            if needle in str(p.get("project") or "").lower() and p not in named:
                named.append(p)
                break
    pick = named[0] if named else (ranked[0] if ranked else None)
    second = ranked[1] if len(ranked) > 1 else None
    delta = None
    if pick and second:
        delta = float(pick.get("apy") or 0) - float(second.get("apy") or 0)
    live = bool(pick)
    return {
        "id": "reef",
        "name": "Reef",
        "category": "Yield Optimisation",
        "codename": "BSC yield router · Lista / Venus / Pancake",
        "status": f"routing {pick.get('project')}" if pick else "yields unavailable",
        "live": live,
        "accent": "orange",
        "hire": "Hire $0. Ranks live BSC yields with Pancake in the mix. Does not deposit. You keep the funds.",
        "why": "Yield is a main-track category. Reef decides with live APR + TVL, not a brochure rate.",
        "metrics": [
            {"label": "Best APR", "value": (pick or {}).get("apy"), "fmt": "pct"},
            {"label": "Protocol", "value": (pick or {}).get("project"), "fmt": "text"},
            {"label": "Pool", "value": (pick or {}).get("symbol"), "fmt": "text"},
            {"label": "TVL", "value": (pick or {}).get("tvlUsd"), "fmt": "usd_short"},
            {"label": "Edge vs #2", "value": delta, "fmt": "pct"},
            {"label": "Universe", "value": len(ranked) or None, "fmt": "int"},
        ],
        "detail": (f"{pick.get('project')} {pick.get('symbol')}" if pick else "No qualifying BSC pool"),
        "source": "defillama",
        "pick": pick,
        "ranked": ranked[:8],
    }
