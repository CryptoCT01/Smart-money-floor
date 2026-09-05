"""Gated TWAK swap. Credentials from env / ~/.twak/config.json — never logged."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

TWAK = Path.home() / ".hermes" / "node" / "bin" / "twak"
CFG = Path.home() / ".twak" / "config.json"
NATIVE = {"BNB", "WBNB", "USDT", "USDC", "CAKE", "ETH", "BTCB"}
# Public BSC contracts — not secrets. TWAK often wants 0x for non-native symbols.
BSC_ADDR = {
    "CAKE": "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82",
    "USDT": "0x55d398326f99059fF775485246999027B3197955",
    "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
    "ETH": "0x2170Ed0880ac9A755fd29B2688956BD959F933F8",
    "BTCB": "0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c",
}
GAS_RESERVE_BNB = 0.002
MAX_USD_HARD = 100.0
# Keep gas: do not spend the last 0.002 BNB. Tiny proof swaps are allowed above this.


def _creds() -> dict[str, str]:
    env = {
        "TWAK_ACCESS_ID": os.environ.get("TWAK_ACCESS_ID") or "",
        "TWAK_HMAC_SECRET": os.environ.get("TWAK_HMAC_SECRET") or "",
    }
    if env["TWAK_ACCESS_ID"] and env["TWAK_HMAC_SECRET"]:
        return env
    if CFG.exists():
        data = json.loads(CFG.read_text())
        return {
            "TWAK_ACCESS_ID": data.get("accessId") or data.get("access_id") or data.get("TWAK_ACCESS_ID") or "",
            "TWAK_HMAC_SECRET": data.get("hmacSecret") or data.get("hmac_secret") or data.get("TWAK_HMAC_SECRET") or "",
        }
    return env


def quote_usd(amount: float, px: float) -> float:
    return float(amount) * float(px or 0)


def execute_swap(*, src: str, dst: str, amount: float, cap_usd: float, px_src: float) -> dict[str, Any]:
    src = src.upper().replace("WBNB", "BNB") if src.upper() == "WBNB" else src.upper()
    dst = dst.upper()
    if src == dst:
        return {"ok": False, "executed": False, "error": "same asset"}
    if amount <= 0:
        return {"ok": False, "executed": False, "error": "amount"}
    usd = quote_usd(amount, px_src)
    cap = min(float(cap_usd or 0), MAX_USD_HARD)
    if cap <= 0:
        return {"ok": False, "executed": False, "error": "hire a trading agent with a spend cap first"}
    if usd > cap:
        return {"ok": False, "executed": False, "error": f"${usd:.2f} exceeds cap ${cap:.2f}"}
    if src == "BNB" and amount < GAS_RESERVE_BNB:
        return {"ok": False, "executed": False, "error": "keep 0.002 BNB for gas"}
    if not TWAK.exists():
        return {"ok": False, "executed": False, "error": "twak binary missing"}
    creds = _creds()
    if not creds.get("TWAK_ACCESS_ID") or not creds.get("TWAK_HMAC_SECRET"):
        return {"ok": False, "executed": False, "error": "TWAK credentials not available"}
    env = os.environ.copy()
    env["TWAK_ACCESS_ID"] = creds["TWAK_ACCESS_ID"]
    env["TWAK_HMAC_SECRET"] = creds["TWAK_HMAC_SECRET"]
    src_arg = "BNB" if src in ("BNB", "WBNB") else BSC_ADDR.get(src, src)
    dst_arg = "BNB" if dst in ("BNB", "WBNB") else BSC_ADDR.get(dst, dst)
    cmd = [
        str(TWAK), "swap", str(amount), src_arg, dst_arg,
        "--chain", "bsc", "--slippage", "5",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, env=env)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "executed": False, "error": str(exc)}
    out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    # never echo access ids
    ok = proc.returncode == 0 and ("0x" in out.lower() or "success" in out.lower())
    return {
        "ok": ok,
        "executed": ok,
        "error": None if ok else (out[-400:] or f"exit {proc.returncode}"),
        "summary": out[-240:] if ok else None,
        "from": src,
        "to": dst,
        "amount": amount,
        "usd": usd,
    }
