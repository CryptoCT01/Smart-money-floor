"""On-chain balances for a BSC address. Public RPC — not TWAK (TWAK can return empty lists)."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .cache import get_or_set
from .dexscreener import WATCH
from .rpc import pad_addr, rpc, to_int

DECIMALS = {
    "WBNB": 18, "BTCB": 18, "ETH": 18, "CAKE": 18, "USDT": 18, "USDC": 18,
    "SOL": 18, "XRP": 18, "ADA": 18, "DOGE": 8, "LINK": 18, "BNB": 18,
}
TTL = 15


def _bal_of(token: str, wallet: str) -> int:
    data = "0x70a08231" + pad_addr(wallet)
    return to_int(rpc("eth_call", [{"to": token, "data": data}, "latest"]))


def _load(address: str) -> dict[str, Any]:
    addr = address.strip()
    if not addr.startswith("0x") or len(addr) != 42:
        return {"ok": False, "error": "bad address", "address": addr, "items": [], "totalUsd": 0}
    bnb_wei = to_int(rpc("eth_getBalance", [addr, "latest"]))
    items: list[dict[str, Any]] = [
        {"sym": "BNB", "address": None, "bal": bnb_wei / 1e18, "raw": str(bnb_wei)}
    ]
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [(sym, token, pool.submit(_bal_of, token, addr)) for sym, token in WATCH]
        for sym, token, fut in futs:
            try:
                raw = fut.result()
            except Exception:  # noqa: BLE001
                continue
            dec = DECIMALS.get(sym, 18)
            bal = raw / (10 ** dec)
            if bal <= 0:
                continue
            if sym == "WBNB" and bal < 1e-8:
                continue
            items.append({"sym": sym, "address": token, "bal": bal, "raw": str(raw)})
    return {"ok": True, "address": addr, "items": items, "source": "bsc-rpc"}


def get_wallet(address: str) -> dict[str, Any]:
    key = address.strip().lower()
    return get_or_set(f"wallet:{key}", TTL, lambda: _load(address))
