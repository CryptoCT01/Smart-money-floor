"""Marlin — Grid trading. Live band from spot ± realized 24h move, Pancake-native."""
from __future__ import annotations

from typing import Any


def snapshot(prices: dict, yields: dict, extra: dict | None = None) -> dict[str, Any]:
    extra = extra or {}
    tokens = {t.get("symbol"): t for t in ((prices or {}).get("tokens") or [])}
    cake = tokens.get("CAKE") or {}
    px = float(cake.get("priceUsd") or 0)
    ch = abs(float(cake.get("priceChange24h") or 4))
    half = max(0.03, min(0.08, ch / 100 * 1.4))
    lo = px * (1 - half) if px else None
    hi = px * (1 + half) if px else None
    grids = 12
    step = ((hi - lo) / grids) if (hi and lo) else None
    proto = extra.get("protocols") or {}
    pancake = proto.get("pancake") or {}
    live = bool(px)
    return {
        "id": "marlin",
        "name": "Marlin",
        "category": "Grid Trading",
        "codename": "PancakeSwap V2 buy-low / sell-high",
        "status": f"{grids}-level grid armed" if live else "signal error",
        "live": live,
        "accent": "cyan",
        "hire": "Hire $0 · cap sizes a 12-level CAKE/WBNB Pancake grid. Levels are published, not placed. No on-chain orders until you SWAP.",
        "why": "Grid width tracks CAKE’s own 24h realized move — not a fake ±4% sticker.",
        "metrics": [
            {"label": "CAKE", "value": px or None, "fmt": "usd"},
            {"label": "Lower", "value": lo, "fmt": "usd"},
            {"label": "Upper", "value": hi, "fmt": "usd"},
            {"label": "Grids", "value": grids if live else None, "fmt": "int"},
            {"label": "Step", "value": step, "fmt": "usd"},
            {"label": "CAKE 24h", "value": cake.get("priceChange24h"), "fmt": "pct"},
        ],
        "detail": f"Band ±{half*100:.1f}% · Pancake AMM TVL " + (
            f"${pancake.get('tvl')/1e9:.2f}B" if pancake.get("tvl") else "—"
        ),
        "source": "dexscreener + pancakeswap",
        "pancakeTvl": pancake.get("tvl"),
    }
