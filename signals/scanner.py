"""BSC scanner — GeckoTerminal trending/new pools + DexScreener BSC boosts + live trades.

No invented tokens. Empty list if the API is quiet.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import time
from typing import Any

from .cache import get_or_set
from .http import try_json

TTL = 25
GT = "https://api.geckoterminal.com/api/v2/networks/bsc"
DEX_BOOSTS = "https://api.dexscreener.com/token-boosts/top/v1"


def _f(x: Any) -> float | None:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def _age_min(created: str | None) -> int | None:
    if not created:
        return None
    try:
        ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
        return int((datetime.now(timezone.utc) - ts).total_seconds() // 60)
    except (TypeError, ValueError):
        return None


def _pool(row: dict[str, Any]) -> dict[str, Any]:
    a = row.get("attributes") or {}
    ch = a.get("price_change_percentage") or {}
    tx = a.get("transactions") or {}
    h1 = tx.get("h1") or {}
    vol = a.get("volume_usd") or {}
    return {
        "name": a.get("name"),
        "address": a.get("address"),
        "priceUsd": _f(a.get("base_token_price_usd")),
        "m5": _f(ch.get("m5")),
        "h1": _f(ch.get("h1")),
        "h6": _f(ch.get("h6")),
        "h24": _f(ch.get("h24")),
        "vol24h": _f(vol.get("h24")),
        "vol1h": _f(vol.get("h1")),
        "liq": _f(a.get("reserve_in_usd")),
        "buys1h": (h1.get("buys") or 0),
        "sells1h": (h1.get("sells") or 0),
        "buyers1h": (h1.get("buyers") or 0),
        "created": a.get("pool_created_at"),
        "ageMin": _age_min(a.get("pool_created_at")),
        "url": f"https://www.geckoterminal.com/bsc/pools/{a.get('address')}",
        "dexscreener": f"https://dexscreener.com/bsc/{a.get('address')}",
    }


def _trade(row: dict[str, Any]) -> dict[str, Any]:
    a = row.get("attributes") or {}
    return {
        "kind": a.get("kind"),
        "usd": _f(a.get("volume_in_usd")),
        "wallet": a.get("tx_from_address"),
        "tx": a.get("tx_hash"),
        "ts": a.get("block_timestamp"),
        "bscscan": f"https://bscscan.com/tx/{a.get('tx_hash')}" if a.get("tx_hash") else None,
        "walletUrl": f"https://bscscan.com/address/{a.get('tx_from_address')}" if a.get("tx_from_address") else None,
    }


def _load() -> dict[str, Any]:
    with ThreadPoolExecutor(max_workers=4) as pool:
        f_tr = pool.submit(try_json, f"{GT}/trending_pools?page=1", 14)
        f_nw = pool.submit(try_json, f"{GT}/new_pools?page=1", 14)
        f_bo = pool.submit(try_json, DEX_BOOSTS, 10)
        trend_raw, e1 = f_tr.result()
        new_raw, e2 = f_nw.result()
        boost_raw, e3 = f_bo.result()

    trending = [_pool(x) for x in ((trend_raw or {}).get("data") or []) if isinstance(x, dict)]
    newborn = [_pool(x) for x in ((new_raw or {}).get("data") or []) if isinstance(x, dict)]
    boosts = []
    if isinstance(boost_raw, list):
        for b in boost_raw:
            if str(b.get("chainId") or "").lower() != "bsc":
                continue
            boosts.append(
                {
                    "name": (b.get("description") or b.get("tokenAddress") or "")[:80],
                    "address": b.get("tokenAddress"),
                    "url": b.get("url"),
                    "amount": b.get("totalAmount") or b.get("amount"),
                }
            )

    climbers = [
        p for p in trending + newborn
        if (p.get("liq") or 0) >= 3000 and ((p.get("h1") or 0) >= 20 or (p.get("h6") or 0) >= 40)
    ]
    climbers.sort(key=lambda p: (p.get("h1") or 0), reverse=True)
    # de-dupe by address
    seen: set[str] = set()
    uniq = []
    for p in climbers:
        addr = (p.get("address") or "").lower()
        if not addr or addr in seen:
            continue
        seen.add(addr)
        uniq.append(p)
    climbers = uniq[:12]

    fresh = [p for p in newborn if (p.get("ageMin") is not None and p["ageMin"] <= 180)]
    fresh.sort(key=lambda p: p.get("ageMin") or 10_000)

    errors = [e for e in (e1, e2, e3) if e]
    top = trending[0] if trending else None
    trades: list[dict[str, Any]] = []
    if top and top.get("address"):
        time.sleep(0.35)
        raw, terr = try_json(
            f"{GT}/pools/{top['address']}/trades?trade_volume_in_usd_greater_than=25",
            14,
        )
        trades = [_trade(x) for x in ((raw or {}).get("data") or [])[:20] if isinstance(x, dict)]
        if terr:
            errors.append(terr)

    return {
        "ok": bool(trending or newborn),
        "source": "geckoterminal+dexscreener",
        "errors": errors,
        "trending": trending[:12],
        "new": fresh[:12] or newborn[:12],
        "climbers": climbers,
        "boosts": boosts[:8],
        "flow": {
            "pool": (top or {}).get("name"),
            "address": (top or {}).get("address"),
            "buys1h": (top or {}).get("buys1h"),
            "sells1h": (top or {}).get("sells1h"),
            "buyers1h": (top or {}).get("buyers1h"),
            "vol1h": (top or {}).get("vol1h"),
            "trades": trades,
        },
    }


def get_scanner() -> dict[str, Any]:
    return get_or_set("scanner:bsc", TTL, _load)
