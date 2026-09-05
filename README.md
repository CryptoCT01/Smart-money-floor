# Smart Money Floor

BNB Agent Studio marketplace for **The Smart Money Era**.

Four equally-deep categories, live BSC data:

| Agent | Category | Live data |
|---|---|---|
| Swordfish | Trading | DexScreener + GoPlus |
| Marlin | Grid Trading | CAKE band from realized 24h + Pancake TVL |
| Anchor | Rebalancing | PancakeSwap yields, IL, forecast |
| Pulse | Health Factor | Venus markets + protocol TVL/borrow |

Also on the floor: **8004scan** agent directory, DeFiLlama yield table, GoPlus security.

## Run

```bash
cd ~/Desktop/bnb-agent
python3 server.py
```

Open http://127.0.0.1:8090

No API keys. Public: DexScreener, DeFiLlama, 8004scan, GoPlus, PancakeSwap farms-api.

## Layout

```
agents/        swordfish · marlin · anchor · pulse
signals/       prices, yields, charts, 8004scan, goplus, protocols
marketplace/   dashboard.html
server.py      stdlib HTTP on :8090
```

Do not modify `trading-floor/` or `humming-bot/`. Those are read-only references.
