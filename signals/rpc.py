"""Public BSC JSON-RPC. No keys."""
from __future__ import annotations

import json
import urllib.request
from typing import Any

RPCS = (
    "https://bsc-dataseed.binance.org/",
    "https://bsc-dataseed1.bnbchain.org/",
)
UA = {"Content-Type": "application/json", "User-Agent": "smart-money-floor/1.0"}


def rpc(method: str, params: list[Any], timeout: float = 12) -> Any:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    last = None
    for url in RPCS:
        req = urllib.request.Request(url, data=body, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data.get("error"):
                last = data["error"]
                continue
            return data.get("result")
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
    raise RuntimeError(str(last))


def pad_addr(addr: str) -> str:
    a = addr.lower().replace("0x", "")
    return a.zfill(64)


def to_int(hex_str: str | None) -> int:
    if not hex_str or hex_str == "0x":
        return 0
    return int(hex_str, 16)
