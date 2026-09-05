# smart-money-brief

Reusable Smart Money Floor orchestration skill. **Live data only** — never invent fills, P&L, or APRs.

## Source of truth

Python helper (shared by Helmsman agent + this skill):

```text
skills/smart_money_brief.py  →  build_brief(floor_pack) -> dict
```

Helmsman marketplace agent wraps the same function:

```text
agents/helmsman.py  →  snapshot(prices, yields, extra)  →  agent tile + brief
```

## Inputs (`floor_pack`)

| Key | Source | Used for |
|-----|--------|----------|
| `prices` | DexScreener via `/api/floor` | Grid call (CAKE/WBNB 24h + liq) |
| `yields` | DeFiLlama | Yield call (`pools` TVL≥$1M, 0<APR≤400); Anchor pancake soft signal |
| `scanner` | GeckoTerminal | Top climber 1h for trade/risk |
| `security` | GoPlus | CLEAR / TAX / HONEYPOT posture — SKIP trade if TAX/HONEYPOT |
| `scan` | 8004scan | BSC agent count + avg score (market context only) |
| `protocols` | DeFiLlama protocols | Venus BSC TVL / borrowed → utilisation |
| `venus` / `venusAccount` | optional wallet Venus | Health factor status when bound |

Missing keys → honest empty / `—`. No stubs.

## Outputs

```json
{
  "primary": {
    "agent": "reef|marlin|pulse|swordfish|anchor|null",
    "reason": "string citing live numbers",
    "confidence": 72.5,
    "label": "Hire Reef"
  },
  "actions": ["3–5 honest bullet strings"],
  "calls": {
    "yield": { "agent": "reef", "recommend": true, "reason": "..." },
    "grid": { "agent": "marlin", "recommend": false, "reason": "..." },
    "health": { "agent": "pulse", "recommend": false, "reason": "..." },
    "trade": { "agent": "swordfish", "skip": false, "goplus": "CLEAR", "reason": "..." },
    "discover": { "line": "8004scan BSC N agents · avg score X", "recommendHire": false },
    "rebalance": { "agent": "anchor", "recommend": false, "reason": "..." }
  },
  "inputs_used": ["yields.pools", "prices", "..."],
  "live": true,
  "metrics": {
    "yieldTopApr": 12.3,
    "climber1h": 28.4,
    "goplus": "CLEAR",
    "bscAgents": 1234,
    "edge": 1.2
  }
}
```

### Decision rules (summary)

1. **Yield → Reef** when top safe pool has APR ≥ 5% and clear edge vs #2 (≥ 0.5pp) or sole pool.
2. **Grid → Marlin** when CAKE (else WBNB) |24h| is in ~2.5–15% and liq ≥ $50k.
3. **Health → Pulse** when wallet HF warn/critical or Venus utilisation ≥ 60%; else watch-only line.
4. **Trade → Swordfish** on top scanner climber if GoPlus not HONEYPOT/TAX; else SKIP.
5. **Discover** is context only — never hires a random 8004 agent without a real URL workflow.
6. **One primary** = highest-scoring recommend among the five; fallback to best live call if none flagged.

## Usage (Python)

```python
from skills.smart_money_brief import build_brief

brief = build_brief({
    "prices": prices,
    "yields": yields,
    "scanner": scanner,
    "security": security,
    "scan": scan,
    "protocols": protocols,
})
print(brief["primary"]["label"], brief["primary"]["reason"])
for line in brief["actions"]:
    print("-", line)
```

## Usage (HTTP)

`GET /api/floor` → `agents[]` includes `id: "helmsman"` with `brief` and six live metrics.
Hire via `POST /api/hire` `{"agent":"helmsman","capUsd":100}`. Runtime ticks recompute the brief and log `PRIMARY → …` (no fake fills). Swap remains Swordfish/Marlin only.

## Outside the UI

Import `build_brief` from any Grok / automation context that already has a floor pack (or equivalent live API bundle). Do not fabricate metric fields when an upstream pack misses.
