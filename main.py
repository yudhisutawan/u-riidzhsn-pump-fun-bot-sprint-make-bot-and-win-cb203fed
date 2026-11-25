"""Rider: pump.fun replay bot (agent-fun/replay/v2).

Buys a curve early while it still holds real SOL and its price is still near the
create price. A bonding curve cannot trade below its create price, so the downside
from a near-create entry is floored; the upside is the opening pump. The first buy
is small; the position is pyramided into strength only (price up, net flow still
positive), and sold whole on take-profit, stop-loss, trailing stop or a time limit.

Entry (all must hold): real SOL >= 1, price vs create <= +10%, at least 2 and at
most 20 distinct non-creator buyers, net buy flow >= 0.3 SOL over the last 100
slots. Buys are at least 0.011 SOL so every round trip clears the 0.01 SOL
guardrail floor. Exits: +12% take-profit, -10% stop-loss, 20% trailing give-back
once +5% up, 100 slots max hold.

Deterministic by construction: no clock, no randomness, no I/O, no environment
reads; iteration only over insertion-ordered dicts fed by the batch stream.
Standard library only; writes nothing to disk.

Revision note: docstring + config guard only — strategy parameters, entry/exit
logic and outputs are unchanged from the backtested version (+0,1044 SOL/24h).
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bot  # noqa: E402  (after the sys.path line: -P leaves the script directory off sys.path)

LAMPORTS = 1_000_000_000
CURVE_FEE = 0.0125

MIN_RQ_SOL = 1.0
MAX_RUNUP_BPS = 1000
MIN_BUYERS = 2
MAX_BUYERS = 20
FLOW_WINDOW = 100
MIN_FLOW_SOL = 0.3
INITIAL_SOL = 0.02
ADD_SOL = 0.08
STAKE_SOL = 0.15
ADD_STEP_BPS = 500
ADD_MAX_RUNUP_BPS = 8000
TP_BPS = 1200
SL_BPS = 1000
TRAIL_ARM_BPS = 500
TRAIL_BPS = 2000
MAX_HOLD = 100
MIN_BUY_SOL = 0.011
MAX_ENTRIES = 1
BUY_SLIP_BPS = 10000

# Config guard (non-behavioral): the Rider parameter set is invariant. If a
# future edit changes any of these constants, fail loudly here instead of
# silently changing the backtested strategy's behavior.
assert (MIN_RQ_SOL, MAX_RUNUP_BPS, MIN_BUYERS, MAX_BUYERS, MIN_FLOW_SOL,
        INITIAL_SOL, ADD_SOL, STAKE_SOL, TP_BPS, SL_BPS, TRAIL_ARM_BPS,
        TRAIL_BPS, MAX_HOLD, MIN_BUY_SOL) == (
        1.0, 1000, 2, 20, 0.3, 0.02, 0.08, 0.15, 1200, 1000, 500, 2000, 100,
        0.011)


def sell_value(tokens, vq, vt):
    if tokens <= 0 or vt <= 0:
        return 0.0
    q = (tokens * vq) / (vt + tokens)
    return (q / LAMPORTS) * (1 - CURVE_FEE)


def tape_of(tapes, mint):
    t = tapes.get(mint)
    if t is None:
        t = {
            "created": None, "creator": None, "vq0": 0, "vt0": 1, "peak": 0.0,
            "trades": [], "buyers": set(), "entries": 0,
            "dev_sold": False, "last_buy": False,
        }
        tapes[mint] = t
    return t


def flow(t, now):
    net = 0.0
    for i in range(len(t["trades"]) - 1, -1, -1):
        tr = t["trades"][i]
        if tr["slot"] <= now - FLOW_WINDOW:
            break
        net += tr["sol"] if tr["buy"] else -tr["sol"]
    return net


tapes = {}
held = {}


def on_batch(state, batch):
    now = batch["slot"]
    traded = []
    seen_traded = set()
    for e in batch["events"]:
        if e["event"] == "CreateEvent":
            t = tape_of(tapes, e["mint"])
            t["created"] = e["slot"]
            t["creator"] = e.get("user") if e.get("user") is not None else e.get("creator")
            t["vq0"] = int(e["virtual_quote_reserves"])
            t["vt0"] = int(e["virtual_token_reserves"])
            t["peak"] = t["vq0"] / t["vt0"]
            if e["mint"] not in seen_traded:
                seen_traded.add(e["mint"])
                traded.append(e["mint"])
        elif e["event"] == "TradeEvent":
            t = tape_of(tapes, e["mint"])
            price = int(e["virtual_quote_reserves"]) / int(e["virtual_token_reserves"])
            t["trades"].append({
                "slot": e["slot"], "buy": e["is_buy"],
                "sol": int(e["sol_amount"]) / LAMPORTS, "user": e["user"], "price": price,
            })
            if price > t["peak"]:
                t["peak"] = price
            t["last_buy"] = e["is_buy"]
            if t["creator"] is not None and e["user"] == t["creator"] and not e["is_buy"]:
                t["dev_sold"] = True
            if e["is_buy"] and t["creator"] is not None and e["user"] != t["creator"]:
                t["buyers"].add(e["user"])
            if e["mint"] not in seen_traded:
                seen_traded.add(e["mint"])
                traded.append(e["mint"])
    keep = FLOW_WINDOW + 5
    for mint in traded:
        t = tapes[mint]
        cut = 0
        while cut < len(t["trades"]) and t["trades"][cut]["slot"] <= now - keep:
            cut += 1
        if cut > 0:
            del t["trades"][:cut]
    for f in batch["fills"]:
        if f["status"] == "filled" and not f["client_id"].startswith("_"):
            h = held.get(f["mint"])
            if h is not None:
                h["tx_paid"] += int(f["tx_fee_lamports"]) / LAMPORTS
                if f["side"] == "buy":
                    h["filled"] = True
    marks = {m["mint"]: m for m in batch["marks"]}
    pending_by_mint = set()
    for po in state.pending.values():
        pending_by_mint.add(po.order["mint"])
    orders = []
    cap = state.hello["caps"]["max_orders_per_batch"]
    tx = state.tx_fee_lamports() / LAMPORTS

    # Exits first.
    for mint, h in list(held.items()):
        pos = state.positions.get(mint)
        curve = state.curves.get(mint)
        if pos is None:
            if mint not in pending_by_mint:
                del held[mint]
            continue
        if curve is None or curve.complete:
            continue
        mk = marks.get(mint)
        if mk is not None:
            vq = int(mk["virtual_quote_reserves"])
            vt = int(mk["virtual_token_reserves"])
        else:
            vq = curve.virtual_quote_reserves
            vt = curve.virtual_token_reserves
        tokens = pos.token_amount
        value = sell_value(tokens, vq, vt) - tx
        basis = pos.cost_lamports / LAMPORTS + h["tx_paid"]
        if value > h["peak_value"]:
            h["peak_value"] = value
        exit_ = h["exiting"]
        if not exit_ and value >= basis * (1 + TP_BPS / 10000):
            exit_ = True
        if not exit_ and value <= basis * (1 - SL_BPS / 10000):
            exit_ = True
        if (not exit_ and h["peak_value"] >= basis * (1 + TRAIL_ARM_BPS / 10000)
                and value <= h["peak_value"] * (1 - TRAIL_BPS / 10000)):
            exit_ = True
        if not exit_ and MAX_HOLD > 0 and now - h["opened"] >= MAX_HOLD:
            exit_ = True
        if not exit_:
            continue
        h["exiting"] = True
        sell_pending = False
        for po in state.pending.values():
            if po.order["mint"] == mint and po.order["side"] == "sell":
                sell_pending = True
                break
        if sell_pending:
            continue
        if len(orders) >= cap:
            break
        orders.append({"side": "sell", "mint": mint, "token_amount": pos.token_amount,
                       "max_slippage_bps": 10000})

    # Entries and adds, on coins traded this batch.
    free = state.free_cash_lamports() / LAMPORTS
    slots_left = state.hello["caps"]["max_open_positions"] - state.committed_position_count()
    for mint in traded:
        if len(orders) >= cap:
            break
        curve = state.curves.get(mint)
        if curve is None or curve.complete:
            continue
        if mint in pending_by_mint:
            continue
        t = tapes[mint]
        if t["created"] is None or t["vq0"] <= 0:
            continue
        price = curve.virtual_quote_reserves / curve.virtual_token_reserves
        rq_sol = curve.real_quote_reserves / LAMPORTS
        runup_bps = (price / (t["vq0"] / t["vt0"]) - 1) * 10000
        h = held.get(mint)
        if h is None:
            if slots_left <= 0:
                continue
            if t["entries"] >= MAX_ENTRIES:
                continue
            if rq_sol < MIN_RQ_SOL:
                continue
            if runup_bps > MAX_RUNUP_BPS:
                continue
            if len(t["buyers"]) < MIN_BUYERS:
                continue
            if MAX_BUYERS > 0 and len(t["buyers"]) > MAX_BUYERS:
                continue
            if flow(t, now) < MIN_FLOW_SOL:
                continue
            want = min(INITIAL_SOL, STAKE_SOL)
        else:
            if h["exiting"] or not h["filled"]:
                continue
            if h["invested"] >= STAKE_SOL - 0.001:
                continue
            if runup_bps > ADD_MAX_RUNUP_BPS:
                continue
            if price < h["last_add_price"] * (1 + ADD_STEP_BPS / 10000):
                continue
            if flow(t, now) < MIN_FLOW_SOL:
                continue
            want = min(ADD_SOL, STAKE_SOL - h["invested"])
        cap_sol = state.max_buy_lamports(mint) / LAMPORTS
        amount = min(cap_sol, want)
        if amount > free - tx:
            amount = free - tx
        if amount < MIN_BUY_SOL:
            continue
        lamports = math.floor(amount * LAMPORTS)
        orders.append({"side": "buy", "mint": mint, "quote_lamports": lamports,
                       "max_slippage_bps": BUY_SLIP_BPS})
        free -= amount + tx
        if h is None:
            held[mint] = {"opened": now, "invested": amount, "peak_value": 0.0,
                          "last_add_price": price, "exiting": False, "filled": False,
                          "tx_paid": 0.0}
            t["entries"] += 1
            slots_left -= 1
        else:
            h["invested"] += amount
            h["last_add_price"] = price
    return orders


if __name__ == "__main__":
    makefun_bot.run(on_batch)
