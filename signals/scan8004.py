"""8004scan — ERC-8004 agent discovery. Anonymous, no key."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .cache import get_or_set
from .http import try_json

BASE = "https://api.8004scan.io/api/v1"
TTL = 45
BSC = 56


def _slim(item: dict[str, Any]) -> dict[str, Any]:
    desc = (item.get("description") or "").strip().replace("\n", " ")
    if len(desc) > 160:
        desc = desc[:157] + "…"
    chain = item.get("chain_id")
    return {
        "name": item.get("name") or "Untitled agent",
        "description": desc,
        "chainId": chain,
        "chain": "BSC" if chain == BSC else (item.get("chain_type") or str(chain)),
        "tokenId": item.get("token_id"),
        "owner": item.get("owner_username") or item.get("owner_ens") or item.get("owner_address"),
        "stars": item.get("star_count") or 0,
        "score": item.get("total_score"),
        "rank": item.get("rank"),
        "health": item.get("health_score"),
        "verified": bool(item.get("is_verified")),
        "x402": bool(item.get("x402_supported")),
        "url": f"https://8004scan.io/agents/{item.get('chain_id')}/{item.get('token_id')}",
    }


def _list(path: str) -> list[dict[str, Any]]:
    data, err = try_json(f"{BASE}{path}", timeout=14)
    if err or not isinstance(data, dict):
        return []
    items = data.get("items") or []
    return [_slim(x) for x in items if isinstance(x, dict)]


def _load() -> dict[str, Any]:
    with ThreadPoolExecutor(max_workers=5) as pool:
        f_stats = pool.submit(try_json, f"{BASE}/stats/global", 14)
        f_feat = pool.submit(_list, "/agents/featured?limit=12")
        f_trend = pool.submit(_list, "/agents/trending?limit=12")
        f_board = pool.submit(_list, "/agents/leaderboard?limit=12")
        f_late = pool.submit(_list, "/agents/latest?limit=12")
        stats, stats_err = f_stats.result()
        featured = f_feat.result()
        trending = f_trend.result()
        leaderboard = f_board.result()
        latest = f_late.result()

    bsc = None
    chains = []
    if isinstance(stats, dict):
        for row in stats.get("chain_stats") or []:
            chains.append(
                {
                    "chainId": row.get("chain_id"),
                    "name": row.get("name"),
                    "agents": row.get("total_agents") or 0,
                    "feedbacks": row.get("total_feedbacks") or 0,
                    "avgScore": row.get("average_feedback_score"),
                }
            )
            if row.get("chain_id") == BSC:
                bsc = chains[-1]

    seen: set[tuple] = set()
    directory: list[dict[str, Any]] = []
    for bucket, tag in (
        (featured, "featured"),
        (leaderboard, "leaderboard"),
        (trending, "trending"),
        (latest, "latest"),
    ):
        for row in bucket:
            key = (row.get("chainId"), row.get("tokenId"))
            if key in seen:
                continue
            seen.add(key)
            row = dict(row)
            row["badge"] = tag
            directory.append(row)

    bsc_agents = [r for r in directory if r.get("chainId") == BSC]
    return {
        "ok": stats_err is None,
        "source": "8004scan",
        "error": stats_err,
        "totals": {
            "agents": (stats or {}).get("total_agents") if isinstance(stats, dict) else None,
            "users": (stats or {}).get("total_users") if isinstance(stats, dict) else None,
            "feedbacks": (stats or {}).get("total_feedbacks") if isinstance(stats, dict) else None,
            "avgScore": (stats or {}).get("average_feedback_score") if isinstance(stats, dict) else None,
            "dailyAgents": (stats or {}).get("daily_new_agents") if isinstance(stats, dict) else None,
        },
        "bsc": bsc,
        "chains": sorted(chains, key=lambda c: c.get("agents") or 0, reverse=True)[:8],
        "featured": featured[:8],
        "trending": trending[:8],
        "leaderboard": leaderboard[:8],
        "latest": latest[:8],
        "directory": directory[:24],
        "bscAgents": bsc_agents[:12],
        "explore": "https://8004scan.io/agents?chain=56",
    }


def get_scan() -> dict[str, Any]:
    return get_or_set("8004scan:floor", TTL, _load)
