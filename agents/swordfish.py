"""Swordfish — Trading. Live DexScreener + GoPlus security on the selected pair."""
from __future__ import annotations

from typing import Any


def snapshot(prices: dict, yields: dict, extra: dict | None = None) -> dict[str, Any]:
    extra = extra or {}
    wbnb = (prices or {}).get("wbnb") or {}
    tokens = (prices or {}).get("tokens") or []
    sec = extra.get("security") or {}
    sec_map = {t.get("symbol"): t for t in (sec.get("tokens") or [])}
    wbnb_sec = sec_map.get("WBNB") or {}
    vol = sum(float(t.get("volume24h") or 0) for t in tokens)
    live = bool(wbnb.get("priceUsd"))
    return {
        "id": "swordfish",
        "name": "Swordfish",
        "category": "Trading",
        "codename": "TWAK BSC swaps · DexScreener + GoPlus",
        "status": "watching BSC majors" if live else "signal error",
        "live": live,
        "accent": "gold",
        "hire": "Hire $0 · cap set here. GoPlus-gated BSC tape + Pancake quote. Funds never move on hire. SWAP is an extra capped click.",
        "why": "Real-time pair liquidity, 24h flow, and a honeypot/tax screen before size is committed.",
        "metrics": [
            {"label": "WBNB", "value": wbnb.get("priceUsd"), "fmt": "usd"},
            {"label": "24h", "value": wbnb.get("priceChange24h"), "fmt": "pct"},
            {"label": "Liq", "value": wbnb.get("liquidityUsd"), "fmt": "usd_short"},
            {"label": "Majors 24h vol", "value": vol or None, "fmt": "usd_short"},
            {"label": "Holders", "value": wbnb_sec.get("holders"), "fmt": "int"},
            {"label": "Honeypot", "value": "CLEAR" if wbnb_sec.get("ok") and not wbnb_sec.get("honeypot") else ("FLAG" if wbnb_sec.get("honeypot") else "—"), "fmt": "text"},
        ],
        "detail": (wbnb.get("pair") or "WBNB/USDT") + " · " + (wbnb.get("dex") or "pancakeswap"),
        "source": "dexscreener + goplus",
        "universe": len(tokens),
    }
