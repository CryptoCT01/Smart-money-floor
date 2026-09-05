"""Pulse — Health factor. Live Venus markets (BNB / stables / BTC), not SOL."""
from __future__ import annotations

from typing import Any


def snapshot(prices: dict, yields: dict, extra: dict | None = None) -> dict[str, Any]:
    extra = extra or {}
    venus = (yields or {}).get("venus") or []
    proto = extra.get("protocols") or {}
    tvl = proto.get("venusBscTvl")
    borrowed = proto.get("venusBscBorrowed")
    top = venus[0] if venus else None
    util = None
    if tvl and borrowed and (tvl + borrowed):
        util = borrowed / (tvl + borrowed) * 100
    live = bool(venus) or bool(tvl)
    return {
        "id": "pulse",
        "name": "Pulse",
        "category": "Health Factor",
        "codename": "Venus core-pool monitor · auto top-up later",
        "status": f"{len(venus)} Venus markets live" if venus else ("protocol TVL live" if tvl else "Venus unavailable"),
        "live": live,
        "accent": "green",
        "hire": "Hire $0. Watches Venus BSC utilisation and markets. Does not auto-repay. Alerts only until you act.",
        "why": "Liquidation is a health-factor problem. Pulse surfaces borrow, supply APR and protocol utilization on BSC.",
        "metrics": [
            {"label": "Venus BSC TVL", "value": tvl, "fmt": "usd_short"},
            {"label": "Borrowed", "value": borrowed, "fmt": "usd_short"},
            {"label": "Utilisation", "value": util, "fmt": "pct"},
            {"label": "Top market", "value": (top or {}).get("symbol"), "fmt": "text"},
            {"label": "Supply APR", "value": (top or {}).get("apy"), "fmt": "pct"},
            {"label": "Markets", "value": len(venus) or None, "fmt": "int"},
        ],
        "detail": "Core pool · BNB / USDT / BTCB — SOL is not a Venus market",
        "source": "defillama + venus",
        "markets": venus[:8],
    }
