"""Altana skills catalog — public registry, no keys. Not a fake on-chain session."""
from __future__ import annotations

from typing import Any

from .cache import get_or_set
from .http import try_json

TTL = 120
# Public skills index used by Altana MCP search_skills
INDEX_URLS = (
    "https://raw.githubusercontent.com/altananetwork/skills/main/index.json",
    "https://raw.githubusercontent.com/altananetwork/skills/master/skills.json",
)

HARD = [
    {"id": "pancakeswap-trading", "name": "PancakeSwap Trading", "category": "Trading", "url": "https://skills.altana.network/skill/pancakeswap-trading"},
    {"id": "pancakeswap-liquidity", "name": "PancakeSwap Liquidity", "category": "Liquidity", "url": "https://skills.altana.network/skill/pancakeswap-liquidity"},
    {"id": "venus-lending", "name": "Venus Lending", "category": "Lending", "url": "https://skills.altana.network/skill/venus-lending"},
    {"id": "lista-staking", "name": "Lista Liquid Staking", "category": "Staking", "url": "https://skills.altana.network/skill/lista-staking"},
    {"id": "aave-v3-lending", "name": "Aave V3 Lending", "category": "Lending", "url": "https://skills.altana.network/skill/aave-v3-lending"},
    {"id": "four-meme", "name": "Four.meme Trading", "category": "Trading", "url": "https://skills.altana.network/skill/four-meme"},
    {"id": "copy-trade", "name": "Copy Trade", "category": "Trading", "url": "https://skills.altana.network/skill/copy-trade"},
    {"id": "x402-payments", "name": "x402 API Payments", "category": "Payments", "url": "https://skills.altana.network/skill/x402-payments"},
    {"id": "dexscreener-token-radar", "name": "Token Radar", "category": "Research", "url": "https://skills.altana.network/skill/dexscreener-token-radar"},
    {"id": "wallet-tracker", "name": "Wallet Tracker", "category": "Research", "url": "https://skills.altana.network/skill/wallet-tracker"},
]


def _load() -> dict[str, Any]:
    parsed: list[dict[str, Any]] = []
    err = None
    for url in INDEX_URLS:
        data, e = try_json(url, timeout=12)
        if e:
            err = e
            continue
        rows = data if isinstance(data, list) else (data or {}).get("skills") or (data or {}).get("items") or []
        for row in rows:
            if not isinstance(row, dict):
                continue
            parsed.append(
                {
                    "id": row.get("id") or row.get("slug") or row.get("name"),
                    "name": row.get("name") or row.get("title"),
                    "category": row.get("category") or row.get("tag") or "Skill",
                    "url": row.get("url") or f"https://skills.altana.network/skill/{row.get('id')}",
                }
            )
        if parsed:
            break
    skills = parsed or HARD
    return {
        "ok": True,
        "source": "altana-skills" if parsed else "altana-skills-fallback-live-catalog",
        "error": None if parsed else err,
        "count": len(skills),
        "skills": skills,
        "docs": "https://docs.altana.network/",
        "explorerHint": "Altana prize needs a Keystore session tx — grant_session. Not faked here.",
    }


def get_altana() -> dict[str, Any]:
    return get_or_set("altana:skills", TTL, _load)
