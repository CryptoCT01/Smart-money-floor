"""Venus core-pool account limits via VenusLens (Unitroller diamond is not callable)."""
from __future__ import annotations

from typing import Any

from .cache import get_or_set
from .rpc import pad_addr, rpc

LENS = "0xe797804c5d4410777c70EF8769c4eB9c39BEF662"
UNITROLLER = "0xfD36E2c2a6789Db23113685031d7F16329158384"
# keccak256("getAccountLimits(address,address)")[:4]
SEL = "0x7dd8f6d9"
TTL = 20


def _load(address: str) -> dict[str, Any]:
    addr = address.strip()
    if not addr.startswith("0x") or len(addr) != 42:
        return {"ok": False, "error": "bad address"}
    data = SEL + pad_addr(UNITROLLER) + pad_addr(addr)
    try:
        raw = rpc("eth_call", [{"to": LENS, "data": data}, "latest"])
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "address": addr}
    hexdata = (raw or "0x")[2:]
    blob = bytes.fromhex(hexdata) if hexdata else b""
    if len(blob) < 128:
        return {"ok": False, "error": "short result", "address": addr, "raw": raw}
    # ABI: offset | markets_offset | liquidity | shortfall | ...
    liquidity = int.from_bytes(blob[64:96], "big")
    shortfall = int.from_bytes(blob[96:128], "big")
    liq_usd = liquidity / 1e18
    short_usd = shortfall / 1e18
    if short_usd > 0:
        status = "critical"
        hf = round(liq_usd / (liq_usd + short_usd), 3) if (liq_usd + short_usd) else 0.0
    elif liq_usd > 0:
        status = "healthy"
        hf = None  # Venus returns USD cushion, not Aave-style HF, when we lack borrow
    else:
        status = "no position"
        hf = None
    return {
        "ok": True,
        "address": addr,
        "source": "venus-lens",
        "comptroller": UNITROLLER,
        "liquidityUsd": liq_usd,
        "shortfallUsd": short_usd,
        "status": status,
        "healthFactor": hf,
        "note": "Core pool via VenusLens.getAccountLimits. Isolated pools not included.",
    }


def get_venus_account(address: str) -> dict[str, Any]:
    key = address.strip().lower()
    return get_or_set(f"venus:{key}", TTL, lambda: _load(address))
