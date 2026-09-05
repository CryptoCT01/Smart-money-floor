"""Pancake-style quote. Never sends a transaction — funds stay in the wallet."""
from __future__ import annotations

from typing import Any

PCS_FEE = 0.0025  # Pancake V2 0.25%
SLIPPAGE = 0.005


def quote(*, src: str, dst: str, amount: float, prices: dict, security: dict | None = None) -> dict[str, Any]:
    src_u = (src or "").upper().replace("WBNB", "BNB") if (src or "").upper() == "WBNB" else (src or "").upper()
    dst_u = (dst or "").upper()
    tokens = {t.get("symbol"): t for t in ((prices or {}).get("tokens") or [])}
    wbnb = (prices or {}).get("wbnb") or {}
    px = {**{k: float(v.get("priceUsd") or 0) for k, v in tokens.items()}}
    if wbnb.get("priceUsd"):
        px["WBNB"] = float(wbnb["priceUsd"])
        px["BNB"] = float(wbnb["priceUsd"])
    src_px = px.get(src_u) or px.get("WBNB" if src_u == "BNB" else src_u) or 0
    dst_px = px.get(dst_u) or px.get("WBNB" if dst_u == "BNB" else dst_u) or 0
    if amount <= 0 or not src_px or not dst_px:
        return {"ok": False, "executed": False, "error": "need live prices and amount", "pancake": True}
    usd_in = amount * src_px
    gross = usd_in / dst_px
    fee = gross * PCS_FEE
    out = gross - fee
    min_out = out * (1 - SLIPPAGE)
    src_row = tokens.get("WBNB" if src_u == "BNB" else src_u) or wbnb
    dst_row = tokens.get("CAKE" if dst_u == "CAKE" else dst_u) or {}
    liq = float(src_row.get("liquidityUsd") or dst_row.get("liquidityUsd") or 0)
    impact = (usd_in / liq * 100) if liq else None
    sec_map = {t.get("symbol"): t for t in ((security or {}).get("tokens") or [])}
    gate = sec_map.get(dst_u) or sec_map.get("CAKE") or {}
    blocked = bool(gate.get("ok") and (gate.get("honeypot") or not gate.get("safe")))
    return {
        "ok": not blocked and out > 0,
        "executed": False,
        "pancake": True,
        "venue": "PancakeSwap V2 fee model · quote only",
        "from": src_u,
        "to": dst_u,
        "amountIn": amount,
        "usdIn": round(usd_in, 4),
        "feeBps": int(PCS_FEE * 10_000),
        "amountOut": round(out, 6),
        "minOut": round(min_out, 6),
        "slippage": SLIPPAGE,
        "priceImpactPct": round(impact, 4) if impact is not None else None,
        "liquidityUsd": liq or None,
        "goplus": {
            "symbol": gate.get("symbol"),
            "safe": gate.get("safe"),
            "honeypot": gate.get("honeypot"),
        },
        "blocked": blocked,
        "reason": "GoPlus honeypot/tax flag — quote refused" if blocked else "No tx. Funds never leave the wallet.",
    }
