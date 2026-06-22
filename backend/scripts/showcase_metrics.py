#!/usr/bin/env python3
"""Honest, size-independent showcase metrics engine (NON-sacred, draft).

ONE consistent basis everywhere — FIXED position size, NON-COMPOUNDED:
  * Each trade's metric is its per-trade ``Net PnL %`` (= NetPnL_INR /
    position_value), already size-independent. We use the RAW Net PnL %
    (TradingView's per-trade value); the Indian cost-model haircut is a
    SEPARATE, flagged option (see NOTES) and is NOT applied here.
  * Max drawdown = peak-to-trough of the RUNNING SUM of per-trade Net PnL %,
    in percentage POINTS, NOT normalised by the running peak. (Normalising by
    peak was the previous ~2x-too-low / compounded-flavoured bug.)
  * TradingView's compounded ``Cumulative PnL %`` is never read. No compounded
    totals anywhere.

Reads the ISOLATED backtest SQLite only — never the app Postgres / live data.
Trades are ordered by EXIT date (when the Net PnL % is realised) for the
running-sum drawdown; per-year / per-month drawdowns reset within the period.
"""
from __future__ import annotations

import sqlite3
import statistics
from collections import OrderedDict, defaultdict

DEFAULT_DB = "backend/backtest_signal_history.sqlite3"


def load_by_instrument(db: str) -> dict[str, list[tuple[str, float, int]]]:
    """Return {instrument: [(exit_dt, net_pnl_pct, trade_number), ...]} sorted
    by (exit_dt, trade_number). ALL rows (open MTM row included — matches the
    trade-list trade count)."""
    conn = sqlite3.connect(db)
    out: dict[str, list[tuple[str, float, int]]] = defaultdict(list)
    rows = conn.execute(
        "SELECT instrument, exit_dt, net_pnl_pct, trade_number "
        "FROM backtest_trades WHERE net_pnl_pct IS NOT NULL"
    ).fetchall()
    conn.close()
    for inst, exit_dt, pnl, tnum in rows:
        out[inst].append((exit_dt, float(pnl), int(tnum)))
    for inst in out:
        out[inst].sort(key=lambda r: (r[0], r[2]))
    return dict(out)


def max_drawdown(pcts: list[float]) -> float:
    """Peak-to-trough of the running SUM of per-trade % (percentage points,
    non-compounded, NOT normalised by peak). Returns a non-positive number.

    Baseline peak starts at 0.0 so a drawdown from the very first trades counts.
    """
    cum = 0.0
    peak = 0.0
    mdd = 0.0
    for r in pcts:
        cum += r
        if cum > peak:
            peak = cum
        dd = cum - peak
        if dd < mdd:
            mdd = dd
    return mdd


def metrics(rows: list[tuple[str, float, int]]) -> dict:
    """5 metrics for an ordered list of (exit_dt, net_pnl_pct, trade_number).

    Order matters only for max_drawdown; count/win/avg/PF are order-independent.
    """
    pcts = [r[1] for r in rows]
    n = len(pcts)
    if n == 0:
        return {"trades": 0, "win_rate_pct": 0.0, "avg_net_pct_per_trade": 0.0,
                "profit_factor": None, "max_drawdown_pct": 0.0}
    wins = [x for x in pcts if x > 0]
    losses = [x for x in pcts if x < 0]
    pf = (sum(wins) / abs(sum(losses))) if losses else None  # None = no losses (infinite PF)
    return {
        "trades": n,
        "win_rate_pct": round(100.0 * len(wins) / n, 2),
        "avg_net_pct_per_trade": round(statistics.mean(pcts), 4),
        "profit_factor": round(pf, 4) if pf is not None else None,
        "max_drawdown_pct": round(max_drawdown(pcts), 2),
    }


def longest_losing_streak(rows: list[tuple[str, float, int]]) -> int:
    """Longest run of consecutive losing trades (net % < 0), chronological."""
    streak = best = 0
    for r in rows:
        if r[1] < 0:
            streak += 1
            best = max(best, streak)
        else:
            streak = 0
    return best


