"""CP5 — classifier validation on synthetic wallets with known labels.

Built to the EXACT schema observed in CP1.2, including string-typed sz / px /
closedPnl / fee / startPosition, bool crossed, int time.

SYNTH-NULL is generated from a seeded RNG with NO structure imposed and NO
parameter chosen to steer its label. Wherever it lands is the finding.
"""
from __future__ import annotations

import json
import random

import hl_client as hl
import metrics as M

T0 = 1_786_000_000_000
MIN = 60_000
HOUR = 3_600_000
DAY = 86_400_000


def fill(t, coin, side, sz, px, crossed, closed_pnl=0.0, start_pos=0.0, fee=0.0):
    return {"coin": coin, "px": f"{px}", "sz": f"{sz}", "side": side, "time": int(t),
            "startPosition": f"{start_pos}", "dir": "Open Long" if side == "B" else "Open Short",
            "closedPnl": f"{closed_pnl}", "hash": "0x" + "0" * 64, "oid": int(t),
            "crossed": bool(crossed), "fee": f"{fee}", "tid": int(t) * 10 + random.randint(0, 9),
            "cloid": None, "feeToken": "USDC", "twapId": None}


def synth_mm():
    """~3000 fills/day, 95pct of notional maker, flat within minutes, many coins."""
    fills, t = [], T0
    coins = ["BTC", "ETH", "SOL", "ARB", "OP", "AVAX", "DOGE", "LINK"]
    for day in range(5):
        for i in range(1500):
            coin = coins[i % len(coins)]
            px = 100.0 + i % 50
            sz = 1.0
            maker = (i % 20) != 0
            t = T0 + day * DAY + i * 20_000
            fills.append(fill(t, coin, "B", sz, px, not maker, 0.0, 0.0, 0.01))
            fills.append(fill(t + 2 * MIN, coin, "A", sz, px + 0.5, not maker, 0.5, sz, 0.01))
    return fills, []


def synth_carry():
    """One coin, one side, held weeks, funding dominates PnL, very few fills."""
    fills = [fill(T0, "BTC", "B", 100.0, 60000.0, True, 0.0, 0.0, 60.0)]
    fills.append(fill(T0 + 25 * DAY, "BTC", "A", 100.0, 60500.0, True, 5000.0, 100.0, 60.0))
    funding = [{"time": T0 + h * HOUR, "hash": "0x" + "0" * 64,
                "delta": {"type": "funding", "coin": "BTC", "usdc": "250.0",
                          "szi": "100.0", "fundingRate": "0.00001", "nSamples": None}}
               for h in range(0, 25 * 24, 8)]
    return fills, funding


def synth_directional():
    """A few fills/day, mostly taker, held many hours, PnL from closedPnl."""
    fills = []
    for d in range(20):
        t = T0 + d * DAY
        fills.append(fill(t, "ETH", "B", 10.0, 2500.0, True, 0.0, 0.0, 5.0))
        fills.append(fill(t + 8 * HOUR, "ETH", "A", 10.0, 2560.0, True, 600.0, 10.0, 5.0))
    return fills, []


def synth_null(seed=20260908):
    """Structureless. Nothing here is tuned to produce a particular label."""
    rng = random.Random(seed)
    coins = ["BTC", "ETH", "SOL"]
    fills, pos = [], {c: 0.0 for c in coins}
    t = T0
    for _ in range(600):
        t += rng.randint(1, 240) * MIN
        c = rng.choice(coins)
        side = rng.choice(["B", "A"])
        sz = round(rng.uniform(0.1, 5.0), 3)
        px = round(rng.uniform(50, 5000), 1)
        crossed = rng.random() < 0.5
        start = pos[c]
        pos[c] += sz if side == "B" else -sz
        fills.append(fill(t, c, side, sz, px, crossed,
                          round(rng.uniform(-500, 500), 2), start, round(sz * px * 0.0003, 4)))
    return fills, []


def main():
    cases = [("SYNTH-MM", synth_mm(), "MARKET-MAKER"),
             ("SYNTH-CARRY", synth_carry(), "NEUTRAL/CARRY"),
             ("SYNTH-DIRECTIONAL", synth_directional(), "DIRECTIONAL"),
             ("SYNTH-NULL", synth_null(), "UNCLASSIFIED")]
    out, ok = [], 0
    for name, (fills, funding), expect in cases:
        m = M.compute(name, fills, funding)
        got = M.classify(m)
        passed = got == expect
        ok += passed
        out.append({"synthetic": name, "expected": expect, "got": got,
                    "pass": passed, "metrics": m})
        print(f"  {name:20s} expect {expect:14s} got {got:14s} {'PASS' if passed else 'FAIL'}")
        for k in ("maker_share_ntl", "fills_per_active_day",
                  "median_flat_to_flat_holding_seconds", "never_closed_fraction",
                  "mean_abs_net_exposure_over_gross", "funding_share_of_pnl",
                  "n_distinct_coins", "fee_paid_over_gross_notional",
                  "closedPnl_count", "closedPnl_median", "closedPnl_mean",
                  "best_episode_share_of_profit"):
            v = m.get(k)
            print(f"        {k:38s} {v if v is None else round(v, 6) if isinstance(v, float) else v}")
    verdict = "GREEN" if ok == 4 else "RED"
    hl.save({"checkpoint": "CP5", "status": verdict, "recovered": f"{ok}/4",
             "gate": "4/4 required", "cases": out}, "receipts/cp5.json")
    print(f"\n  CP5 {verdict}: {ok}/4 recovered")
    return 0 if ok == 4 else 1


if __name__ == "__main__":
    raise SystemExit(main())
