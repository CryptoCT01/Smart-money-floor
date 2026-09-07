"""Altana Keystore session bridge — spawns scripts/altana/*.mjs, never exposes keys."""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / ".altana-state.json"
ENV_FILE = ROOT / ".env.altana"
SCRIPTS = ROOT / "scripts" / "altana"
FUND_HINT = "Send BNB to address"
EXPLORER_ADDR = "https://bscscan.com/address/"

_NODE_CANDIDATES = (
    os.path.expanduser("~/.local/bin/node"),
    "/opt/homebrew/bin/node",
    "/usr/local/bin/node",
    "node",
)


def _find_node() -> str:
    for c in _NODE_CANDIDATES:
        if c == "node":
            return c
        if Path(c).exists():
            return c
    return "node"


def _read_state() -> dict[str, Any]:
    if not STATE.exists():
        return {}
    try:
        return json.loads(STATE.read_text() or "{}")
    except json.JSONDecodeError:
        return {}


def public_status() -> dict[str, Any]:
    st = _read_state()
    addr = st.get("walletAddress")
    session = st.get("session") or None
    sess_out = None
    if session:
        expiry_iso = session.get("expiryIso")
        if not expiry_iso and session.get("expiry"):
            expiry_iso = datetime.fromtimestamp(
                int(session["expiry"]), tz=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
        sess_out = {
            "active": bool(session.get("active")) and not session.get("revoked"),
            "publicKey": session.get("publicKey"),
            "expiry": session.get("expiry"),
            "expiryIso": expiry_iso,
            "spendCapWei": session.get("spendCapWei"),
            "spendCapEther": session.get("spendCapEther"),
            "spendPeriod": session.get("spendPeriod"),
            "callsAllowlist": session.get("callsAllowlist") or [],
            "grantTxHash": session.get("grantTxHash"),
            "grantExplorer": session.get("grantExplorer"),
            "revoked": bool(session.get("revoked")),
            "revokeTxHash": session.get("revokeTxHash"),
            "revokeExplorer": session.get("revokeExplorer"),
        }
    return {
        "ok": True,
        "chain": st.get("chain") or "BNB",
        "chainId": st.get("chainId") or 56,
        "walletAddress": addr,
        "walletExplorer": (EXPLORER_ADDR + addr) if addr else None,
        "funded": bool(st.get("funded")),
        "balanceEther": st.get("balanceEther"),
        "fundHint": FUND_HINT,
        "session": sess_out,
        "lastTx": st.get("lastTx"),
        "waitForFund": bool(addr) and not st.get("funded"),
        "waitForFaucet": bool(addr) and not st.get("funded"),  # legacy alias
        "envPresent": ENV_FILE.exists(),
        "scriptsDir": str(SCRIPTS),
        "docs": "https://docs.altana.network/sdk/bnb",
    }


def _run_script(name: str, timeout: int = 180) -> dict[str, Any]:
    script = SCRIPTS / name
    if not script.exists():
        return {"ok": False, "error": f"missing script {name}"}
    node = _find_node()
    env = os.environ.copy()
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in env:
                env[k] = v
    try:
        proc = subprocess.run(
            [node, str(script)],
            cwd=str(SCRIPTS),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except FileNotFoundError:
        return {"ok": False, "error": "node runtime not found — install Node.js"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"{name} timed out"}
    raw = (proc.stdout or "").strip().splitlines()
    parsed: dict[str, Any] | None = None
    for line in reversed(raw):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                parsed = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    if parsed is None and raw:
        try:
            parsed = json.loads("\n".join(raw))
        except json.JSONDecodeError:
            parsed = None
    if parsed is None:
        err = (proc.stderr or proc.stdout or "no output")[:400]
        return {"ok": False, "error": err, "exitCode": proc.returncode}
    for bad in ("adminKey", "privateKey", "sessionKey", "ALTANA_ADMIN_KEY"):
        parsed.pop(bad, None)
    if "ok" not in parsed:
        parsed["ok"] = proc.returncode == 0
    parsed["exitCode"] = proc.returncode
    return parsed


def ensure_wallet() -> dict[str, Any]:
    st = _read_state()
    if st.get("walletAddress"):
        if (SCRIPTS / "status.mjs").exists():
            return _run_script("status.mjs", timeout=90)
        return public_status()
    return _run_script("create-wallet.mjs", timeout=120)


def grant() -> dict[str, Any]:
    return _run_script("grant-session.mjs", timeout=180)


def revoke() -> dict[str, Any]:
    return _run_script("revoke-session.mjs", timeout=180)


def execute_demo() -> dict[str, Any]:
    return _run_script("execute-session.mjs", timeout=180)
