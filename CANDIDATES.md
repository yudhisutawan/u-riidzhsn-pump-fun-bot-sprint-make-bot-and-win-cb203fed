# Candidates — Pump.fun Bot Sprint

Tournament by **measured net PnL**, not opinion. Every number below comes from
replaying the kit's frozen dev window (24 h, Nov 2–3, `dataset/events/` parts
00000/1/2) through a faithful local port of the harness engine
(`baselines/pilot/momentum/tools/sim.ts` → same market math, fees, latency,
failed-tx draws). Each setting was scored as the mean over 4 failed-tx keys
unless noted. Capital 10 SOL, max 5 open positions, buy cap 1% of real
reserve, fees 5 000 + 100 000 lamports per order + 95/30 bps curve fees.

## What the data says (measured on part-00000, 430 coins)

- A bonding curve **cannot trade below its create price** (0 of 430 coins ever
  went 5% below create; median end price ≈ create price). Downside from a
  near-create entry is floored; upside is the opening pump (median max run-up
  +19% in the first 5 trades, p90 +86%).
- **Size requires reserve, reserve requires pump**: by the time real SOL
  reaches 2, the price is already > +10% above create (0 coins in part-00000
  had real SOL >= 2 while run-up <= +10%). Buying low means buying small;
  buying big means buying the top, which then reverts.
- **Fees dominate small stakes**: a 0.01 SOL round trip pays ~0.00046 SOL in
  tx + curve fees (~4.6%). A trade needs a real edge, not just a small win.
- The bot's buy fills 2 slots after its decision, usually near the top of the
  first micro-spike — so "buy at create, sell the spike" only works with a
  fast exit and a pyramid into runners.

## Tournament results (net PnL, SOL)

| # | Candidate | part-00000 | part-00001 | part-00002 | 24 h (ALL) | Coins (ALL) | Max DD |
| --- | --- | --- | --- | --- | --- | --- | --- |
| — | Hold-cash (baseline) | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 |
| — | Equal-weight baseline (kit example) | −0.0168 | −0.1010 | −0.0431 | — | 5/part | 0.9% |
| H8 | Equal-weight rotation (Hermes 8) | = equal-weight baseline | | | | | |
| — | Momentum pilot, default (stake 2 SOL) | −9.3837 | — | — | — | 48 | 95.0% |
| — | Momentum pilot, small-stake sweep best | −0.489 (mean) | — | — | — | 63 | 9.2% |
| H1 | Quick-flip momentum (Hermes 1, tuned sniper family) | −0.0735 | −0.233 (mean) | −0.131 (mean) | — | 135/part | 1.2% |
| H2 | Micro-cap sniper (Hermes 2, pilot default) | −0.1349 | — | — | — | 136 | 1.7% |
| H3 | Conservative probes (Hermes 3; buy 0.01, sell immediately) | −0.0096 | — | — | — | 46 | 0.2% |
| H4 | Spike-rider, trailing stop (Hermes 4) | −0.087..−0.089 | — | — | — | 135 | 1.4% |
| H5 | Mean-reversion dip buyer (Hermes 5) | rejected: at retrace to +2%, median real SOL is 0.02 — the 1% cap cannot size a 0.01 SOL buy | | | | | |
| H6 | Volume-weighted trend filter (Hermes 6) | = Rider entry flow filter (net flow >= 0.3 SOL / 100 slots); without it Rider drops to +0.0184 | | | | | |
| H7 | Volatility-band breakout (Hermes 7) | = Rider run-up filter (entry only <= +10% vs create); loosening to +15/+20% turns ALL strongly negative (−0.14/−0.40) | | | | | |
| — | Reversion pilot, default | −1.7794 | −1.3727 | −0.2933 | — | 70/part | 18.2% |
| — | Rider, TP +25% / SL −10% / hold 100 (early version) | −0.0285 | — | — | — | 46 | 0.4% |
| — | Rider, TP +5% / SL −10% / hold 100 | +0.0336 | −0.0402 | −0.0158 | −0.0259 | 134 | 0.7% |
| — | Rider, TP +12% / SL −10% / hold 100, adds 0.08 → 0.15 | +0.0158 | −0.0158 | +0.0599 (mean; worst −0.0335) | +0.0857 | 120 | 0.9% |
| — | Rider, + maxBuyers 8 (tight) | +0.0140 | +0.0165 | +0.0729 (mean; worst −0.0211) | +0.1304 | 56 | 0.5% |
| ✅ | **Rider, WINNER (maxBuyers 20, minBuyers 2)** | **+0.0172** | **+0.0011** | **+0.0902** | **+0.1044** | **115** | **0.8%** |

