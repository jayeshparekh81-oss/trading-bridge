"""Stop-probe-depth measurement (research, read-only).

Founder's question (2026-07-16): institutional practice says place the stop BEYOND the
level, not ON it, because liquidity probes sweep the level before reversing. Our thesis
buffer is 0.10pt (2 ticks) — effectively ON the level. "Beyond by how much?" is a number
only our data can give.

For each key level in the registry ladder, when price TOUCHES the level and then REVERSES
(a PROBE — the level holds) vs CONTINUES (a BREAK), measure how far PAST the level the wick
reaches before the reversal. That excursion IS the empirical stop-hunt depth: a stop inside
it gets swept; a stop beyond it survives.

Method (forward window K bars, no future used to pick levels or bias the sample):
  * fresh touch from BELOW  = prev bar wholly under L, this bar's high >= L (L as resistance)
  * fresh touch from ABOVE  = prev bar wholly over  L, this bar's low  <= L (L as support)
  * PROBE  = within K bars a bar CLOSES back on the origin side (level held). depth = the
             deepest excursion past L reached up to that reversal.
  * BREAK  = within K bars price never closes back (level gave way).
A probe depth is inherently known only AFTER the reversal (retrospective measurement); the
no-look-ahead discipline is that the DERIVED buffer is a FIXED constant applied prospectively,
not a per-trade peek. N=2 days is a first look + tool, NEVER a conclusion — the 15-day set
decides. Read-only: consumes analysis/<date>/<sym>_<sid>.bars.parquet + levels_<sym>_<sid>.parquet.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

FUTS = [("NIFTY_FUT", 61093), ("BANKNIFTY_FUT", 61088)]
BUF_FRACTIONS = [0.1, 0.25, 0.5]          # ATR fractions to evaluate as buffer candidates
CURRENT_BUFFER_PTS = 0.10                  # thesis_stop_buffer_ticks 2 * tick_size 0.05
MIN_STOP_ATR, MIN_STOP_PCT = 0.3, 0.03     # the shipped R-stability floor (for the cost calc)


def load_bars(path: Path) -> list[tuple[float, float, float]]:
    t = pq.read_table(str(path)).to_pydict()
    return list(zip(t["high"], t["low"], t["close"]))


def load_levels(path: Path) -> list[float]:
    # unique prices, deduped to 1pt (PDL/PWL etc. coincide)
    prices = sorted(set(pq.read_table(str(path)).to_pydict()["price"]))
    out: list[float] = []
    for p in prices:
        if not out or p - out[-1] > 1.0:
            out.append(p)
    return out


def day_atr(bars: list[tuple[float, float, float]]) -> float:
    """Mean per-bar True Range over the day (a stable per-instrument ATR)."""
    trs = []
    pc = None
    for h, l, c in bars:
        trs.append(h - l if pc is None else max(h - l, abs(h - pc), abs(l - pc)))
        pc = c
    return sum(trs) / len(trs) if trs else 0.0


def probes_for_level(bars, L: float, k: int) -> list[tuple[float, str]]:
    """(depth, 'probe'|'break') for each fresh touch of level ``L``."""
    out = []
    n = len(bars)
    i = 1
    while i < n:
        h, l, c = bars[i]
        ph, pl, pc = bars[i - 1]
        if pc < L and ph < L and h >= L:
            side = "below"
        elif pc > L and pl > L and l <= L:
            side = "above"
        else:
            i += 1
            continue
        peak = (h - L) if side == "below" else (L - l)
        outcome, j = "break", i
        end = min(n - 1, i + k)
        while j <= end:
            hh, ll, cc = bars[j]
            exc = (hh - L) if side == "below" else (L - ll)
            peak = max(peak, exc)                              # deepest excursion so far
            back = (cc < L) if side == "below" else (cc > L)
            if back:                                          # closed back on origin side
                outcome = "probe"
                break
            j += 1
        out.append((round(peak, 2), outcome))                 # depth = peak excursion past L
        i = (j + 1) if outcome == "probe" else (end + 1)      # skip the resolved episode
    return out


def _pctl(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


def measure(bars, levels, atr: float, k: int) -> dict:
    events = [e for L in levels for e in probes_for_level(bars, L, k)]
    probes = [d for d, o in events if o == "probe"]
    breaks = sum(1 for _, o in events if o == "break")
    n = len(events)
    depths = {q: _pctl(probes, p) for q, p in [("med", .5), ("p75", .75), ("p90", .9)]}
    return {
        "touches": n, "n_probes": len(probes), "n_breaks": breaks,
        "break_rate": round(breaks / n, 3) if n else None,
        "atr": round(atr, 2),
        "probe_depth_pts": {**{q: round(v, 2) for q, v in depths.items()},
                            "max": round(max(probes), 2) if probes else 0.0},
        "probe_depth_atr": {q: round(v / atr, 3) if atr else None for q, v in depths.items()},
    }


def stop_R_median(bars, levels, buffer_pts: float) -> tuple[float, float]:
    """Median long-stop distance (R, in pts and %) at a given buffer, WITH the shipped floor."""
    Rs, pcts = [], []
    for h, l, c in bars:
        below = [p for p in levels if p < c]
        if not below:
            continue
        struct = c - (max(below) - buffer_pts)                 # (c-level) + buffer
        floor = max(MIN_STOP_ATR * day_atr(bars), MIN_STOP_PCT / 100.0 * c)
        R = max(struct, floor)
        Rs.append(R)
        pcts.append(100.0 * R / c)
    return (round(_pctl(Rs, .5), 2), round(_pctl(pcts, .5), 3)) if Rs else (0.0, 0.0)


def analyze(date: str, sym: str, sid: int, root: Path, k: int) -> dict:
    a = root / "analysis" / date
    bp, lp = a / f"{sym}_{sid}.bars.parquet", a / f"levels_{sym}_{sid}.parquet"
    if not bp.exists() or not lp.exists():
        return {"date": date, "sym": sym, "usable": False,
                "skip_reason": f"missing bars/levels in analysis/{date}"}
    bars, levels = load_bars(bp), load_levels(lp)
    atr = day_atr(bars)
    m = measure(bars, levels, atr, k)
    # buffer candidates: ATR fractions, do they clear p75 / p90 probe depth?
    p75, p90 = m["probe_depth_pts"]["p75"], m["probe_depth_pts"]["p90"]
    cands = []
    for f in BUF_FRACTIONS:
        buf = f * atr
        cur_med, cur_pct = stop_R_median(bars, levels, CURRENT_BUFFER_PTS)
        new_med, new_pct = stop_R_median(bars, levels, buf)
        cands.append({"frac": f, "buffer_pts": round(buf, 2),
                      "clears_p75": buf >= p75, "clears_p90": buf >= p90,
                      "median_R_pts": new_med, "median_R_pct": new_pct,
                      "median_R_pts_now": cur_med})
    return {"date": date, "sym": sym, "usable": True, "n_bars": len(bars),
            "n_levels": len(levels), **m, "candidates": cands}


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dates", default="2026-07-15,2026-07-16")
    ap.add_argument("--k", type=int, default=5, help="forward window in bars")
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv[1:])
    root = Path(args.root)
    print(f"STOP-PROBE-DEPTH — forward window K={args.k} bars, dates {args.dates}")
    print("=" * 74)
    for sym, sid in FUTS:
        print(f"\n### {sym}")
        for date in args.dates.split(","):
            r = analyze(date, sym, sid, root, args.k)
            if not r["usable"]:
                print(f"  {date}: SKIP — {r['skip_reason']}")
                continue
            print(f"  {date}: {r['touches']} touches ({r['n_probes']} probes / "
                  f"{r['n_breaks']} breaks, break_rate={r['break_rate']}), ATR~{r['atr']}pt")
            dp, da = r["probe_depth_pts"], r["probe_depth_atr"]
            print(f"     probe depth  pts: med={dp['med']} p75={dp['p75']} p90={dp['p90']} max={dp['max']}")
            print(f"     probe depth  ATR: med={da['med']} p75={da['p75']} p90={da['p90']}")
            print(f"     buffer candidates (current buffer {CURRENT_BUFFER_PTS}pt -> "
                  f"median R now {r['candidates'][0]['median_R_pts_now']}pt):")
            for c in r["candidates"]:
                print(f"       {c['frac']:>4}xATR = {c['buffer_pts']:6.2f}pt  "
                      f"clears p75={str(c['clears_p75']):5s} p90={str(c['clears_p90']):5s}  "
                      f"-> median R {c['median_R_pts']:6.2f}pt ({c['median_R_pct']}%)")
    print("\n" + "=" * 74)
    print("N=2 days — HYPOTHESIS-FROM-2-DAYS, NOT a conclusion. The 15-day set decides.")
    print("Levels = EOD ladder proxy (intraday registry moves); shape, not exact per-bar.")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
