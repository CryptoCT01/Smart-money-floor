"""DeFiLlama yields — free, no auth. BSC pools + Venus markets (no 1M floor)."""
from __future__ import annotations

from typing import Any

from .cache import get_or_set
from .http import try_json

YIELDS_URL = "https://yields.llama.fi/pools"
TTL = 60
MIN_TVL = 1_000_000
VENUS_MIN = 50_000
BSC_CHAINS = {"bsc", "binance", "binance smart chain", "bnb", "bnb smart chain"}


def _is_bsc(pool: dict[str, Any]) -> bool:
    return str(pool.get("chain") or "").lower() in BSC_CHAINS


def _row(pool: dict[str, Any]) -> dict[str, Any]:
    return {
        "project": pool.get("project"),
        "symbol": pool.get("symbol"),
        "apy": float(pool.get("apy") or 0),
        "apyBase": float(pool.get("apyBase") or 0) if pool.get("apyBase") is not None else None,
        "apyReward": float(pool.get("apyReward") or 0) if pool.get("apyReward") is not None else None,
        "tvlUsd": float(pool.get("tvlUsd") or 0),
        "stablecoin": bool(pool.get("stablecoin")),
        "ilRisk": pool.get("ilRisk"),
        "exposure": pool.get("exposure"),
        "pool": pool.get("pool"),
        "predicted": (pool.get("predictions") or {}).get("predictedClass"),
        "mu": pool.get("mu"),
    }


def _load() -> dict[str, Any]:
    raw, err = try_json(YIELDS_URL, timeout=22)
    if err or not isinstance(raw, dict):
        return {"ok": False, "source": "defillama", "error": err or "empty", "pools": [], "count": 0}

    data = raw.get("data") or []
    bsc_all = [_row(p) for p in data if _is_bsc(p)]
    bsc = [p for p in bsc_all if p["tvlUsd"] >= MIN_TVL]
    bsc.sort(key=lambda p: p["apy"], reverse=True)

    def match(needle: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        n = needle.lower()
        return [p for p in rows if n in str(p.get("project") or "").lower()]

    pancake = match("pancake", bsc)
    venus = [p for p in match("venus", bsc_all) if p["tvlUsd"] >= VENUS_MIN]
    venus.sort(key=lambda p: p["tvlUsd"], reverse=True)
    lista = match("lista", bsc)

    return {
        "ok": True,
        "source": "defillama",
        "count": len(bsc),
        "pools": bsc[:30],
        "pancake": pancake[:12],
        "venus": venus[:16],
        "lista": lista[:6],
        "top": bsc[0] if bsc else None,
    }


def get_yields() -> dict[str, Any]:
    return get_or_set("defillama:yields", TTL, _load)
