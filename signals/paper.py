"""Paper track record from live Binance candles. Not on-chain fills."""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from typing import Any

from .cache import get_or_set

UA = {"User-Agent": "smart-money-floor/0.1"}
BINANCE = {
    "CAKE": "CAKEUSDT",
    "WBNB": "BNBUSDT",
    "BNB": "BNBUSDT",
}


def _klines(symbol: str, interval: str = "1h", limit: int = 168) -> list[dict[str, Any]]:
    pair = BINANCE.get((symbol or "CAKE").upper())
    if not pair:
        return []
    url = f"https://api.binance.com/api/v3/klines?symbol={pair}&interval={interval}&limit={limit}"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    out = []
    for row in raw:
        out.append({
            "t": int(row[0]) // 1000,
            "o": float(row[1]),
            "h": float(row[2]),
            "l": float(row[3]),
            "c": float(row[4]),
            "v": float(row[5]),
        })
    return out


def _sma(xs: list[float], n: int) -> float | None:
    if len(xs) < n:
        return None
    return sum(xs[-n:]) / n


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def _run(candles: list[dict[str, Any]], *, cap_usd: float, kind: str) -> dict[str, Any]:
    cash = float(cap_usd)
    qty = 0.0
    equity_curve: list[float] = []
    trades: list[dict[str, Any]] = []
    peak = cap_usd
    max_dd = 0.0
    entry_px = None
    closes: list[float] = []
    for c in candles:
        px = c["c"]
        closes.append(px)
        sma = _sma(closes, 12)
        eq = cash + qty * px
        equity_curve.append(eq)
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak if peak else 0
        if dd > max_dd:
            max_dd = dd
        if sma is None:
            continue
        if kind == "grid":
            buy = qty == 0 and px < sma * 0.992
            sell = qty > 0 and px > sma * 1.008
        else:
            buy = qty == 0 and px > sma
            sell = qty > 0 and px < sma
        if buy and cash > 0:
            notional = cash * 0.35
            qty = notional / px
            cash -= notional
            entry_px = px
            trades.append({"side": "buy", "px": px, "t": c["t"], "usd": notional})
        elif sell and qty > 0 and entry_px:
            usd = qty * px
            pnl = usd - (qty * entry_px)
            cash += usd
            trades.append({"side": "sell", "px": px, "t": c["t"], "usd": usd, "pnlUsd": pnl})
            qty = 0.0
            entry_px = None
    if qty and candles:
        px = candles[-1]["c"]
        cash += qty * px
        qty = 0.0
    roundtrips = [t for t in trades if t.get("side") == "sell"]
    wins = [t for t in roundtrips if float(t.get("pnlUsd") or 0) > 0]
    losses = [t for t in roundtrips if float(t.get("pnlUsd") or 0) <= 0]
    pnl = cash - cap_usd
    wr = (len(wins) / len(roundtrips) * 100) if roundtrips else None
    window = None
    if candles:
        window = {"from": _iso(candles[0]["t"]), "to": _iso(candles[-1]["t"]), "hours": len(candles)}
    return {
        "ok": bool(candles),
        "kind": kind,
        "label": "PAPER — live Binance candles, not on-chain fills",
        "window": window,
        "capUsd": cap_usd,
        "trades": len(trades),
        "roundtrips": len(roundtrips),
        "wins": len(wins),
        "losses": len(losses),
        "winRatePct": round(wr, 2) if wr is not None else None,
        "pnlUsd": round(pnl, 4),
        "pnlPct": round(pnl / cap_usd * 100, 3) if cap_usd else None,
        "maxDrawdownPct": round(max_dd * 100, 3),
        "risk": {
            "perTradeFrac": 0.35,
            "capUsd": cap_usd,
            "maxDrawdownUsd": round(max_dd * cap_usd, 4),
        },
        "lastEquityUsd": round(cash, 4),
        "sampleTrades": trades[-8:],
        "candles": len(candles),
    }


def get_record(cap_usd: float = 100.0) -> dict[str, Any]:
    def load() -> dict[str, Any]:
        cake = _klines("CAKE")
        bnb = _klines("WBNB")
        marlin = _run(cake, cap_usd=cap_usd, kind="grid")
        swordfish = _run(bnb, cap_usd=cap_usd, kind="trend")
        return {
            "ok": marlin.get("ok") or swordfish.get("ok"),
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "note": "Paper record from live public candles. Zero on-chain fills. Win rate / window / risk are measured on this series.",
            "marlin": {**marlin, "symbol": "CAKE", "venue": "Pancake grid paper"},
            "swordfish": {**swordfish, "symbol": "WBNB", "venue": "BSC trend paper"},
        }

    return get_or_set("paper:7d", 90, load)
