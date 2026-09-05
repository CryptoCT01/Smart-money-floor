"""24h OHLCV. Binance first (works on the Mac), Kraken then CoinGecko as fallbacks."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .cache import get_or_set

TIMEOUT = 12
TTL = 30
UA = {"User-Agent": "smart-money-floor/0.1"}

BINANCE_SYM = {
    "WBNB": "BNBUSDT",
    "BNB": "BNBUSDT",
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "CAKE": "CAKEUSDT",
}
KRAKEN_SYM = {
    "WBNB": "BNBUSD",
    "BNB": "BNBUSD",
    "BTC": "XBTUSD",
    "ETH": "ETHUSD",
}
GECKO_ID = {
    "WBNB": "binancecoin",
    "BNB": "binancecoin",
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "CAKE": "pancakeswap-token",
}


def _get(url: str) -> Any:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _pack(symbol: str, candles: list[dict], source: str) -> dict[str, Any]:
    if not candles:
        return {"ok": False, "symbol": symbol, "error": "empty", "candles": [], "points": []}
    last = candles[-1]["c"]
    first = candles[0]["c"]
    high = max(x["h"] for x in candles)
    low = min(x["l"] for x in candles)
    ch = ((last - first) / first * 100) if first else 0
    points = [{"t": x["t"] * 1000, "p": x["c"]} for x in candles]
    return {
        "ok": True,
        "symbol": symbol,
        "source": source,
        "candles": candles,
        "points": points,
        "last": last,
        "high": high,
        "low": low,
        "change24h": ch,
    }


def _binance(symbol: str) -> dict[str, Any] | None:
    pair = BINANCE_SYM.get(symbol)
    if not pair:
        return None
    url = f"https://api.binance.com/api/v3/klines?symbol={pair}&interval=5m&limit=96"
    try:
        raw = _get(url)
    except Exception:
        return None
    if not isinstance(raw, list) or not raw:
        return None
    candles = []
    for row in raw:
        candles.append({
            "t": int(row[0]) // 1000,
            "o": float(row[1]),
            "h": float(row[2]),
            "l": float(row[3]),
            "c": float(row[4]),
            "v": float(row[5]),
        })
    return _pack(symbol, candles, "binance")


def _kraken(symbol: str) -> dict[str, Any] | None:
    pair = KRAKEN_SYM.get(symbol)
    if not pair:
        return None
    url = f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval=5"
    try:
        raw = _get(url)
    except Exception:
        return None
    if raw.get("error"):
        return None
    result = raw.get("result") or {}
    series = next((v for k, v in result.items() if k != "last"), None)
    if not series:
        return None
    candles = []
    for row in series[-96:]:
        candles.append({
            "t": int(row[0]),
            "o": float(row[1]),
            "h": float(row[2]),
            "l": float(row[3]),
            "c": float(row[4]),
            "v": float(row[6]),
        })
    return _pack(symbol, candles, "kraken")


def _gecko(symbol: str) -> dict[str, Any] | None:
    cid = GECKO_ID.get(symbol)
    if not cid:
        return None
    url = (
        "https://api.coingecko.com/api/v3/coins/"
        + urllib.parse.quote(cid)
        + "/market_chart?vs_currency=usd&days=1"
    )
    try:
        raw = _get(url)
    except Exception:
        return None
    prices = raw.get("prices") or []
    if not prices:
        return None
    candles = []
    for t, p in prices:
        px = float(p)
        candles.append({"t": int(t) // 1000, "o": px, "h": px, "l": px, "c": px, "v": 0})
    return _pack(symbol, candles, "coingecko")


def _load(symbol: str) -> dict[str, Any]:
    for loader in (_binance, _kraken, _gecko):
        out = loader(symbol)
        if out and out.get("ok"):
            return out
    return {"ok": False, "symbol": symbol, "error": "all chart sources failed", "candles": [], "points": []}


def get_chart(symbol: str = "WBNB") -> dict[str, Any]:
    key = (symbol or "WBNB").upper()
    if key not in BINANCE_SYM and key not in GECKO_ID:
        key = "WBNB"
    return get_or_set(f"chart:{key}", TTL, lambda: _load(key))