def aggregate_metrics(rows: list[tuple[str, float, int]]) -> dict:
    """The 5 verified core metrics + honest extras (size-independent)."""
    pcts = [r[1] for r in rows]
    base = metrics(rows)
    if not pcts:
        return base
    wins = [x for x in pcts if x > 0]
    losses = [x for x in pcts if x < 0]
    base.update({
        "wins": len(wins),
        "losses": len(losses),
        "flats": len([x for x in pcts if x == 0]),
        "best_trade_pct": round(max(pcts), 2),
        "worst_trade_pct": round(min(pcts), 2),
        "median_net_pct_per_trade": round(statistics.median(pcts), 4),
        "longest_losing_streak": longest_losing_streak(rows),
    })
    return base


def per_period(rows: list[tuple[str, float, int]], width: int) -> "OrderedDict[str, dict]":
    """Group by exit-date prefix (width 4 = year 'YYYY', 7 = month 'YYYY-MM')
    and compute metrics within each period (drawdown resets per period)."""
    groups: "OrderedDict[str, list]" = OrderedDict()
    for r in sorted(rows, key=lambda x: (x[0], x[2])):
        key = r[0][:width]
        groups.setdefault(key, []).append(r)
    return OrderedDict((k, metrics(v)) for k, v in groups.items())


def compute_all(db: str = DEFAULT_DB) -> dict:
    data = load_by_instrument(db)
    result = {}
    for inst, rows in data.items():
        result[inst] = {
            "aggregate": metrics(rows),
            "by_year": per_period(rows, 4),
            "by_month": per_period(rows, 7),
        }
    return result


# ── 4-state honest live labels + display ───────────────────────────────────
DISPLAY = {"BSE": "NSE:BSE Futures", "CDSL": "NSE:CDSL Futures", "ANGELONE": "NSE:ANGELONE Futures"}
LIVE_STATE = {
    "BSE": ("LIVE_REAL", "Live (real money)",
            "Live real-money strategy. Past performance is not a guarantee of future results."),
    "CDSL": ("LIVE_NO_TRADES", "Newly live — no live trades yet",
             "Recently switched to live; no real-money trades executed yet. Backtest shown is in-sample."),
    "ANGELONE": ("PAPER", "Paper (simulated)",
                 "Paper / backtest-only candidate — not deployed live; no real money traded."),
}
CAVEATS = [
    "IN-SAMPLE backtest — a hypothesis about edge, NOT a guarantee of future results.",
    "Size-independent per-trade metrics on a FIXED position size, NON-compounded basis.",
    "Max drawdown = peak-to-trough of the running SUM of per-trade Net PnL % (percentage points), "
    "NOT normalised by peak — this is not a compounded equity drawdown.",
    "Raw Net PnL % basis. Estimated Indian F&O costs are NOT applied here (see cost_model).",
    "No slippage modelled; backtest fills at signal price.",
    "Backtest is separate from live. No compounded totals or rupee P&L appear anywhere.",
    "ANGELONE is PAPER; CDSL is newly live with no live trades yet; only BSE has live real-money history.",
]


def build_doc(db: str = DEFAULT_DB, *, generated_utc: str = "") -> dict:
    """Assemble the regenerated showcase artifact (aggregate + per-year +
    per-month per strategy, 4-state labels, in-sample caveats). No series,
    no compounded totals, no INR."""
    data = load_by_instrument(db)
    strategies = []
    for inst in ["BSE", "CDSL", "ANGELONE"]:
        rows = data[inst]
        exits = sorted(r[0] for r in rows)
        track_type, label, disc = LIVE_STATE[inst]
        strategies.append({
            "key": inst.lower(),
            "instrument": inst,
            "display_name": DISPLAY[inst],
            "backtest": {
                "track_type": "BACKTEST_IN_SAMPLE",
                "label": "Backtest (in-sample)",
                "disclaimer": "In-sample backtest — not a guarantee of live results.",
                "strategy_version": "v4.8.1",
                "source": "tv_trade_list",
                "basis": "fixed_position_size_non_compounded_raw_net_pct",
                "in_sample_range": {"from": exits[0][:7], "to": exits[-1][:7]},
                "aggregate": aggregate_metrics(rows),
                "by_year": per_period(rows, 4),
                "by_month": per_period(rows, 7),
            },
            "live_status": {"track_type": track_type, "label": label, "disclaimer": disc},
        })
    return {
        "meta": {
            "generated_utc": generated_utc,
            "kind": "DRAFT — review-only showcase metrics (Module 1 regenerate)",
            "strategy_version": "v4.8.1",
            "source": "tv_trade_list",
            "store": "isolated SQLite backtest_trades (read-only)",
            "basis": "fixed_position_size_non_compounded",
            "drawdown_definition": "peak_to_trough_of_running_sum_of_per_trade_net_pct_percentage_points_not_normalised",
            "cost_model": {
                "applied": False,
                "note": "FLAG for review: optionally apply the Indian F&O cost model (costs.py) as a "
                        "UNIFORM haircut across ALL metrics + periods. NOT applied here — these figures "
                        "are on the raw Net PnL % basis (matching the verified reference values).",
            },
            "excluded_artifacts": ["compounded_cumulative", "inr_pnl", "position_qty", "position_value"],
            "caveats": CAVEATS,
        },
        "strategies": strategies,
    }


