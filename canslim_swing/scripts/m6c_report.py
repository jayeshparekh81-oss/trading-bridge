#!/usr/bin/env python3
"""M6c report — Round-2A sealed shot, grid thermometer, nulls, gates, verdict."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

TRACK = Path(__file__).resolve().parents[1]
R2 = TRACK / "data" / "round2"
REPORT = TRACK / "reports" / "swing_module6c_round2_verdict.txt"
INSURERS = ["HDFCLIFE", "ICICIGI", "ICICIPRULI", "SBILIFE"]
LATE_IPO = ["ETERNAL", "IRFC", "KALYANKJIL", "LODHA", "SONACOMS"]


def fmt(df, idx=False):
    if df is None or len(df) == 0:
        return "  (none)\n"
    with pd.option_context("display.width", 220, "display.max_rows", len(df) + 5):
        return df.to_string(index=idx) + "\n"


def main() -> None:
    led = pd.read_parquet(R2 / "r2_champion_trades.parquet")
    eq = pd.read_parquet(R2 / "r2_champion_equity.parquet")
    grid = pd.read_parquet(R2 / "r2_grid.parquet")
    nul = np.load(R2 / "r2_null.npy")
    mc = np.load(R2 / "r2_mc_dd.npy")
    sens = pd.read_parquet(R2 / "r2_sensitivity.parquet")
    sect = pd.read_parquet(R2 / "r2_sector_trades.parquet")
    hits = pd.read_parquet(R2 / "r2_stagef_hits.parquet")
    cov = pd.read_parquet(R2 / "coverage.parquet")

    w = led[led["net_pnl"] > 0]
    l = led[led["net_pnl"] <= 0]
    pf = w["net_pnl"].sum() / max(-l["net_pnl"].sum(), 1e-9)
    exp_rs = led["net_pnl"].mean()
    exp_r = led["r_multiple"].mean()
    maxdd = float((eq["equity"] / eq["equity"].cummax() - 1).min())
    pval = (1 + (nul >= exp_r).sum()) / (1 + len(nul))

    gates = {
        "in-window expectancy > 0": (exp_rs > 0, f"{exp_rs:+,.0f} Rs/trade"),
        "in-window PF >= 1.3": (pf >= 1.3, f"{pf:.2f}"),
        "in-window maxDD <= 15%": (maxdd >= -0.15, f"{100*maxdd:.2f}%"),
        "trades >= 60": (len(led) >= 60, f"{len(led)}"),
        "beats null p < 0.05": (pval < 0.05, f"p = {pval:.4f}"),
    }

    L, A = [], None
    A = L.append
    A("=" * 78)
    A("canslim-swing MODULE 6c — ROUND-2A SEALED SHOT + GRID THERMOMETER + NULL")
    A("Registered frame: window 01-Apr-2019 -> 31-Jul-2021, cold start Rs 10,00,000.")
    A("One config. One shot. No tuning. No rerun after reading.")
    A("=" * 78)
    A("")
    A("STAGE A — ISOLATION + ADVERSARIAL REVIEW (run BEFORE any result was read)")
    A("")
    A("  A.1 Separate runner (m6c_run.py) with a hard assertion that no trade entry,")
    A("      trade exit or equity row predates 2019-04-01. The scan root spans")
    A("      2016-2021 so indicators/52w levels/EPS year-ago bases are warm, but the")
    A("      simulation calendar is restricted to the window: warmup can be READ,")
    A("      never ACTED ON. Cold start, no warm-start positions (differs from M5).")
    A("")
    A("  A.2 Refute-by-default review, 4 dimensions x independent verifiers (14 agents).")
    A("      1 CRITICAL confirmed, 9 claims refuted. Fixed BEFORE Stage B ran:")
    A("")
    A("      [CRITICAL] Post-window EPS decided the cons/stand SERIES PICK.")
    A("          eps_base_table counts each symbol's quarters over the WHOLE eps frame")
    A("          with no as-of cutoff. The merged Round-2 parquet carries announcements")
    A("          out to 2026 — 62% of its rows postdate the window — so a 2026 filing")
    A("          could decide which series a 2019 scan day used. Every OTHER as-of rule")
    A("          in that function was verified correct (announce_ts <= EOD, cummax of")
    A("          period_end in announcement order, (year,month) year-ago match, 200-day")
    A("          staleness, NaT/NaN dropped). MEASURED IMPACT: PF 1.68 -> 1.16. Left in,")
    A("          it would have manufactured a PASS on the PF gate.")
    A("          FIX: the EPS frame is truncated at the sealed boundary in m6c_run.load()")
    A("          with an assertion, so post-window announcements are invisible.")
    A("")
    A("      Also fixed pre-emptively (found by me, independently confirmed): the grid's")
    A("      base-EPS floors were derived from the full 2016-2021 scan; now computed")
    A("      from IN-WINDOW rows only (p25 Rs 2.775, p50 Rs 4.120 from 1,143 rows).")
    A("      Verified by direct test: 0 symbols lack a bar on the last window session,")
    A("      so the terminal force-close can never price from a post-window bar.")
    A("")
    A("      RESIDUAL, STATED: within the window the series pick still uses the full")
    A("      in-window announcement history rather than being per-day. That is the")
    A("      same rule M3/M5/Round-1 used, so it is consistent rather than a new leak,")
    A("      and the reviewer verified the per-day variant reproduces this exact result.")
    A("")
    A("-" * 78)
    A("UNIVERSE DISCLOSURE")
    A(f"  registered: 169 = M6b's 173 audited MINUS 4 insurers ({', '.join(INSURERS)}),")
    A("  dropped because M6b measured them at 0% C-gate coverage for EVERY quarter.")
    A(f"  EFFECTIVE: 164. Five more symbols produce no scan row at all — "
      f"{', '.join(LATE_IPO)}")
    A("  IPO'd between Jan and Jul 2021 and never reach the 252-session minimum before")
    A("  the window closes. Correct fail-closed behaviour; the registered 169 was")
    A("  optimistic and 164 is the number every result below actually rests on.")
    A("")
    A("-" * 78)
    A("STAGE B — CHAMPION, ONE SHOT")
    A("  E4 (stop + close < prior 20-session low) | stop 8% | C-growth 1.30x |")
    A("  no base-EPS floor | RS >= 90 within the 164 | Nifty > 10-month EMA | no vol rule")
    A("")
    A(f"    trades              {len(led)}")
    A(f"    win rate            {100*len(w)/len(led):.1f}%")
    A(f"    expectancy          {exp_rs:+,.0f} Rs/trade   ({exp_r:+.3f} R)")
    A(f"    profit factor       {pf:.2f}")
    A(f"    max drawdown        {100*maxdd:.2f}%")
    A(f"    net PnL             {led['net_pnl'].sum():+,.0f} Rs")
    A(f"    equity              {eq['equity'].iloc[0]:,.0f} -> {eq['equity'].iloc[-1]:,.0f} Rs")
    A(f"    avg hold            {led['days_held'].mean():.1f} sessions")
    A(f"    exit mix            {led['exit_reason'].value_counts().to_dict()}")
    A("")
    A("-" * 78)
    A("STAGE C — GRID THERMOMETER (all 2,268 configs in-window; SELECTION FORBIDDEN)")
    A(f"  positive expectancy: {100*(grid['exp_r']>0).mean():.1f}% of 2,268 configs")
    A(f"  exp_r spread: min {grid['exp_r'].min():+.3f} | p25 {grid['exp_r'].quantile(.25):+.3f} "
      f"| median {grid['exp_r'].median():+.3f} | p75 {grid['exp_r'].quantile(.75):+.3f} "
      f"| max {grid['exp_r'].max():+.3f}")
    A(f"  median PF across grid: {grid['pf'].median():.2f} | median trades: {grid['trades'].median():.0f}")
    A(f"  CHAMPION percentile within the grid: {100*(grid['exp_r']<exp_r).mean():.1f}")
    A(f"  champion PF {pf:.2f} vs grid median PF {grid['pf'].median():.2f}")
    A("")
    A("  PRE-REGISTERED READINGS, verbatim:")
    A("    '~90%+ positive => window is tide'")
    A("    'mixed grid + champion top-decile => evidence of METHOD'")
    A("    'mixed grid + champion negative => config-specific failure'")
    A(f"  APPLIES: the first. {100*(grid['exp_r']>0).mean():.1f}% of the grid is positive, so this window is")
    A("  TIDE. The grid is not mixed, so the second and third readings do not apply —")
    A("  but note the champion also sits in the BOTTOM decile of that tide (6th pct).")
    A("")
    A("  mean exp_r by exit variant (descriptive only, NOT selection):")
    A(fmt(grid.groupby("exit")["exp_r"].mean().round(3).to_frame("mean_exp_r"), idx=True))
    A("-" * 78)
    A("STAGE D — NULLS")
    A(f"  500x random-entry null, in-window, same universe / trade count / hold-duration")
    A(f"  distribution, entries on non-candidate days:")
    A(f"    null mean {nul.mean():+.4f} R  | sd {nul.std():.4f} | p95 {np.quantile(nul,.95):+.4f} "
      f"| max {nul.max():+.4f}")
    A(f"    champion  {exp_r:+.4f} R  ->  percentile {100*(nul<exp_r).mean():.1f}, p = {pval:.4f}")
    A("")
    A("  *** THE REGIME METER: the null's own mean is " + f"{nul.mean():+.3f} R. ***")
    A("  Random entries in this window earned more than TEN TIMES the champion's")
    A("  expectancy. The window is Apr-2019 -> Jul-2021: the COVID crash and the")
    A("  recovery rally. Nearly any long exposure worked; the C-gate + trend template")
    A("  + RS>=90 filtering did not merely fail to add value, it subtracted it.")
    A("")
    A(f"  10,000x MC resample of the champion's own trades (drawdown in R):")
    A(f"    median {np.median(mc):.2f}R | 5th pct {np.quantile(mc,.05):.2f}R | worst {mc.min():.2f}R")
    A("")
    A("-" * 78)
    A("STAGE E — THE FIVE REGISTERED GATES (mechanical)")
    A("")
    for name, (ok, val) in gates.items():
        A(f"    [{'PASS' if ok else 'FAIL'}]  {name:<34} (actual {val})")
    if len(led) < 60:
        A("")
        A(f"    *** UNDERPOWERED: {len(led)} trades against a registered minimum of 60. ***")
        A("    The gate is NOT lowered. A 31-trade sample cannot carry a strong")
        A("    conclusion in either direction, and that is itself part of the result.")
    A("")
    A(f"    OVERALL: {'PASS' if all(o for o, _ in gates.values()) else 'FAIL'}  "
      f"({sum(o for o, _ in gates.values())}/5 gates passed)")
    A("")
    A("-" * 78)
    A("STAGE F — CORP-ACTION CHECK ON TOUCH (NSE, 1 req/s)")
    A(f"  symbols in the champion's ledger: {led['symbol'].nunique()} | all fetched, 0 parked")
    A(f"  split/bonus/demerger ex-dates INSIDE a held window: {len(hits)}")
    A("  No recompute required — nothing to exclude.")
    A("")
    A("-" * 78)
    A("STAGE G — SLIPPAGE SENSITIVITY")
    A(fmt(sens.round({"exp_r": 4, "expectancy_rs": 0, "pf": 3, "win": 1,
                      "maxdd": 4, "net": 0, "cagr": 4})))
    A("  The result is slippage-insensitive; it is not a cost artefact.")
    A("")
    A("-" * 78)
    A("DISCLOSURES — residual skew, never averaged away")
    A("")
    A("  Champion trades by sector bucket:")
    A(fmt(sect, idx=True))
    A("  Universe composition (164 effective): other 127 | NBFC 20 | bank 17.")
    A("  The champion traded 27 'other', 3 NBFC, 1 bank. The financials it did touch")
    A("  lost on every trade (4 trades, 0% win, -36,267 Rs combined) — a small sample,")
    A("  but it means the +67,739 Rs from 'other' names carries the entire result.")
    A("")
    A("  M6b eligibility echo (why the window starts at Apr-2019 and not Jan-2018):")
    A(fmt(cov[["quarter", "pct", "SKEW", "bank_pct", "NBFC_pct", "other_pct"]]))
    A("  The amended window begins exactly where coverage clears 60%. The 2018-Q1 ..")
    A("  2019-Q1 quarters at 9-15% (bank-only) are excluded by construction, which is")
    A("  why no result above is pooled across that boundary.")
    A("")
    A("=" * 78)
    A("VERDICT")
    A("=" * 78)
    A("")
    A("  The strategy FAILED its Round-2 sealed test, finishing at the 1st percentile of")
    A("  a random-entry null whose own mean was ten times its expectancy.")
    A("")
    A("  REGISTERED WEIGHT: a 2.3-year window carrying 31 trades is ADDITIONAL")
    A("  EVIDENCE — ek aur gawah — not a final adjudication, and that was fixed in")
    A("  advance rather than chosen after seeing the numbers. This witness says what")
    A("  Round-1's said: 99% of the 2,268-config grid was profitable here, so the")
    A("  window is tide, not skill; the champion cleared neither the tide nor the null;")
    A("  and the trade count is below the registered 60, so the finding is underpowered")
    A("  in the direction of caution. Two independent windows have now returned the")
    A("  same shape of answer — the build-half edge was regime, and out of sample the")
    A("  method has not beaten doing something arbitrary in the same names. That is a")
    A("  consistent pair of negative witnesses, not a proof; what would change the")
    A("  picture is a window where the grid is genuinely mixed, because only there can")
    A("  a champion's rank carry information about method rather than about the market.")
    A("")
    A("=" * 78)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(L) + "\n")
    print(f"REPORT: {REPORT}")


if __name__ == "__main__":
    main()
