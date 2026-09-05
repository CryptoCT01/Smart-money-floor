"""Helmsman — Floor Captain. Orchestrates live brief → one primary hire call.

LIVE DATA ONLY via skills.smart_money_brief.build_brief.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from skills.smart_money_brief import build_brief  # noqa: E402


def snapshot(prices: dict, yields: dict, extra: dict | None = None) -> dict[str, Any]:
    extra = extra or {}
    floor_pack = {
        "prices": prices or {},
        "yields": yields or {},
        "scanner": extra.get("scanner") or {},
        "security": extra.get("security") or {},
        "scan": extra.get("scan") or {},
        "protocols": extra.get("protocols") or {},
        "venus": extra.get("venus") or extra.get("venusAccount") or {},
    }
    # Optional: merge other agent snapshots if provided (not required for brief)
    brief = build_brief(floor_pack)
    primary = brief.get("primary") or {}
    metrics_src = brief.get("metrics") or {}
    agent_id = primary.get("agent")
    hire_label = primary.get("label") or ("Hire " + agent_id.capitalize() if agent_id else "—")
    conf = primary.get("confidence")
    edge = metrics_src.get("edge")
    conf_or_edge = None
    conf_fmt = "text"
    if conf is not None:
        conf_or_edge = conf
        conf_fmt = "pct"
    elif edge is not None:
        conf_or_edge = edge
        conf_fmt = "pct"

    live = bool(brief.get("live"))
    detail_bits = []
    if agent_id:
        detail_bits.append(f"Primary → {agent_id}")
    if primary.get("reason"):
        detail_bits.append(str(primary["reason"])[:120])
    detail = " · ".join(detail_bits) if detail_bits else "Waiting on live floor inputs"

    return {
        "id": "helmsman",
        "name": "Helmsman",
        "category": "Floor Captain",
        "codename": "Orchestration · live brief → one hire",
        "status": f"steer → {agent_id}" if agent_id else "briefing",
        "live": live,
        "accent": "cyan",
        "hire": (
            "Hire Helmsman to keep a live floor brief ticking: yield, grid, health, "
            "trade/risk and 8004 context — then one primary recommend among the five stations."
        ),
        "why": (
            "Captain strip for the floor. Reads the same live packs as every station and "
            "picks one honest primary hire with numbers — no fake fills or invented APRs."
        ),
        "metrics": [
            {"label": "Primary", "value": hire_label if agent_id else "—", "fmt": "text"},
            {"label": "Confidence", "value": conf_or_edge, "fmt": conf_fmt},
            {"label": "Yield top APR", "value": metrics_src.get("yieldTopApr"), "fmt": "pct"},
            {"label": "Climber 1h", "value": metrics_src.get("climber1h"), "fmt": "pct"},
            {"label": "GoPlus", "value": metrics_src.get("goplus") or "—", "fmt": "text"},
            {"label": "8004 BSC", "value": metrics_src.get("bscAgents"), "fmt": "int"},
        ],
        "detail": detail,
        "source": "floor pack · smart-money-brief",
        "brief": {
            "primary": primary,
            "actions": brief.get("actions") or [],
            "inputs_used": brief.get("inputs_used") or [],
            "calls": {k: {"recommend": (v or {}).get("recommend"), "reason": (v or {}).get("reason") or (v or {}).get("line")}
                      for k, v in (brief.get("calls") or {}).items()},
        },
        "actions": brief.get("actions") or [],
    }
