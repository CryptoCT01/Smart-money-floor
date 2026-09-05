"""Anchor — Rebalancing. Live PancakeSwap V3 yields + IL / prediction flags."""
from __future__ import annotations

from typing import Any


def snapshot(prices: dict, yields: dict, extra: dict | None = None) -> dict[str, Any]:
    extra = extra or {}
    pancake = (yields or {}).get("pancake") or []
    top = pancake[0] if pancake else (yields or {}).get("top")
    proto = extra.get("protocols") or {}
    v3 = proto.get("pancakeV3") or {}
    live = bool(top)
    in_range = (top or {}).get("predicted") or "—"
    return {
        "id": "anchor",
        "name": "Anchor",
        "category": "Rebalancing",
        "codename": "PancakeSwap V3 LP range auto-reset",
        "status": "watching concentrated ranges" if live else "yields unavailable",
        "live": live,
        "accent": "purple",
        "hire": "When price leaves the LP tick range, remove liquidity and re-mint a new range around spot.",
        "why": "Fees drop to zero out of range. Anchor watches APR, TVL and IL so you rebalance on data, not vibes.",
        "metrics": [
            {"label": "Top APR", "value": (top or {}).get("apy"), "fmt": "pct"},
            {"label": "Pool TVL", "value": (top or {}).get("tvlUsd"), "fmt": "usd_short"},
            {"label": "Pool", "value": (top or {}).get("symbol"), "fmt": "text"},
            {"label": "IL risk", "value": (top or {}).get("ilRisk"), "fmt": "text"},
            {"label": "Forecast", "value": in_range, "fmt": "text"},
            {"label": "PCS V3 TVL", "value": v3.get("bscTvl") or v3.get("tvl"), "fmt": "usd_short"},
        ],
        "detail": ((top or {}).get("project") or "pancakeswap") + " · " + ((top or {}).get("symbol") or ""),
        "source": "defillama + pancakeswap",
        "pools": pancake[:6],
    }
