# Smart Money Floor

Live **BNB Chain** agent marketplace for [The Smart Money Era](https://www.bnbchain.org/en/hackathons/smart-money-era) hackathon.

Find → understand → hire BSC specialists from **live** public APIs only. No mock prices, fake fills, or invented PnL.

## Agents

| Agent | Role |
|---|---|
| Helmsman | Floor captain — live hire recommendations |
| Swordfish | TermiX-style trading signals + gated swap |
| Marlin | Grid trading |
| Anchor | Rebalancing |
| Reef | Yield optimisation |
| Pulse | Health factor / Venus |

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
env -u PYTHONPATH python3 server.py
```

Open http://127.0.0.1:8090

### Optional env

| Variable | Purpose |
|---|---|
| `AGENT_WALLET` | Optional read-only demo address for balance/Venus views |
| `TWAK_ACCESS_ID` / `TWAK_HMAC_SECRET` | Required only for live SWAP (never commit these) |

Credentials are read from the environment or local `~/.twak/config.json` at runtime. They are **never** logged or shipped in this repo.

## Safety

- Live data only from public endpoints (DexScreener, DeFiLlama, GoPlus, 8004scan, …)
- Hired agents run **watch loops** unless you explicitly SWAP under cap (Swordfish/Marlin)
- Do not commit `.env`, wallets, or API keys

## License

Hackathon demo — use at your own risk.
