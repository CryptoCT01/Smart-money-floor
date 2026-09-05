"""GoPlus token security — free, no auth. BSC chain id 56."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .cache import get_or_set
from .http import try_json
from .dexscreener import WATCH

TTL = 90
URL = "https://api.gopluslabs.io/api/v1/token_security/56?contract_addresses={addr}"


def _one(symbol: str, addr: str) -> dict[str, Any]:
    data, err = try_json(URL.format(addr=addr), timeout=10)
    result = ((data or {}).get("result") or {}).get(addr.lower()) or {}
    if err or not result:
        return {"symbol": symbol, "address": addr, "ok": False, "error": err or "empty"}

    def flag(key: str) -> bool:
        return str(result.get(key) or "0") not in ("0", "false", "False", "")

    buy = result.get("buy_tax")
    sell = result.get("sell_tax")
    honeypot = flag("is_honeypot") or flag("honeypot_with_same_creator")
    return {
        "symbol": symbol,
        "address": addr,
        "ok": True,
        "honeypot": honeypot,
        "openSource": str(result.get("is_open_source") or "0") == "1",
        "buyTax": float(buy) if buy not in (None, "") else 0.0,
        "sellTax": float(sell) if sell not in (None, "") else 0.0,
        "holders": int(float(result.get("holder_count") or 0)),
        "ownerChangeBalance": flag("owner_change_balance"),
        "hiddenOwner": flag("hidden_owner"),
        "canTakeBack": flag("can_take_back_ownership"),
        "isMintable": flag("is_mintable"),
        "safe": (not honeypot) and float(buy or 0) < 10 and float(sell or 0) < 10,
    }


def _load() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = [pool.submit(_one, s, a) for s, a in WATCH]
        for fut in futs:
            rows.append(fut.result())
    order = {s: i for i, (s, _) in enumerate(WATCH)}
    rows.sort(key=lambda r: order.get(r["symbol"], 99))
    return {"ok": any(r.get("ok") for r in rows), "source": "goplus", "tokens": rows}


def get_security() -> dict[str, Any]:
    return get_or_set("goplus:bsc", TTL, _load)