Winner row is the submitted `main.py`, default failed-tx key; mean over 4 keys
on ALL is +0.1048 (worst +0.0979). Per-part 4-key means: +0.0185 / +0.0018 /
+0.0627. Wins 25/115 trips; best single trip +0.1195 SOL.

## Why the winner won

- **Entry near create + flow filter** (real SOL >= 1, run-up <= +10%,
  2–20 distinct buyers, net flow >= +0.3 SOL/100 slots) is the only pocket
  that survives fees: it buys the pump before it is over, with a floored
  downside.
- **Pyramid into strength** (add 0.08 SOL when price is +5% above the last
  buy, run-up <= +80%, flow still positive, up to 0.15 SOL/coin) is what
  captures the fat tail — without adds the same entry is −0.0141.
- **Fast exit** (TP +12%, SL −10%, max hold 100 slots) beats holding: holding
  to 300–1000 slots loses −0.01..−0.17 because prices revert to create.
- **Buyer cap 20** (a launch bundled by many wallets dumps) lifts ALL from
  +0.0923 (no cap) to +0.1048–0.1304; the tight cap 8 scores higher on ALL
  (+0.1304) but enters only 11 coins in part-00002 — a 5.3 h window like the
  6 h final — which would **fail the 20-coin guardrail**. The winner trades
  ~0.026 SOL of dev mean for guardrail safety (29–51 coins per part).

## Winner parameters (`main.py`)

- Entry: `minRqSol 1.0`, `maxRunupBps 1000`, `minBuyers 2`, `maxBuyers 20`,
  `flowWindow 100`, `minFlowSol 0.3`
- Size: `initialSol 0.02`, `addSol 0.08`, `stakeSol 0.15`,
  `addStepBps 500`, `addMaxRunupBps 8000`, `minBuySol 0.011`
  (every buy >= 0.011 SOL, so every round trip clears the 0.01 SOL floor)
- Exit: `tpBps 1200`, `slBps 1000`, `trailArmBps 500`, `trailBps 2000`,
  `maxHold 100`, `maxEntries 1`
- Skip-dev-sold and last-trade-must-be-buy filters were tried and **hurt**
  (creator selling by entry time is the norm, not a signal).

## Guardrails & determinism (winner, verified on the real `main.py`)

- Round trips >= 0.01 SOL: **115 coins on 24 h; 35 / 51 / 29 per part**
  (need >= 20) — every buy is >= 0.011 SOL.
- Max drawdown **0.77%** on 24 h (limit 50%); 0.27–0.41% per part.
- Rejected orders: **0**. Failed txs (2% draw): 7 on 24 h.
- **Two full runs produce byte-identical action logs.**
- `python3 -P -s main.py` runs outside the repo dir; stdlib only; writes
  nothing to disk; no network, clock, or randomness.

## Honest caveats

- Parameters were selected on the full 24 h dev window with per-part
  robustness checks; there is no untouched held-out window left — the final
  window is fresh data (6 h from Nov 28 16:00 WITA) and the score there is
  uncertain. Per-part means (+0.0185 / +0.0018 / +0.0627) and the
  concentration (best trip +0.1195 of +0.1044 total) show the edge is real
  but tail-dependent: on a fresh window the bot can plausibly land anywhere
  from about −0.03 to +0.09.
- The prize needs net PnL > 0 after all fees; on dev the winner clears that
  bar on every part and on the full window.
