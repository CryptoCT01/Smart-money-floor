"""DeFiLlama protocol TVLs + PancakeSwap CAKE spot. No keys."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .cache import get_or_set
from .http import try_json

TTL = 60


def _load() -> dict[str, Any]:
    with ThreadPoolExecutor(max_workers=4) as pool:
        f_prots = pool.submit(try_json, "https://api.llama.fi/protocols", 20)
        f_chains = pool.submit(try_json, "https://api.llama.fi/v2/chains", 15)
        f_venus = pool.submit(try_json, "https://api.llama.fi/protocol/venus", 15)
        f_cake = pool.submit(try_json, "https://farms-api.pancakeswap.com/price/cake", 8)
        prots, e1 = f_prots.result()
        chains, e2 = f_chains.result()
        venus, e3 = f_venus.result()
        cake, e4 = f_cake.result()

    def pick(name: str) -> dict[str, Any] | None:
        if not isinstance(prots, list):
            return None
        for p in prots:
            if (p.get("name") or "").lower() == name.lower():
                tvl = p.get("tvl")
                bsc = (p.get("chainTvls") or {}).get("BSC")
                return {"name": p.get("name"), "tvl": tvl, "bscTvl": bsc, "category": p.get("category")}
        return None

    pancake = pick("PancakeSwap AMM") or pick("PancakeSwap AMM V3")
    pancake_v3 = pick("PancakeSwap AMM V3")
    bsc_tvl = None
    if isinstance(chains, list):
        for c in chains:
            if str(c.get("name") or "").lower() in ("bsc", "binance", "bnb", "bnb chain"):
                bsc_tvl = c.get("tvl")
                break

    venus_bsc = None
    venus_borrow = None
    if isinstance(venus, dict):
        ct = venus.get("currentChainTvls") or {}
        venus_bsc = ct.get("BSC")
        venus_borrow = ct.get("BSC-borrowed")

    cake_px = None
    if isinstance(cake, dict) and cake.get("price"):
        try:
            cake_px = float(cake["price"])
        except (TypeError, ValueError):
            cake_px = None

    return {
        "ok": pancake is not None or venus_bsc is not None,
        "errors": [e for e in (e1, e2, e3, e4) if e],
        "bscTvl": bsc_tvl,
        "pancake": pancake,
        "pancakeV3": pancake_v3,
        "venusBscTvl": venus_bsc,
        "venusBscBorrowed": venus_borrow,
        "cakeUsd": cake_px,
        "source": "defillama+pancakeswap",
    }


def get_protocols() -> dict[str, Any]:
    return get_or_set("protocols:floor", TTL, _load)
