"""smart-money-brief — single source of truth for Helmsman + Grok skill.

LIVE DATA ONLY. Never invent fills, P&L, or APRs.
Consumes a floor pack (prices/yields/scanner/security/scan/protocols)
and returns a structured brief with one primary hire recommendation.
"""
from __future__ import annotations

from typing import Any


def _f(x: Any, default: float | None = None) -> float | None:
    try:
        if x is None or x == "":
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def _safe_pools(pools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in pools or []:
        apy = _f(p.get("apy"), 0.0) or 0.0
        tvl = _f(p.get("tvlUsd"), 0.0) or 0.0
        if tvl < 1_000_000 or apy <= 0 or apy > 400:
            continue
        if str(p.get("ilRisk") or "").lower() == "yes" and apy < 8:
            continue
        out.append(p)
    out.sort(key=lambda x: _f(x.get("apy"), 0.0) or 0.0, reverse=True)
    return out


def _goplus_posture(sec_row: dict[str, Any] | None) -> str:
    if not sec_row or not sec_row.get("ok"):
        return "—"
    if sec_row.get("honeypot"):
        return "HONEYPOT"
    buy = _f(sec_row.get("buyTax"), 0.0) or 0.0
    sell = _f(sec_row.get("sellTax"), 0.0) or 0.0
    if sec_row.get("safe") and buy < 10 and sell < 10:
        return "CLEAR"
    if buy > 0 or sell > 0:
        return "TAX"
    return "REVIEW"


def _sym_from_name(name: str | None) -> str | None:
    if not name:
        return None
    # GeckoTerminal names like "PEPE / WBNB"
    part = str(name).split("/")[0].strip().split()[0].upper()
    return part or None


def build_brief(floor_pack: dict[str, Any] | None) -> dict[str, Any]:
    """Build a live orchestration brief from a floor pack.

    Expected keys (all optional; missing → honest empty / —):
      prices, yields, scanner, security, scan, protocols,
      venus (wallet Venus account, optional)
    """
    pack = floor_pack or {}
    prices = pack.get("prices") or {}
    yields = pack.get("yields") or {}
    scanner = pack.get("scanner") or {}
    security = pack.get("security") or {}
    scan = pack.get("scan") or {}
    proto = pack.get("protocols") or {}
    venus_acct = pack.get("venus") or pack.get("venusAccount") or {}

    inputs_used: list[str] = []
    actions: list[str] = []
    calls: dict[str, Any] = {}

    # ---- 1. Yield call → Reef ----
    ranked = _safe_pools(yields.get("pools"))
    pick = ranked[0] if ranked else None
    second = ranked[1] if len(ranked) > 1 else None
    edge = None
    if pick and second:
        edge = (_f(pick.get("apy"), 0.0) or 0.0) - (_f(second.get("apy"), 0.0) or 0.0)
    yield_call = {
        "agent": "reef",
        "ok": bool(pick),
        "pool": pick,
        "edgeVs2": edge,
        "universe": len(ranked),
        "recommend": False,
        "reason": "no qualifying BSC pool (TVL≥$1M, 0<APR≤400)",
    }
    if pick:
        inputs_used.append("yields.pools")
        apy = _f(pick.get("apy"), 0.0) or 0.0
        tvl = _f(pick.get("tvlUsd"), 0.0) or 0.0
        yield_call["reason"] = (
            f"{pick.get('project')} {pick.get('symbol')} APR {apy:.2f}% · "
            f"TVL ${tvl/1e6:.1f}M"
            + (f" · edge +{edge:.2f}pp vs #2" if edge is not None else "")
        )
        # Clear edge: top APR ≥ 5% and (edge ≥ 0.5pp or sole pool)
        yield_call["recommend"] = apy >= 5.0 and (edge is None or edge >= 0.5 or len(ranked) == 1)
        actions.append(
            f"Yield: {pick.get('project')} {pick.get('symbol')} at {apy:.2f}% APR "
            f"(TVL ${tvl/1e6:.1f}M)" + (" — Reef edge clear" if yield_call["recommend"] else "")
        )
    calls["yield"] = yield_call

    # ---- 2. Grid call → Marlin (CAKE preferred, else WBNB) ----
    tokens = {t.get("symbol"): t for t in (prices.get("tokens") or [])}
    cake = tokens.get("CAKE") or {}
    wbnb = prices.get("wbnb") or tokens.get("WBNB") or {}
    grid_src = cake if cake.get("priceUsd") else wbnb
    grid_sym = "CAKE" if cake.get("priceUsd") else ("WBNB" if wbnb.get("priceUsd") else None)
    ch24 = abs(_f((grid_src or {}).get("priceChange24h"), 0.0) or 0.0)
    liq = _f((grid_src or {}).get("liquidityUsd"), 0.0) or 0.0
    px = _f((grid_src or {}).get("priceUsd"), 0.0) or 0.0
    # Useful vol band: realized |24h| between ~2.5% and 15%, with meaningful liq
    band_ok = bool(grid_sym and px and 2.5 <= ch24 <= 15.0 and liq >= 50_000)
    grid_call = {
        "agent": "marlin",
        "ok": bool(grid_sym and px),
        "symbol": grid_sym,
        "priceUsd": px or None,
        "change24h": (grid_src or {}).get("priceChange24h"),
        "liquidityUsd": liq or None,
        "recommend": band_ok,
        "reason": "price pack miss" if not (grid_sym and px) else (
            f"{grid_sym} ${px:.4f} · 24h {(_f((grid_src or {}).get('priceChange24h'), 0) or 0):+.2f}% · "
            f"liq ${liq/1e6:.2f}M" if liq else f"{grid_sym} ${px:.4f} · 24h move {ch24:.2f}%"
        ),
    }
    if grid_call["ok"]:
        inputs_used.append("prices")
        actions.append(
            f"Grid: {grid_sym} |24h| {ch24:.2f}%"
            + (" — Marlin band useful" if band_ok else " — outside useful vol band or thin liq")
        )
    calls["grid"] = grid_call

    # ---- 3. Health call → Pulse ----
    tvl_v = _f(proto.get("venusBscTvl"))
    borrowed = _f(proto.get("venusBscBorrowed"))
    util = None
    if tvl_v is not None and borrowed is not None and (tvl_v + borrowed) > 0:
        util = borrowed / (tvl_v + borrowed) * 100
        inputs_used.append("protocols.venus")
    hf = _f(venus_acct.get("healthFactor") or venus_acct.get("hf"))
    hf_status = None
    if hf is not None:
        inputs_used.append("venus.wallet")
        if hf < 1.2:
            hf_status = "critical"
        elif hf < 1.5:
            hf_status = "warn"
        else:
            hf_status = "ok"
    health_recommend = bool(
        (hf_status in ("critical", "warn"))
        or (util is not None and util >= 55)
        or (tvl_v is not None and hf is None)  # watch-only still surfaces Pulse when util high or as soft rec below
    )
    # Soft: recommend Pulse primarily when HF warn/critical or util elevated
    health_primary_worthy = bool(
        (hf_status in ("critical", "warn")) or (util is not None and util >= 60)
    )
    health_call = {
        "agent": "pulse",
        "ok": tvl_v is not None or hf is not None,
        "venusTvl": tvl_v,
        "borrowed": borrowed,
        "utilisation": util,
        "healthFactor": hf,
        "hfStatus": hf_status or ("watch-only" if tvl_v is not None else None),
        "recommend": health_primary_worthy,
        "reason": (
            f"wallet HF {hf:.2f} ({hf_status})"
            if hf is not None
            else (
                f"Venus BSC TVL ${tvl_v/1e9:.2f}B · util {util:.1f}%"
                if tvl_v is not None and util is not None
                else (
                    f"Venus BSC TVL ${tvl_v/1e9:.2f}B · watch-only (no wallet HF)"
                    if tvl_v is not None
                    else "Venus protocol unavailable"
                )
            )
        ),
    }
    if health_call["ok"]:
        actions.append(
            "Health: " + health_call["reason"]
            + (" — Pulse" if health_primary_worthy else " — Pulse watch")
        )
    calls["health"] = health_call

    # ---- 4. Trade/risk call → Swordfish (skip honeypot/tax) ----
    climbers = list(scanner.get("climbers") or [])
    top_climb = climbers[0] if climbers else None
    if top_climb:
        inputs_used.append("scanner.climbers")
    sec_map = {t.get("symbol"): t for t in (security.get("tokens") or []) if t.get("symbol")}
    climb_sym = _sym_from_name((top_climb or {}).get("name")) if top_climb else None
    # Prefer GoPlus on related major if climber symbol unknown; try climb_sym then WBNB
    sec_row = None
    if climb_sym and climb_sym in sec_map:
        sec_row = sec_map[climb_sym]
    elif "WBNB" in sec_map:
        sec_row = sec_map["WBNB"]
    posture = _goplus_posture(sec_row)
    if sec_row and sec_row.get("ok"):
        inputs_used.append("security.goplus")
    skip = posture in ("HONEYPOT", "TAX")
    climb_h1 = _f((top_climb or {}).get("h1"))
    trade_ok = bool(top_climb) and not skip
    trade_call = {
        "agent": "swordfish",
        "ok": bool(top_climb) or bool(sec_row and sec_row.get("ok")),
        "climber": top_climb,
        "climberSym": climb_sym,
        "climber1h": climb_h1,
        "goplus": posture,
        "skip": skip,
        "recommend": trade_ok and (climb_h1 is None or climb_h1 >= 20),
        "reason": (
            f"SKIP · GoPlus {posture}"
            + (f" on {climb_sym or 'related'}" if climb_sym or sec_row else "")
            if skip
            else (
                f"climber {(top_climb or {}).get('name') or '—'} · 1h "
                f"{climb_h1:+.1f}%" if climb_h1 is not None else
                (f"climber {(top_climb or {}).get('name')}" if top_climb else "no climber · majors watch")
            )
            + (f" · GoPlus {posture}" if posture != "—" else "")
        ),
    }
    if top_climb:
        if skip:
            actions.append(f"Trade: SKIP {(top_climb or {}).get('name')} — GoPlus {posture}")
        else:
            actions.append(
                f"Trade: watch {(top_climb or {}).get('name')}"
                + (f" 1h {climb_h1:+.1f}%" if climb_h1 is not None else "")
                + f" · GoPlus {posture} — Swordfish"
            )
    elif posture != "—":
        actions.append(f"Trade: majors GoPlus {posture} — Swordfish watch")
    calls["trade"] = trade_call

    # ---- 5. Discover call — market context (not a hire of random 8004 agents) ----
    bsc = scan.get("bsc") or {}
    totals = scan.get("totals") or {}
    bsc_agents = bsc.get("agents") if bsc.get("agents") is not None else totals.get("agents")
    avg_score = bsc.get("avgScore") if bsc.get("avgScore") is not None else totals.get("avgScore")
    if bsc_agents is not None or scan.get("ok"):
        inputs_used.append("scan.8004")
    discover_line = None
    if bsc_agents is not None:
        discover_line = (
            f"8004scan BSC {int(bsc_agents):,} agents"
            + (f" · avg score {float(avg_score):.1f}" if avg_score is not None else "")
        )
    elif totals.get("agents") is not None:
        discover_line = f"8004scan {int(totals['agents']):,} agents network-wide"
    discover_call = {
        "ok": discover_line is not None,
        "bscAgents": int(bsc_agents) if bsc_agents is not None else None,
        "avgScore": _f(avg_score),
        "line": discover_line or "8004scan unavailable",
        "recommendHire": False,  # never hire random 8004 agents without a real URL workflow
    }
    if discover_line:
        actions.append(f"Discover: {discover_line} (context only)")
    calls["discover"] = discover_call

    # ---- Anchor soft signal (rebalance) when pancake top has IL / strong APR ----
    pancake = (yields.get("pancake") or [None])[0] or yields.get("top")
    anchor_rec = False
    anchor_reason = "no Pancake pool"
    if pancake:
        inputs_used.append("yields.pancake")
        pap = _f(pancake.get("apy"), 0.0) or 0.0
        il = str(pancake.get("ilRisk") or "").lower()
        anchor_reason = (
            f"Pancake {pancake.get('symbol')} APR {pap:.2f}% · IL {pancake.get('ilRisk') or '—'}"
        )
        # Primary-worthy when IL flagged and APR still meaningful (range risk)
        anchor_rec = il == "yes" and pap >= 8
        if anchor_rec:
            actions.append(f"Rebalance: {anchor_reason} — Anchor")
    calls["rebalance"] = {
        "agent": "anchor",
        "ok": bool(pancake),
        "pool": pancake,
        "recommend": anchor_rec,
        "reason": anchor_reason,
    }

    # ---- Pick ONE primary ----
    candidates: list[tuple[float, str, str, float | None]] = []
    # score, agent_id, reason, confidence-ish
    if yield_call["recommend"] and pick:
        conf = min(95.0, 55.0 + (edge or 0) * 8 + min(20.0, (_f(pick.get("apy"), 0) or 0) / 2))
        candidates.append((90.0 + (edge or 0), "reef", yield_call["reason"], conf))
    if grid_call["recommend"]:
        # Mid-band vol scores higher
        vol_score = 80.0 - abs(ch24 - 6.0) * 2
        candidates.append((vol_score, "marlin", grid_call["reason"], min(90.0, 50.0 + ch24 * 2)))
    if health_call["recommend"]:
        conf = 92.0 if hf_status == "critical" else (85.0 if hf_status == "warn" else 70.0)
        candidates.append((95.0 if hf_status == "critical" else 88.0, "pulse", health_call["reason"], conf))
    if trade_call["recommend"] and not skip:
        conf = min(88.0, 50.0 + (climb_h1 or 20) * 0.5)
        candidates.append((75.0 + min(20.0, (climb_h1 or 0) / 5), "swordfish", trade_call["reason"], conf))
    if anchor_rec:
        candidates.append((70.0, "anchor", anchor_reason, 65.0))

    # Fallbacks when nothing "recommend" flagged — still pick best available live call
    if not candidates:
        if yield_call["ok"] and pick:
            candidates.append((50.0, "reef", yield_call["reason"], 45.0))
        elif grid_call["ok"]:
            candidates.append((45.0, "marlin", grid_call["reason"], 40.0))
        elif health_call["ok"]:
            candidates.append((40.0, "pulse", health_call["reason"], 40.0))
        elif trade_call["ok"] and not skip:
            candidates.append((35.0, "swordfish", trade_call["reason"], 35.0))
        elif calls["rebalance"]["ok"]:
            candidates.append((30.0, "anchor", anchor_reason, 30.0))

    primary_agent = None
    primary_reason = "insufficient live inputs"
    confidence = None
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        _, primary_agent, primary_reason, confidence = candidates[0]

    # Cap actions 3–5 honest bullets
    if not actions:
        actions = ["No live floor inputs yet — waiting on yields / prices / scanner / 8004scan"]
    actions = actions[:5]
    while len(actions) < 3 and discover_line:
        # pad only with real context already collected
        break
    if len(actions) < 3:
        if yield_call["ok"] and all("Yield:" not in a for a in actions):
            actions.append("Yield: " + yield_call["reason"])
        if grid_call["ok"] and all("Grid:" not in a for a in actions):
            actions.append("Grid: " + grid_call["reason"])
        if health_call["ok"] and all("Health:" not in a for a in actions):
            actions.append("Health: " + health_call["reason"])
        actions = actions[:5]

    live = bool(inputs_used)
    return {
        "primary": {
            "agent": primary_agent,
            "reason": primary_reason,
            "confidence": round(confidence, 1) if confidence is not None else None,
            "label": f"Hire {primary_agent.capitalize()}" if primary_agent else "No hire yet",
        },
        "actions": actions,
        "calls": calls,
        "inputs_used": sorted(set(inputs_used)),
        "live": live,
        "metrics": {
            "yieldTopApr": _f(pick.get("apy")) if pick else None,
            "yieldTopProject": (pick or {}).get("project"),
            "climber1h": climb_h1,
            "goplus": posture,
            "bscAgents": discover_call.get("bscAgents"),
            "edge": edge,
        },
    }