# ── reference values (independently provided; must reproduce exactly) ───────
REFERENCE = {
    "BSE": {"trades": 1149, "win_rate_pct": 77.5, "avg_net_pct_per_trade": 1.62, "profit_factor": 5.80, "max_drawdown_pct": -10.30},
    "CDSL": {"trades": 1032, "win_rate_pct": 70.8, "avg_net_pct_per_trade": 1.13, "profit_factor": 3.91, "max_drawdown_pct": -11.89},
    "ANGELONE": {"trades": 942, "win_rate_pct": 73.1, "avg_net_pct_per_trade": 1.42, "profit_factor": 3.82, "max_drawdown_pct": -17.86},
}
REFERENCE_ANGELONE_YEAR_DD = {
    "2020": -17.86, "2021": -15.45, "2022": -13.91, "2023": -16.31,
    "2024": -15.95, "2025": -14.14, "2026": -14.61,
}
TOL = {"trades": 0, "win_rate_pct": 0.1, "avg_net_pct_per_trade": 0.01, "profit_factor": 0.01, "max_drawdown_pct": 0.01}


def verify(db: str = DEFAULT_DB) -> bool:
    res = compute_all(db)
    ok = True
    print("=== AGGREGATE verification (computed vs reference) ===")
    for inst, ref in REFERENCE.items():
        got = res[inst]["aggregate"]
        for k, refv in ref.items():
            gotv = got[k]
            diff = abs(gotv - refv)
            passed = diff <= TOL[k]
            ok = ok and passed
            print(f"  {inst:8} {k:24} got={gotv!s:>10}  ref={refv!s:>8}  {'PASS' if passed else 'MISMATCH (Δ='+format(diff,'.4f')+')'}")
    print("\n=== ANGELONE per-YEAR max-drawdown verification ===")
    ang_year = res["ANGELONE"]["by_year"]
    for yr, refdd in REFERENCE_ANGELONE_YEAR_DD.items():
        gotdd = ang_year.get(yr, {}).get("max_drawdown_pct")
        passed = gotdd is not None and abs(gotdd - refdd) <= 0.01
        ok = ok and passed
        print(f"  {yr}  got={gotdd!s:>8}  ref={refdd:>8}  {'PASS' if passed else 'MISMATCH'}")
    print(f"\n=== OVERALL: {'ALL PASS' if ok else 'MISMATCH — STOP, do not regenerate'} ===")
    return ok


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "regen":
        out = sys.argv[2] if len(sys.argv) > 2 else "backend/scripts/showcase_backtest.json"
        # verify FIRST — never regenerate from a mismatched engine
        if not verify():
            print("\nABORT: reference verification failed — not regenerating.")
            sys.exit(1)
        from datetime import datetime, timezone
        doc = build_doc(generated_utc=datetime.now(timezone.utc).isoformat())
        with open(out, "w") as f:
            json.dump(doc, f, indent=2)
        print(f"\nregenerated {out}")
        for s in doc["strategies"]:
            a = s["backtest"]["aggregate"]
            print(f"  {s['instrument']:8} live={s['live_status']['track_type']:14} "
                  f"trades={a['trades']:5} win={a['win_rate_pct']}% avg={a['avg_net_pct_per_trade']}% "
                  f"PF={a['profit_factor']} maxDD={a['max_drawdown_pct']}%  years={len(s['backtest']['by_year'])}")
    else:
        verify(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB)
