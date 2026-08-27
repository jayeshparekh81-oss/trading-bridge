#!/usr/bin/env python3
"""Module-0 · feature layer for the NSE delivery study.

Consumes data/nse_delivery.parquet (from fetch_nse_delivery.py) and builds, per
symbol:

  adj_close      — corporate-action-adjusted close. sec_bhavdata_full's
                   PREV_CLOSE is the RAW prior close (an un-adjusted split fakes a
                   ~-90% return), so we detect the ex-date price gap and
                   back-adjust prior bars by the CLEAN round split/bonus ratio;
                   ambiguous large gaps (news) are left unadjusted and surface in
                   the ±20% eyeball flag. An unadjusted bonus gap would otherwise
                   fake a huge return.
  ret_1d         — that adjusted daily return (diagnostic; flagged if |ret|>20%).
  fwd_ret_1d     — forward 1-day adjusted return  (t → t+1).
  fwd_ret_5d     — forward 5-day adjusted return  (t → t+5).
  deliv_pct_60   — SELF-CALIBRATING spike metric: percentile-rank of today's
                   DELIV_PER within its own trailing 60-trading-day window
                   (today included). Relative to each stock's own norm, not a
                   fixed magic number. Needs a full 60-obs window → NaN before.
  spike          — deliv_pct_60 >= 0.90 (top decile vs the stock's own history).

NO-LOOK-AHEAD: the spike flag and percentile use only DELIV_PER up to and
including day t; forward returns look strictly at t+1..t+N. The two never share
information.

Library (importable) + runnable (writes data/delivery_feature.parquet and
prints the corp-action / extreme-move eyeball log).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

DELIV_WINDOW = 60        # trailing trading days for the self-calibrating percentile
SPIKE_PCT = 0.90         # top-decile of a stock's own recent DELIV_PER
EXTREME_RET = 0.20       # |adjusted daily return| beyond this ⇒ flag for eyeball

# Corporate-action back-adjustment. sec_bhavdata_full's PREV_CLOSE is the RAW
# prior close (verified: NESTLEIND 1:10 split ex-date shows prev_close=27116 but
# open=2754), so an un-adjusted split fakes a ~-90% return. We detect the ex-date
# price gap (open[t] already trades on the post-event basis) and back-adjust ONLY
# when the gap matches a clean round split/bonus ratio; ambiguous large gaps
# (news) are left alone and surface in the ±20% eyeball flag. Mirrors the proven
# fetch_dhan_equity.detect_and_adjust classifier.
GAP_DETECT = 0.20        # |open[t]/close[t-1] - 1| beyond this ⇒ candidate corp action
RATIO_TOL = 0.05         # relative tolerance to call a gap a clean round ratio
CANDIDATE_RATIOS = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 7.0, 10.0, 11.0]  # + inverses


def _classify_ratio(ratio: float) -> tuple[bool, float]:
    """Is `ratio` (close[t-1]/open[t]) a clean round split/bonus ratio (e.g. 2.0
    for a 1:1 bonus, 10.0 for a 1:10 split)? Checks the ratio and its inverse."""
    for c in CANDIDATE_RATIOS:
        if abs(ratio / c - 1.0) <= RATIO_TOL:
            return True, c
        if abs((1.0 / ratio) / c - 1.0) <= RATIO_TOL:
            return True, 1.0 / c
    return False, ratio


def _trailing_pctile_incl(s: pd.Series, window: int) -> pd.Series:
    """Percentile-rank of today's value within its own trailing `window` (today
    included), using the MID-RANK (a.k.a. 'mean') convention:

        pct = ( #strictly-less-than-today + 0.5 * #equal-to-today ) / window

    Ties are split, so a perfectly FLAT series sits at 0.5 (its own median), not
    1.0 — the naive `mean(w <= today)` would call every day of a flat, low-
    variance delivery stock a top-percentile 'spike'. Requires a full window
    (else NaN) so early bars can't spike on a thin sample. Matches
    scipy.stats.percentileofscore(kind='mean')/100.
    """
    def _rank(w: np.ndarray) -> float:
        today = w[-1]
        return float((np.sum(w < today) + 0.5 * np.sum(w == today)) / w.size)
    return s.rolling(window, min_periods=window).apply(_rank, raw=True)


def build_symbol(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Feature-ise one symbol's daily rows (must be date-sorted). Returns the
    enriched frame and a list of corp-action events detected for eyeballing."""
    df = df.sort_values("date").reset_index(drop=True)

    # ── Corp-action-adjusted close via ex-date price-gap back-adjustment ─────
    # For each day: gap = open[t]/close[t-1]. A split/bonus gaps beyond GAP_DETECT
    # AND lands on a clean round ratio → back-adjust every PRIOR bar ×gap so the
    # series is continuous at today's (post-event) scale; events compound in time
    # order. Ambiguous large gaps are recorded but NOT adjusted (→ ±20% flag).
    close = df["close"].to_numpy(dtype=float)
    openp = df["open"].to_numpy(dtype=float)
    n = len(df)
    corp_events: list[dict] = []
    for t in range(1, n):
        c_prev, o = close[t - 1], openp[t]
        if not (np.isfinite(c_prev) and np.isfinite(o)) or c_prev <= 0 or o <= 0:
            continue
        gap = o / c_prev
        if abs(gap - 1.0) <= GAP_DETECT:
            continue
        clean, inferred = _classify_ratio(c_prev / o)
        corp_events.append({
            "t": t, "symbol": df["symbol"].iloc[t], "date": df["date"].iloc[t].date(),
            "gap_pct": (gap - 1.0) * 100.0, "factor": gap,
            "inferred_ratio": inferred, "clean": clean,
        })
    adj = close.copy()
    for ev in corp_events:  # chronological → compounding is correct
        if ev["clean"]:
            adj[: ev["t"]] *= ev["factor"]
    df["adj_close"] = adj

    df["ret_1d"] = df["adj_close"].pct_change()
    df["fwd_ret_1d"] = df["adj_close"].shift(-1) / df["adj_close"] - 1.0
    df["fwd_ret_5d"] = df["adj_close"].shift(-5) / df["adj_close"] - 1.0

    # ── Self-calibrating delivery-% spike ───────────────────────────────────
    df["deliv_pct_60"] = _trailing_pctile_incl(df["deliv_per"], DELIV_WINDOW)
    # Nullable boolean: undefined (NaN percentile → warm-up window, or a '-'
    # delivery day) must stay NA, NOT collapse to False. A False here would
    # silently seed the non-spike baseline with every symbol's first 59 days.
    valid = df["deliv_pct_60"].notna()
    spike = pd.array([pd.NA] * len(df), dtype="boolean")
    spike[valid.to_numpy()] = (df.loc[valid, "deliv_pct_60"] >= SPIKE_PCT).to_numpy()
    df["spike"] = spike

    # ── Corp-action + extreme-move eyeball log ──────────────────────────────
    events: list[dict] = []
    for ev in corp_events:
        kind = "corp_action(adjusted)" if ev["clean"] else "corp_action(AMBIGUOUS,not-adjusted)"
        events.append({
            "symbol": ev["symbol"], "date": ev["date"], "kind": kind,
            "detail": f"open-gap {ev['gap_pct']:+.1f}%  ratio≈{ev['inferred_ratio']:.3f}"
                      + ("  → back-adjusted" if ev["clean"] else "  → FLAGGED only (news?)"),
        })
    for t in range(len(df)):
        r = df["ret_1d"].iloc[t]
        if pd.notna(r) and abs(r) > EXTREME_RET:
            events.append({
                "symbol": df["symbol"].iloc[t],
                "date": df["date"].iloc[t].date(),
                "kind": "extreme_ret>20%",
                "detail": f"post-adjustment ret_1d {r * 100:+.1f}%",
            })
    return df, events


def build(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    out, all_events = [], []
    for _sym, g in df.groupby("symbol", sort=True):
        fe, ev = build_symbol(g)
        out.append(fe)
        all_events.extend(ev)
    feat = pd.concat(out, ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)
    return feat, all_events


def main(argv: list[str] | None = None) -> int:
    src = DATA_DIR / "nse_delivery.parquet"
    if not src.exists():
        print(f"ERROR: {src} not found — run fetch_nse_delivery.py first.", file=sys.stderr)
        return 2
    raw = pd.read_parquet(src)
    feat, events = build(raw)

    out_pq = DATA_DIR / "delivery_feature.parquet"
    feat.to_parquet(out_pq, index=False)
    print(f"[feature] wrote {out_pq}  ({len(feat):,} rows, {feat['symbol'].nunique()} symbols)")

    corp = [e for e in events if e["kind"].startswith("corp_action")]
    extreme = [e for e in events if e["kind"].startswith("extreme")]
    n_adj = sum(1 for e in corp if e["kind"] == "corp_action(adjusted)")
    print(f"\n──── CORP-ACTION SCAN (ex-date open-gap > {GAP_DETECT:.0%}) ────")
    print(f"  {len(corp)} candidate events: {n_adj} clean split/bonus back-adjusted, "
          f"{len(corp) - n_adj} ambiguous flagged-only:")
    for e in sorted(corp, key=lambda x: (x["symbol"], x["date"])):
        print(f"   {e['symbol']:<12} {e['date']}  {e['detail']}")

    print(f"\n──── EXTREME MOVES AFTER ADJUSTMENT (|ret_1d| > {EXTREME_RET:.0%}) — eyeball for missed corp actions ────")
    if not extreme:
        print("  none — no adjusted daily return beyond ±20%.")
    for e in sorted(extreme, key=lambda x: (x["symbol"], x["date"])):
        print(f"   {e['symbol']:<12} {e['date']}  {e['detail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
