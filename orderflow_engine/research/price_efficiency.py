"""PRICE EFFICIENCY (P5, 2026-07-21) — ticks moved PER UNIT OF AGGRESSIVE VOLUME.

  UpsideEff_i   = up_ticks_i   / max(aggressive_buy_qty_i,  eps)
  DownsideEff_i = down_ticks_i / max(aggressive_sell_qty_i, eps)

with up_ticks = max(close−open, 0)/tick_size and down_ticks = max(open−close, 0)/tick_size
per tick-bar, and buy/sell qty = the R3 Lee-Ready aggressor-classified volumes
(tape/bars.py:37-38, emitted tape/engine.py:171). Rolling-W (default 10) variants use
Σticks / Σqty over the TRAILING window — strictly causal, bar i uses bars ≤ i only.

HOW THIS DIFFERS FROM KAUFMAN ER (tested 2026-07-19, ρ≈0.04–0.07 vs outcomes, inverted,
REJECTED as a gate): ER = |net move| / Σ|bar moves| is PRICE-ONLY — price path in both
numerator and denominator; it measures how straight the path was. Price efficiency puts
VOLUME in the denominator: it measures how much price a unit of aggression BOUGHT —
LOW UpsideEff on heavy buying = passive sellers absorbing (the P7/LAR absorption
signature); high = a thin book giving way. Different numerator (directional ticks, not
net), different denominator (aggressor qty, not path) — mathematically distinct objects.

STATUS: research-lane feature, DEFAULT OFF — computed only by this module/CLI, written to
NEW output files only; nothing in the tape/signals pipeline reads it; R2 hash untouched.
Per the P5 precheck it is carried as an input candidate for the absorption/LAR work and a
15-day-set feature candidate — NOT a live component, NOT a gate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Sequence

DEFAULT_TICK = 0.05        # NIFTY/BANKNIFTY futures tick (signals config exits.tick_size)
DEFAULT_EPS = 1.0          # qty floor: zero aggressive volume -> efficiency 0, never div/0
DEFAULT_WINDOW = 10


def bar_efficiency(bar: dict, *, tick: float = DEFAULT_TICK,
                   eps: float = DEFAULT_EPS) -> tuple[float, float]:
    """(UpsideEff, DownsideEff) for ONE bar dict carrying open/close/buy_vol/sell_vol."""
    up = max(float(bar["close"]) - float(bar["open"]), 0.0) / tick
    dn = max(float(bar["open"]) - float(bar["close"]), 0.0) / tick
    return up / max(float(bar["buy_vol"]), eps), dn / max(float(bar["sell_vol"]), eps)


def rolling_efficiency(bars: Sequence[dict], *, window: int = DEFAULT_WINDOW,
                       tick: float = DEFAULT_TICK, eps: float = DEFAULT_EPS) -> list[dict]:
    """CAUSAL per-bar rows: per-bar and rolling-``window`` up/down efficiency.
    Row i is computed from bars[max(0,i-window+1) .. i] ONLY (no look-ahead — leak-tested).
    Returns one dict per input bar: {up, dn, up_w, dn_w, n_in_window}."""
    out: list[dict] = []
    for i in range(len(bars)):
        u1, d1 = bar_efficiency(bars[i], tick=tick, eps=eps)
        j0 = max(0, i - window + 1)
        su = sd = bu = se = 0.0
        for k in range(j0, i + 1):
            b = bars[k]
            su += max(float(b["close"]) - float(b["open"]), 0.0) / tick
            sd += max(float(b["open"]) - float(b["close"]), 0.0) / tick
            bu += float(b["buy_vol"])
            se += float(b["sell_vol"])
        out.append({"up": round(u1, 6), "dn": round(d1, 6),
                    "up_w": round(su / max(bu, eps), 6),
                    "dn_w": round(sd / max(se, eps), 6),
                    "n_in_window": i - j0 + 1})
    return out


def write_day(analysis_root: str | Path, day: str, symbol: str, bars: Sequence[dict], *,
              window: int = DEFAULT_WINDOW, tick: float = DEFAULT_TICK,
              eps: float = DEFAULT_EPS) -> Path:
    """Write the day's efficiency rows to a NEW json file (never touches existing files)."""
    rows = rolling_efficiency(bars, window=window, tick=tick, eps=eps)
    out = Path(analysis_root) / day / f"price_efficiency_{symbol}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"day": day, "symbol": symbol, "window": window,
                               "tick": tick, "eps": eps, "rows": rows}, indent=None))
    return out


def main(argv: list[str]) -> int:
    """CLI (opt-in only — the feature is OFF unless this is invoked explicitly):
    replay a recorded day's tick bars and write price_efficiency_<sym>.json per
    instrument into analysis/<day>/ (NEW files only)."""
    import argparse
    ap = argparse.ArgumentParser(prog="research.price_efficiency")
    ap.add_argument("--date", required=True)
    ap.add_argument("--instruments", default="NIFTY_FUT,BANKNIFTY_FUT")
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW)
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv[1:])
    from replayer.engine import ReplayEngine
    from replayer.source import ReplaySource
    from tape.config import load_tape_config
    from tape.engine import TapeEngine
    from signals.pipeline import build_meta
    dd = Path(args.root) / "data" / args.date
    meta = build_meta(dd)
    tape = TapeEngine(load_tape_config(), {s: m["symbol"] for s, m in meta.items()})
    insts = [s.strip() for s in args.instruments.split(",") if s.strip()]
    ReplayEngine(ReplaySource(dd, instruments=insts)).drive(tape, speed="max")
    by_sym: dict[str, list[dict]] = {}
    for b in tape.bar_rows:
        if b["bar_type"] == "tick":
            by_sym.setdefault(b["symbol"], []).append(b)
    for sym, bars in sorted(by_sym.items()):
        bars.sort(key=lambda b: b["end_ts_ns"])
        p = write_day(Path(args.root) / "analysis", args.date, sym, bars, window=args.window)
        print(f"{sym}: {len(bars)} bars -> {p}")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
