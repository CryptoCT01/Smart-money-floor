"""DexScreener — free, no auth. BSC majors, fetched in parallel."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .cache import get_or_set

DEX_URL = "https://api.dexscreener.com/latest/dex/tokens/{token}"
TIMEOUT = 8
TTL = 20

# Public token contracts on BSC. Not secrets.
WATCH = [
    ("WBNB", "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"),
    ("BTCB", "0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c"),
    ("ETH",  "0x2170Ed0880ac9A755fd29B2688956BD959F933F8"),
    ("CAKE", "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82"),
    ("USDT", "0x55d398326f99059fF775485246999027B3197955"),
    ("USDC", "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d"),
    ("SOL",  "0x570A5D26f7765Ecb712C0924E4De545B89fD43dF"),
    ("XRP",  "0x1D2F0da169ceB9fC7B3144628dB156f3F6c60dBE"),
    ("ADA",  "0x3EE2200Efb3400fAbB9AacF31297cBdD1d435D47"),
    ("DOGE", "0xbA2aE424d960c26247Dd6c32edC70B295c744C43"),
    ("LINK", "0xF8A0BF9cF54Bb92F17374d9e9A321E6a111a51bD"),
]


def _get(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "smart-money-floor/0.1"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _best_bsc_pair(pairs: list[dict[str, Any]]) -> dict[str, Any] | None:
    bsc = [
        p
        for p in pairs
        if str(p.get("chainId") or "").lower() in ("bsc", "bnb")
    ]
    bsc.sort(key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0), reverse=True)
    return bsc[0] if bsc else None


def _summarize(symbol: str, pair: dict[str, Any]) -> dict[str, Any]:
    liq = (pair.get("liquidity") or {}).get("usd")
    vol = (pair.get("volume") or {}).get("h24")
    ch = (pair.get("priceChange") or {}).get("h24")
    return {
        "symbol": symbol,
        "priceUsd": float(pair.get("priceUsd") or 0),
        "priceChange24h": float(ch or 0),
        "liquidityUsd": float(liq or 0),
        "volume24h": float(vol or 0),
        "dex": pair.get("dexId"),
        "pair": f"{(pair.get('baseToken') or {}).get('symbol')}/{(pair.get('quoteToken') or {}).get('symbol')}",
        "url": pair.get("url"),
        "updatedAt": pair.get("pairUpdatedAt"),
    }


def _one(symbol: str, addr: str) -> tuple[str, dict[str, Any] | None, str | None]:
    try:
        data = _get(DEX_URL.format(token=addr))
        pair = _best_bsc_pair(data.get("pairs") or [])
        if pair:
            return symbol, _summarize(symbol, pair), None
        return symbol, None, f"{symbol}: no BSC pair"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        return symbol, None, f"{symbol}: {exc}"


def _load() -> dict[str, Any]:
    tokens: list[dict[str, Any]] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(_one, symbol, addr) for symbol, addr in WATCH]
        for fut in as_completed(futs):
            symbol, row, err = fut.result()
            if row:
                tokens.append(row)
            if err:
                errors.append(err)
    order = {s: i for i, (s, _) in enumerate(WATCH)}
    tokens.sort(key=lambda t: order.get(t["symbol"], 99))
    wbnb = next((t for t in tokens if t["symbol"] == "WBNB"), None)
    return {
        "ok": wbnb is not None,
        "source": "dexscreener",
        "tokens": tokens,
        "wbnb": wbnb,
        "errors": errors,
        "coins": [s for s, _ in WATCH],
    }


def get_prices() -> dict[str, Any]:
    return get_or_set("dexscreener:prices", TTL, _load)
