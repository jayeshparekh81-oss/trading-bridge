"""BAR-QUALITY DIAGNOSTICS (P8, 2026-07-21) — descriptive stats ONLY, folded ADDITIVELY
into the pre-registered bar-representation study (TAPE_NOTES:1099, b2fc49a). That study's
pre-registered criteria text is UNTOUCHED — these numbers feed it, they judge nothing.

Session regime REUSES existing config anchors (no new regime invented):
  OPEN  = first `initial_balance_minutes` of the session (R4's IB window,
          levels/config.py:30 — 60 min)
  CLOSE = at/after `gates.session_cutoff` (signals/config.py:63 — "14:45" IST)
  MID   = between.

Per day/instrument/bar-stream: flat-bar rate (zero-range %), duration quantiles
Q10/Q50/Q90 + Q90/Q10 ratio split by regime, range-per-bar and volume-per-bar
median+IQR, ticks(trades)-per-bar consistency. DEFAULT OFF — opt-in CLI writing NEW
analysis/<day>/bar_quality_<sym>.json files + a cross-day summary; nothing existing
changes; R2 hash untouched.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Sequence

NS = 1_000_000_000
IST = timezone(timedelta(hours=5, minutes=30))
MIN_BARS = 5                        # below this: honest note, no quantile claims


def _q(xs: Sequence[float], p: float) -> float:
    s = sorted(xs)
    return s[max(0, min(len(s) - 1, int(p * (len(s) - 1))))]


def _dist(xs: Sequence[float]) -> dict:
    return {"median": round(_q(xs, 0.5), 4), "iqr": round(_q(xs, 0.75) - _q(xs, 0.25), 4)}


def regime_of(ts_ns: int, session_start_ns: int, ib_minutes: float, cutoff_hhmm: str) -> str:
    if ts_ns < session_start_ns + int(ib_minutes * 60 * NS):
        return "open"
    hh, mm = (int(x) for x in cutoff_hhmm.split(":"))
    t = datetime.fromtimestamp(ts_ns / NS, IST)
    return "close" if (t.hour, t.minute) >= (hh, mm) else "mid"


def bar_quality(bars: Sequence[dict], *, session_start_ns: Optional[int] = None,
                ib_minutes: float = 60.0, cutoff_hhmm: str = "14:45") -> dict:
    """Descriptive quality stats for one bar stream (dicts with start/end_ts_ns,
    duration_s, open/high/low/close, volume, trade_count)."""
    n = len(bars)
    if n == 0:
        return {"n_bars": 0, "note": "EMPTY bar stream — no stats"}
    s0 = session_start_ns if session_start_ns is not None else bars[0]["start_ts_ns"]
    out: dict = {"n_bars": n,
                 "flat_bar_rate": round(sum(1 for b in bars if b["high"] == b["low"]) / n, 4)}
    if n < MIN_BARS:
        out["note"] = f"SHORT stream (n={n} < {MIN_BARS}) — quantiles omitted"
        return out
    durs = [float(b["duration_s"]) for b in bars]
    out["duration_s"] = {"q10": round(_q(durs, 0.10), 2), "q50": round(_q(durs, 0.50), 2),
                         "q90": round(_q(durs, 0.90), 2),
                         "q90_q10_ratio": round(_q(durs, 0.90) / max(_q(durs, 0.10), 1e-9), 2)}
    by_reg: dict[str, list[float]] = {"open": [], "mid": [], "close": []}
    for b in bars:
        by_reg[regime_of(b["end_ts_ns"], s0, ib_minutes, cutoff_hhmm)].append(float(b["duration_s"]))
    out["duration_by_regime"] = {
        reg: ({"n": len(v), "q10": round(_q(v, 0.10), 2), "q50": round(_q(v, 0.50), 2),
               "q90": round(_q(v, 0.90), 2),
               "q90_q10_ratio": round(_q(v, 0.90) / max(_q(v, 0.10), 1e-9), 2)}
              if len(v) >= MIN_BARS else {"n": len(v), "note": "too few bars"})
        for reg, v in by_reg.items()}
    out["range_pts"] = _dist([b["high"] - b["low"] for b in bars])
    out["volume"] = _dist([float(b["volume"]) for b in bars])
    out["trades_per_bar"] = _dist([float(b["trade_count"]) for b in bars])
    return out


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="research.bar_quality")
    ap.add_argument("--date")
    ap.add_argument("--instruments", default="NIFTY_FUT,BANKNIFTY_FUT")
    ap.add_argument("--summary", action="store_true", help="cross-day summary table")
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv[1:])
    root = Path(args.root)
    if args.summary:
        rows = []
        for f in sorted((root / "analysis").glob("*/bar_quality_*.json")):
            d = json.loads(f.read_text())
            q = d["quality"]
            if q.get("n_bars", 0) >= MIN_BARS:
                rows.append((d["day"], d["symbol"], q["n_bars"], q["flat_bar_rate"],
                             q["duration_s"]["q50"], q["duration_s"]["q90_q10_ratio"],
                             q["range_pts"]["median"], q["volume"]["median"],
                             q["trades_per_bar"]["median"]))
            else:
                rows.append((d["day"], d["symbol"], q.get("n_bars", 0), None, None, None, None, None, None))
        print(f"{'day':11s}{'sym':15s}{'bars':>5s}{'flat%':>7s}{'durQ50':>8s}{'Q90/10':>7s}"
              f"{'rngMed':>8s}{'volMed':>8s}{'trdMed':>7s}")
        for r in rows:
            print(f"{r[0]:11s}{r[1]:15s}{r[2]:5d}" + "".join(
                f"{(v if v is not None else '—'):>7}" if i == 0 else f"{(v if v is not None else '—'):>8}"
                for i, v in [(0, r[3]), (1, r[4]), (0, r[5]), (1, r[6]), (1, r[7]), (0, r[8])]))
        (root / "analysis" / "bar_quality_summary.json").write_text(json.dumps(
            {"columns": ["day", "symbol", "n_bars", "flat_rate", "dur_q50",
                         "dur_q90_q10", "range_med", "vol_med", "trades_med"],
             "rows": rows}, indent=1))
        print(f"-> {root/'analysis'/'bar_quality_summary.json'}")
        return 0
    if not args.date:
        ap.error("--date required (or --summary)")
    from replayer.engine import ReplayEngine
    from replayer.source import ReplaySource
    from tape.config import load_tape_config
    from tape.engine import TapeEngine
    from levels.config import load_levels_config
    from signals.config import load_signal_config
    from signals.pipeline import build_meta
    dd = root / "data" / args.date
    meta = build_meta(dd)
    tape = TapeEngine(load_tape_config(), {s: m["symbol"] for s, m in meta.items()})
    insts = [s.strip() for s in args.instruments.split(",") if s.strip()]
    ReplayEngine(ReplaySource(dd, instruments=insts)).drive(tape, speed="max")
    ib = load_levels_config().initial_balance_minutes
    cutoff = str(load_signal_config().gates["session_cutoff"])
    by_sym: dict[str, list[dict]] = {}
    for b in tape.bar_rows:
        if b["bar_type"] == "tick":
            by_sym.setdefault(b["symbol"], []).append(b)
    for s, bars in sorted(by_sym.items()):
        bars.sort(key=lambda b: b["end_ts_ns"])
        q = bar_quality(bars, ib_minutes=ib, cutoff_hhmm=cutoff)
        out = root / "analysis" / args.date / f"bar_quality_{s}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"day": args.date, "symbol": s,
                                   "regime_anchors": {"ib_minutes": ib, "cutoff": cutoff},
                                   "quality": q}))
        print(f"{s}: n={q['n_bars']} flat={q.get('flat_bar_rate')} -> {out}")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
