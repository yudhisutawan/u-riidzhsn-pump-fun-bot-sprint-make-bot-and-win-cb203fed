[![make.fun · u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed](https://make.fun/badge/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed.svg)](https://make.fun/bounty/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed?utm_source=github&utm_medium=readme&utm_campaign=u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed)
[![rank](https://make.fun/badge/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed/yudhisutawan/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed/rank.svg)](https://make.fun/bounty/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed)
[![reward](https://make.fun/badge/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed/yudhisutawan/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed/reward.svg)](https://make.fun/bounty/u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed?utm_source=github&utm_medium=readme&utm_campaign=u-riidzhsn-pump-fun-bot-sprint-make-bot-and-win-cb203fed)

# Pump.fun Bot Sprint: Make Bot And Win

A deterministic Solana trading bot for the pump.fun bonding-curve replay
(`agent-fun/replay/v2`, template `pumpfun-replay`). It trades paper money on
recorded chain data, ranked on net PnL. Standard library only, no network, no
randomness, no clock — every run is byte-for-byte reproducible.

## Strategy: "Rider" (early entry + pyramid into strength)

A bonding curve cannot trade below its create price, so the downside from a
near-create entry is floored while the upside is the opening pump. The bot:

1. **Enters early** when a curve still holds real SOL and its price is still
   near create: real SOL >= 1, price vs create <= +10%, 2–20 distinct
   non-creator buyers, net buy flow >= 0.3 SOL over the last 100 slots.
2. **Buys small first** (0.02 SOL, capped at 1% of real reserve) and
   **pyramids only into strength** — price up >= 5% from the last buy, run-up
   still <= +80%, flow still positive — up to 0.15 SOL per coin.
3. **Sells whole** on the first of: +12% take-profit, −10% stop-loss, a 20%
   trailing give-back once +5% up, or 100 slots max hold.
4. Every buy is >= 0.011 SOL, so every round trip clears the 0.01 SOL
   guardrail floor; at most 5 positions open at once.

Full tournament (8 Hermes strategies + baselines + pilots) and per-part
backtests: see [CANDIDATES.md](CANDIDATES.md).

## Backtest (dev window, 24 h, Nov 2–3, 3 parts)

| Window | Net PnL | Coins | Trips | Wins | Max DD |
| --- | --- | --- | --- | --- | --- |
| part-00000 | +0.0172 SOL | 35 | 35 | 12 | 0.27% |
| part-00001 | +0.0011 SOL | 51 | 51 | 8 | 0.41% |
| part-00002 (held-out proxy for a 6 h final) | +0.0902 SOL | 29 | 29 | 6 | 0.40% |
| **All 24 h** | **+0.1044 SOL** | **115** | **115** | **25** | **0.77%** |

Guardrails: >= 20 coins with round trips >= 0.01 SOL on every part
(29–51), max drawdown 0.77% (limit 50%), 0 rejected orders. Two runs of the
bot produce byte-identical action logs. Baselines for comparison: hold-cash
0.0000 SOL, equal-weight −0.0168 SOL (only 5 coins), best tuned sniper
−0.0735 SOL, momentum pilot −9.3837 SOL.

## Run

The grader runs it as `python3 -P -s /bot/main.py` with `PYTHONHASHSEED=0`.
`vendor/makefun_bot.py` is an unmodified copy of the kit's Python SDK shim.

## License

MIT — see [LICENSE](LICENSE).
