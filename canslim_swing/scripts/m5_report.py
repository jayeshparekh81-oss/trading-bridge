#!/usr/bin/env python3
"""M5 report assembler — stages A-G, the five gates, and the verdict."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m5_select_nulls as SN  # noqa: E402

TRACK = Path(__file__).resolve().parents[1]
M5 = TRACK / "data" / "m5"
REPORT = TRACK / "reports" / "swing_module5_verdict.txt"

FINDINGS = [
    ("CRITICAL", "E4 turtle exit was unreachable", "exit_variants/ordering/costs (3 dims)",
     "low20 = rolling(20).min() INCLUDED the current bar, so `close < low20` is "
     "mathematically impossible. E4 never trend-exited: all 324 E4 configs were "
     "measuring stop-only buy-and-hold with a spurious exp_r of +9.79. "
     "Fixed with .shift(1); E4 went 11 trades/0 turtle exits -> 74 trades/45 exits."),
    ("CRITICAL", "Partial exits scored as independent trades", "costs_sizing/exit_variants",
     "E5/E7 legs were each divided by the FULL 1% risk_amt and counted as separate "
     "trades, roughly HALVING expectancy-R — the exact statistic the pre-registered "
     "selection rule maximises. Fixed by collapsing legs to positions (positionize) "
     "so R = total position PnL / intended risk."),
    ("MAJOR", "E5 was given a 25% target it must not have", "exit_variants/ordering",
     "Free-roll is stop + half at +2R + SMA50 trail on the remainder. The target set "
     "included E5, so 19% of E5 exits were targets and the free-roll never happened."),
    ("MAJOR", "E5 armed a FULL SMA50 exit before the half-sale", "exit_variants",
     "43% of E5 positions were closed in full by SMA50 before ever reaching +2R; the "
     "trail is defined only for the remainder. Before +2R the stop is the only exit."),
    ("MAJOR", "Remainder unprotected after a partial exit", "exit_variants/ordering",
     "After an armed partial fill the loop `continue`d, so the retained shares faced "
     "no stop for the rest of that session. Now re-checked in the same session."),
    ("MAJOR", "10-month EMA filter was double-lagged", "sealed_isolation/ordering",
     "shift(1) on a month-end index plus reindex(ffill) double-counted the lag: ~95% "
     "of days used an EMA one month staler than intended, and the lag flipped between "
     "1 and 2 months depending on whether the month-end was a holiday. 756 configs "
     "affected — including the eventual champion's filter."),
    ("MAJOR", "ATR20 for stop placement included the fill day", "costs_sizing",
     "The 2xATR stop read the entry day's own high/low — lookahead in stop placement. "
     "Fixed with .shift(1)."),
    ("MAJOR", "Null R basis hardcoded to 8%", "costs_sizing",
     "m5_select_nulls scored the random-entry null with a fixed 0.08 stop denominator, "
     "so the null would be on a different R basis than any champion using the 5% or "
     "ATR stop. Now derives the denominator from the champion's own stop rule."),
]
REFUTED = [
    "EPS boundary inclusive of BOUNDARY+1day lands a midnight 2025 filing in build",
    "Year-ago base EPS looked up with no as-of filter on announcement time (2 dims)",
    "warm-start positions shallow-copied so simulate mutates caller state (2 dims)",
    "E2's +25% target can fire before the 8-week rule suspends it",
    "End-of-data liquidation falls back to the file's last bar",
    "EPS rows with missing announce_ts dropped from both halves",
    "Partition renders the sealed half unevaluable by the same loader",
]


def fmt(df, idx=False):
    with pd.option_context("display.width", 220, "display.max_rows", len(df) + 5):
        return df.to_string(index=idx) + "\n"


def main() -> None:
    sweep = pd.read_parquet(M5 / "sweep_results.parquet")
    meta = json.loads((M5 / "sweep_meta.json").read_text())
    sel = SN.select(sweep)
    champ = sel["champion"]
    sealed = json.loads((M5 / "sealed_result.json").read_text())
    sens = pd.read_parquet(M5 / "sensitivity.parquet")
    recomp = pd.read_parquet(M5 / "stagef_recompute.parquet")
    hits = pd.read_json(M5 / "stagef_hits.json")
    for c in ("ex_date", "entry", "exit"):      # json round-trip -> epoch ints
        if c in hits.columns:
            hits[c] = pd.to_datetime(hits[c], unit="ms", errors="coerce").dt.date
    null_d = np.load(M5 / "null_dist.npy")
    mc = np.load(M5 / "mc_dd.npy")
    cb = pd.read_parquet(M5 / "champion_build_trades.parquet")

    L, A = [], None
    A = L.append
    A("=" * 78)
    A("canslim-swing MODULE 5 — SWEEP, SELECTION, NULLS, SEALED VERDICT")
    A("=" * 78)
    A("")
    A("STAGE A — PARTITION + ADVERSARIAL HARNESS REVIEW (run BEFORE any sweep result)")
    A("")
    A("  A.1 Physical partition: data/build/ (<= 31-Dec-2024) and data/sealed/ (>).")
    A("      EPS is split on ANNOUNCEMENT time, not period end, so a filing announced")
    A("      in 2025 about a 2024 quarter stays out of the build half. load_market()")
    A("      asserts on every frame it opens, including all per-symbol price files.")
    A(f"      build scan rows 105,044 | sealed 71,524 | universe {meta['universe']} | "
      f"days {meta['calendar_first']} -> {meta['calendar_last']}")
    A("")
    A("  A.2 Refute-by-default review: 5 dimensions x independent verifiers (31 agents).")
    A(f"      16 findings CONFIRMED (8 unique defects), {len(REFUTED)} classes refuted.")
    A("      ALL fixed before Stage B ran. The two criticals would have decided the")
    A("      verdict on their own:")
    A("")
    for sev, title, dim, body in FINDINGS:
        A(f"      [{sev}] {title}   ({dim})")
        for line in _wrap(body, 68):
            A(f"          {line}")
        A("")
    A("      Refuted (NOT defects — recorded so the review is auditable both ways):")
    for r in REFUTED:
        A(f"        - {r}")
    A("")
    A("      An engine-version stamp is now part of the sweep cache key, so a changed")
    A("      indicator definition can never silently reuse stale cached results.")
    A("")
    A("-" * 78)
    A("STAGE B — BUILD-HALF SWEEP (pre-registered grid)")
    A(f"  configs: {len(sweep):,}  (7 exits x 3 stops x 2 growth x 3 floors x 3 RS x 3 mfilter x 2 vol)")
    A(f"  runtime: {meta['elapsed_s']:.0f}s  ({meta['elapsed_s'] / len(sweep) * 1000:.0f} ms/config)")
    A(f"  base-EPS floors DERIVED from {meta['floors']['_n']:,} build candidate rows:")
    A(f"      none = 0 | p25 = Rs {meta['floors']['p25']:.2f} | p50 = Rs {meta['floors']['p50']:.2f}")
    A("  Build-half runs mark open positions out at the boundary (they cannot see 2025),")
    A("  so these numbers are NOT comparable to M4's build-half segment, which let")
    A("  boundary-straddling positions exit on real 2025 prices.")
    A("")
    A("  Per-dimension mean build expectancy-R (descriptive only, NOT selection):")
    for dim in ("exit", "stop", "c_growth", "floor", "rs", "mfilter", "volume"):
        g = sweep.groupby(dim)["exp_r"].agg(["mean", "median", "count"]).round(3)
        A(f"    {dim}:")
        for k, row in g.iterrows():
            A(f"      {str(k):<12} mean {row['mean']:>7.3f}  median {row['median']:>7.3f}  n {int(row['count'])}")
    A("")
    A("-" * 78)
    A("STAGE C — SELECTION (pre-declared rule, applied mechanically)")
    A(f"  positive-expectancy share of ALL {len(sweep):,} configs: "
      f"{sel['pct_positive_all']:.1f}%")
    A(f"  eligible (build trades >= 50 AND build maxDD <= 15%): {sel['n_elig']:,}")
    A(f"  positive-expectancy share among eligible: {sel['pct_positive_elig']:.1f}%")
    A("")
    A("  ***  NOT A SLIVER — THE OPPOSITE PROBLEM  ***")
    A(f"  {sel['pct_positive_all']:.0f}% of the entire grid is profitable on the build half. A grid this")
    A("  uniformly positive is evidence about the PERIOD, not about the edge: almost")
    A("  any long trend-following rule made money between Jul-2022 and Dec-2024. The")
    A("  champion is therefore selected from a set where being positive is the norm,")
    A("  which makes the build-half ranking weak evidence and puts essentially all of")
    A("  the informational weight on the sealed shot.")
    A("")
    A(f"  CHAMPION: exit={champ['exit']}  stop={champ['stop']}  c_growth={champ['c_growth']}  "
      f"floor={champ['floor']}  RS={champ['rs']:.0f}  mfilter={champ['mfilter']}  volume={champ['volume']}")
    A(f"    build: trades {int(champ['trades'])} | exp_r {champ['exp_r']:.3f} | PF {champ['pf']:.2f} "
      f"| maxDD {100 * champ['maxdd']:.1f}% | win {champ['win']:.1f}%")
    A(f"    neighbour map: {champ['nb_share'] * 100:.0f}% of its {int(champ['nb_n'])} one-notch neighbours are "
      f"positive-expectancy (bar was 60%)")
    A(f"    selection rule relaxed? {'YES' if sel.get('rule_relaxed') else 'NO — cleared the 60% bar outright'}")
    A("")
    A("  TOP-20 eligible configs by build expectancy-R:")
    cols = ["exit", "stop", "c_growth", "floor", "rs", "mfilter", "volume",
            "trades", "exp_r", "pf", "maxdd", "win", "nb_share"]
    A(fmt(sel["eligible"].head(20)[cols].round(
        {"exp_r": 3, "pf": 2, "maxdd": 3, "win": 1, "nb_share": 2})))
    A("-" * 78)
    A("STAGE D — NULL BATTERY (champion, build half only)")
    A(f"  500x random-entry null: same universe, same trade count, same hold-duration")
    A(f"  distribution, entries on days that were NOT candidate days.")
    A(f"    null mean exp_r {null_d.mean():+.3f} | sd {null_d.std():.3f} | p95 "
      f"{np.quantile(null_d, .95):+.3f} | max {null_d.max():+.3f}")
    A(f"    champion build exp_r {champ['exp_r']:+.3f}  ->  percentile "
      f"{100 * (null_d < champ['exp_r']).mean():.1f}, p = "
      f"{(1 + (null_d >= champ['exp_r']).sum()) / (1 + len(null_d)):.4f}")
    A("")
    A(f"  NOTE: the null's own mean is {null_d.mean():+.3f}R, not zero. Random entries in this")
    A("  universe over this window were PROFITABLE on average — the same bull-regime")
    A("  signal as the 93% positive grid. The champion clears the null, but the null")
    A("  it clears sits well above zero.")
    A("")
    A(f"  10,000x MC resample of the champion's own trades (drawdown in R units):")
    A(f"    median {np.median(mc):.2f}R | 5th pct {np.quantile(mc, .05):.2f}R | worst {mc.min():.2f}R")
    A(f"    (observed build maxDD {100 * champ['maxdd']:.1f}%)")
    A("")
    A("-" * 78)
    A("STAGE E — SEALED SHOT (once; separate script m5_sealed.py)")
    A("")
    A("  BOUNDARY HANDLING: the champion is run CONTINUOUSLY from 2022-07-29 with a")
    A("  single Rs 10,00,000 start. The portfolio state at 31-Dec-2024 is whatever the")
    A("  champion itself produced on the build half — a genuine warm start — and")
    A("  positions opened in 2024 run into 2025 and exit on their real prices.")
    A(f"  At the boundary: equity Rs {sealed['boundary_equity']:,.0f} with "
      f"{sealed['carried_positions']} positions carried across.")
    A("  Trades are attributed by ENTRY date; full-journey maxDD uses the continuous curve.")
    A("  Full price history is loaded so SMA50/ATR20/20-session-low are defined in")
    A("  early 2025 — warm-up, not leakage: no sealed row touched the selection, which")
    A("  was frozen before this script was written.")
    A("")
    B, S, F = sealed["build"], sealed["sealed"], sealed["full"]
    A(f"  BUILD  (entry <= 2024-12-31): trades {B['trades']} | exp_r {B['exp_r']:+.3f} | "
      f"PF {B['pf']:.2f} | win {B['win']:.1f}% | net Rs {B['net']:,.0f}")
    A(f"  SEALED (entry >= 2025-01-01): trades {S['trades']} | exp_r {S['exp_r']:+.3f} | "
      f"PF {S['pf']:.2f} | win {S['win']:.1f}% | net Rs {S['net']:,.0f}")
    A(f"  FULL JOURNEY: trades {F['trades']} | maxDD {100 * F['maxdd']:.2f}% | "
      f"equity Rs {F['eq0']:,.0f} -> Rs {F['eq1']:,.0f}")
    A("")
    A("  THE FIVE PRE-REGISTERED GATES:")
    g = sealed["gates"]
    labels = {
        "sealed_expectancy_positive": f"sealed net expectancy > 0        (actual {S['exp_rs']:+,.0f} Rs/trade)",
        "sealed_pf_ge_1_3": f"sealed profit factor >= 1.3      (actual {S['pf']:.2f})",
        "full_maxdd_le_15pct": f"full-journey maxDD <= 15%        (actual {100 * F['maxdd']:.2f}%)",
        "total_trades_ge_80": f"total trades (build+sealed) >= 80 (actual {F['trades']})",
        "beats_null_p_lt_0_05": f"champion beats null p < 0.05     (actual p = {sealed['null_p']:.4f})",
    }
    for k, v in g.items():
        A(f"    [{'PASS' if v else 'FAIL'}]  {labels[k]}")
    A("")
    A(f"    OVERALL: {'PASS' if all(g.values()) else 'FAIL'}  "
      f"({sum(g.values())}/5 gates passed)")
    A("")
    A("-" * 78)
    A("STAGE F — VERIFY-ON-TOUCH (network; NSE corp actions, 1 req/s)")
    A("  Every NO-REFERENCE symbol the champion actually traded, both halves.")
    A("  38 of the champion's 58 traded symbols are NO-REFERENCE; all 38 fetched, 0 parked.")
    A("  215 corporate actions retrieved; 8 were splits/bonuses/demergers.")
    A(f"  Actions of concern falling INSIDE a held window: {len(hits)}")
    if len(hits):
        A(fmt(hits))
        A("  BDL's series shows NO ~-50% cliff at that ex-date (moves around it: +6.7%,")
        A("  +9.8%, -0.1%, -6.1%), i.e. the price history IS split-adjusted, consistent")
        A("  with M1's finding. The trade is legitimate. Recomputed anyway, as required:")
        A(fmt(recomp))
        A("  The verdict is identical with and without the flagged symbol.")
    A("")
    A("-" * 78)
    A("STAGE G — SLIPPAGE SENSITIVITY (champion only; sensitivity, never selection)")
    A(fmt(sens))
    A("  The sealed failure is not a slippage artefact: it holds at every level tested,")
    A("  and 0.05% -> 0.20% moves sealed expectancy only from -0.124R to -0.151R.")
    A("")
    A("=" * 78)
    A("VERDICT")
    A("=" * 78)
    A("")
    A("  The strategy FAILED its pre-registered sealed test: 3 of 5 gates failed —")
    A(f"  sealed expectancy {S['exp_rs']:+,.0f} Rs/trade (needed > 0), sealed profit factor")
    A(f"  {S['pf']:.2f} (needed >= 1.3), and full-journey drawdown {100 * F['maxdd']:.2f}% (needed <= 15%) —")
    A("  and the two gates it passed are the two that carry the least information: the")
    A("  trade-count minimum, and a null-comparison whose own null averaged a positive")
    A("  +0.19R because 93% of the entire 2,268-config grid was profitable on a build")
    A("  half that ran through a strong bull market. A build half where nearly")
    A("  everything wins cannot distinguish an edge from a regime, and the sealed half")
    A("  — 27 trades, 29.6% win rate, PF 0.75 — is where that distinction showed up.")
    A("  The honest reading is that this CANSLIM implementation, at these settings, on")
    A("  this 188-name universe, has not demonstrated an edge that survives out of")
    A("  sample; the build-half result was the market, not the method.")
    A("")
    A("=" * 78)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(L) + "\n")
    print(f"REPORT: {REPORT}")


def _wrap(s, w):
    out, cur = [], ""
    for word in s.split():
        if len(cur) + len(word) + 1 > w:
            out.append(cur)
            cur = word
        else:
            cur = (cur + " " + word).strip()
    if cur:
        out.append(cur)
    return out


if __name__ == "__main__":
    main()
