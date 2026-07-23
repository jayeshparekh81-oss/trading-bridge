"""BAR-SIZE SWEEP (2026-07-23) — IN-SAMPLE EXPLORATION — NOT A REGISTERED RESULT.

Multi-size capture + per-fire persistence + sequential de-dup + resumable batch driver for
the burned-days bar-size sweep (menu {100..1000 step 100}; 100 = the cached baseline, never
re-run here). Research lane only: burned days (<= 2026-07-21), per-run scratch yaml for the
tick_bar_size override, committed config untouched, no live/window access.

Pieces:
  * capture_day_multi(day, sizes, ...) — ONE replay pass feeding N tapes + N SignalEngines;
    levels/chain are SHARED (SignalEngine only reads them). Chain replay cost paid once.
  * per-fire records {entry_ns, exit_ns, gross, net, cost_r} per size/day/instrument.
  * dedup_sequential(fires) — one-position no-cap view: sort by entry_ns, keep a fire iff
    its entry_ns >= the previously kept fire's exit_ns (per instrument per day).
  * batch driver — resumable state per (day, size); every completed unit writes its JSON
    immediately; HARD STOP: no unit STARTS after 08:30 IST and anything past 08:45 refuses.
  * verify_against_disk only at size 100 (the persisted signals.parquet universe); other
    sizes record {"checked": False, "reason": "non-baseline bar size"}.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Optional, Sequence

from research.delta_vwap_evaluator import (
    DayCapture, median_delta_al, price_candidate, rule_decisions,
)

IST = timezone(timedelta(hours=5, minutes=30))
HARD_STOP_START = time(8, 30)      # no unit STARTS at/after this (IST)
HARD_STOP_REFUSE = time(8, 45)     # absolutely nothing runs at/after this (IST)
MARKET_EVENING = time(16, 0)       # units may start from here (post-close) until HARD_STOP


# ============================ multi-size capture ==============================
def capture_day_multi(day: str, sizes: Sequence[int], *, root: str | Path = ".",
                      base_config_path: str | Path | None = None) -> dict[int, DayCapture]:
    """One full-day replay -> {size: DayCapture}. Levels + chain are built ONCE and shared;
    each size gets its own TapeEngine + SignalEngine (frozen signal config). The per-size
    instrumentation mirrors delta_vwap_evaluator.capture_day exactly (ctx cache + as-of cost
    inputs); the committed evaluator file is deliberately not modified."""
    import yaml
    from chain.config import load_chain_config
    from chain.engine import ChainEngine
    from chain.lotsize import load_lot_by_index
    from levels.config import load_levels_config
    from levels.engine import LevelsEngine
    from replayer.engine import ReplayEngine
    from replayer.source import ReplaySource
    from signals.config import load_signal_config
    from signals.engine import SignalEngine
    from signals.events import load_events
    from signals.pipeline import MultiConsumer, build_meta
    from tape.config import TapeConfig, load_tape_config

    dd = Path(root) / "data" / day
    sd = date.fromisoformat(day)
    meta = build_meta(dd)
    sym = {s: m["symbol"] for s, m in meta.items()}
    base_tc = load_tape_config(base_config_path)
    lv = LevelsEngine(load_levels_config(base_config_path), sym, date=day)
    cm = {s: m for s, m in meta.items() if m["kind"] in ("spot", "future", "option")}
    lot = load_lot_by_index(Path(root) / "cache" if (Path(root) / "cache").exists()
                            else Path("cache"), sd,
                            sorted({m["index"] for m in cm.values() if m.get("index")}))
    chain = ChainEngine(load_chain_config(base_config_path), cm, sd, lot_by_index=lot)

    consumers: list = [lv, chain]                 # shared, updated once per packet
    per_size: dict[int, dict] = {}
    for n in sizes:
        d = json.loads(json.dumps(base_tc.d))     # deep copy of the loaded tape config
        d.setdefault("bars", {})["tick_bar_size"] = int(n)
        tape = __import__("tape.engine", fromlist=["TapeEngine"]).TapeEngine(TapeConfig(d), sym)
        sig = SignalEngine(load_signal_config(base_config_path), tape, lv, chain, meta, sd,
                           events=load_events())
        ctxs: dict = {}
        costs: dict = {}
        orig_bc = sig._build_context
        def _bc(sid, bar, ts, _o=orig_bc, _c=ctxs):
            c = _o(sid, bar, ts)
            _c[(sid, c.ts_ns)] = c
            return c
        sig._build_context = _bc
        orig_ev = sig._evaluate
        def _ev(sid, bar, ts, _o=orig_ev, _c=ctxs, _k=costs, _s=sig):
            _o(sid, bar, ts)
            c = _c.get((sid, bar["end_ts_ns"]))
            if c is not None:
                for side in _s.sides:
                    _k[(sid, c.ts_ns, side)] = _s._capture_cost_inputs(c, side)
        sig._evaluate = _ev
        consumers += [tape, sig]
        per_size[int(n)] = {"tape": tape, "sig": sig, "ctxs": ctxs, "costs": costs}

    ReplayEngine(ReplaySource(dd)).drive(MultiConsumer(consumers), speed="max")

    out: dict[int, DayCapture] = {}
    sid_by = {m["symbol"]: s for s, m in meta.items()}
    for n, parts in per_size.items():
        tape, sig = parts["tape"], parts["sig"]
        sig.finalize()
        bars: dict = {}
        for b in tape.bar_rows:                   # CLOSED bars only (no tape.finalize) —
            if b["bar_type"] == "tick":           # live stepping never sees the partial
                bars.setdefault(b["security_id"], []).append(b)
        for arr in bars.values():
            arr.sort(key=lambda b: b["end_ts_ns"])
        cands = []
        for r in sig.rows:
            sid = sid_by.get(r["instrument"])
            c = parts["ctxs"].get((sid, r["ts_ns"]))
            sgn = 1 if r["side"] == "long" else -1
            cands.append({"ts_ns": r["ts_ns"], "sid": sid, "instrument": r["instrument"],
                          "side": r["side"], "fired": bool(r["fired"]), "score": r["score"],
                          "delta_al": (c.bar_delta * sgn) if c is not None else None,
                          "vwap_dist_al": ((c.price - c.vwap) * sgn)
                                          if (c is not None and c.vwap is not None) else None})
        out[n] = DayCapture(day=day, candidates=cands, ctx=parts["ctxs"], bars=bars,
                            cost_inputs=parts["costs"], sig_cfg=sig.cfg,
                            depth_ofi_enabled=tape.cfg.depth_ofi_enabled)
    return out


# ============================ per-fire records + de-dup =======================
def perfire_records(cap: DayCapture, instrument: str, dmed: Optional[float]) -> list[dict]:
    """Priced per-fire records for every rule-fire: {entry_ns, exit_ns, gross, net, cost_r}."""
    out = []
    for cand, fires in rule_decisions(cap, instrument, dmed):
        if not fires:
            continue
        rec = price_candidate(cap, cand)
        if rec is None:
            continue
        out.append({"entry_ns": rec["entry_ns"], "exit_ns": rec["exit_ns"],
                    "gross": rec["realized_r"], "net": rec["realized_r_net"],
                    "cost_r": rec["cost_r"]})
    return out


def dedup_sequential(fires: Sequence[dict]) -> list[dict]:
    """One-position no-cap view (per instrument per day): chronological by entry_ns, keep a
    fire iff its entry_ns >= the previously KEPT fire's exit_ns."""
    kept: list[dict] = []
    for f in sorted(fires, key=lambda x: x["entry_ns"]):
        if not kept or f["entry_ns"] >= kept[-1]["exit_ns"]:
            kept.append(f)
    return kept


def _sums(fires: Sequence[dict]) -> dict:
    g = [f["gross"] for f in fires if f["gross"] is not None]
    n = [f["net"] for f in fires if f["net"] is not None]
    c = [f["cost_r"] for f in fires if f["cost_r"] is not None]
    return {"trades": len(fires), "gross": round(sum(g), 3), "net": round(sum(n), 3),
            "cost_r_per_trade": round(sum(c) / len(c), 4) if c else None}


# ============================ hard-stop clock guard ===========================
def may_start_unit(now: Optional[datetime] = None) -> tuple[bool, str]:
    """A unit may START only in the overnight window: from 16:00 IST until 08:30 IST.
    08:30-08:45 -> no new starts; >= 08:45 -> refuse outright. (A unit is ~15 min, so the
    last permitted start finishes well before the 09:05 recorder connect.)"""
    now = now or datetime.now(IST)
    t = now.timetz().replace(tzinfo=None)
    if HARD_STOP_START <= t < MARKET_EVENING:
        reason = ("HARD STOP: past 08:45 IST — refuse" if t >= HARD_STOP_REFUSE
                  else "HARD STOP: no unit starts after 08:30 IST")
        return False, reason
    return True, "ok"


# ============================ resumable batch driver ==========================
def result_path(state_dir: Path, day: str, size: int) -> Path:
    return Path(state_dir) / f"sweep_{day}_s{size}.json"


def stub_path(state_dir: Path, size: int) -> Path:
    return Path(state_dir) / f"sweep_stubs_s{size}.json"


def plan_units(days: Sequence[str], sizes: Sequence[int], batch_width: int,
               state_dir: Path) -> list[tuple[str, list[int]]]:
    """(day, batch) units in chronological day order; a batch keeps only its sizes whose
    result JSON is missing (resume support). Fully-done batches drop out."""
    units = []
    for day in sorted(days):
        pending = [s for s in sizes if not result_path(state_dir, day, s).exists()]
        for i in range(0, len(pending), batch_width):
            units.append((day, pending[i:i + batch_width]))
    return units


def run_unit(day: str, batch: list[int], *, root: str | Path, state_dir: Path,
             instruments: Sequence[str] = ("NIFTY_FUT", "BANKNIFTY_FUT"),
             base_config_path=None) -> None:
    """Capture one (day, batch) and write one result JSON per size IMMEDIATELY. The anchored
    median for (day, size) comes from the SAME size's prior-day candidate stubs."""
    from research.bar_quality import bar_quality
    from research.delta_vwap_evaluator import verify_against_disk
    caps = capture_day_multi(day, batch, root=root, base_config_path=base_config_path)
    for size, cap in caps.items():
        sp = stub_path(state_dir, size)
        stubs = json.loads(sp.read_text()) if sp.exists() else {}
        captures = {d: DayCapture(day=d, candidates=stubs[d]) for d in stubs if d < day}
        captures[day] = cap
        prior = sorted(d for d in stubs if d < day)
        res = {"label": "IN-SAMPLE EXPLORATION — NOT A REGISTERED RESULT",
               "day": day, "size": size, "prior_days": prior}
        res["verify"] = (verify_against_disk(cap, Path(root) / "analysis") if size == 100
                         else {"checked": False, "reason": "non-baseline bar size"})
        for inst in instruments:
            dmed = median_delta_al(captures, prior, inst)
            fires = perfire_records(cap, inst, dmed)
            dd = dedup_sequential(fires)
            sid = next((c["sid"] for c in cap.candidates if c["instrument"] == inst), None)
            inst_bars = cap.bars.get(sid, [])
            res[inst] = {"train_median": dmed,
                         "bars": len(inst_bars),
                         "candidates": sum(1 for c in cap.candidates if c["instrument"] == inst),
                         "fires": len(fires),
                         "candidate_view": _sums(fires),
                         "dedup_view": _sums(dd),
                         "perfire": fires,
                         "bar_quality": bar_quality(inst_bars) if inst_bars else None}
        result_path(state_dir, day, size).write_text(json.dumps(res))
        # append this day's candidates to the size's stub state (median source for later days)
        keep = ("ts_ns", "sid", "instrument", "side", "fired", "score",
                "delta_al", "vwap_dist_al")
        stubs[day] = [{k: c[k] for k in keep} for c in cap.candidates]
        sp.write_text(json.dumps(stubs))


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="research.barsize_sweep")
    ap.add_argument("--days", required=True)
    ap.add_argument("--sizes", required=True)
    ap.add_argument("--batch-width", type=int, required=True)
    ap.add_argument("--state-dir", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--base-config", default=None)
    ap.add_argument("--one-unit", action="store_true",
                    help="process exactly ONE pending unit then exit (external loop restarts)")
    args = ap.parse_args(argv)
    days = [d for d in args.days.split(",") if d.strip()]
    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]
    state_dir = Path(args.state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    units = plan_units(days, sizes, args.batch_width, state_dir)
    if not units:
        print("nothing pending — sweep complete")
        return 0
    for day, batch in units:
        ok, why = may_start_unit()
        if not ok:
            print(f"STOP before ({day}, {batch}): {why} — state is resumable")
            return 3
        print(f"unit start ({day}, sizes {batch}) at {datetime.now(IST):%H:%M IST}")
        run_unit(day, batch, root=args.root, state_dir=state_dir,
                 base_config_path=args.base_config)
        print(f"unit done  ({day}, sizes {batch})")
        if args.one_unit:
            return 0
    print("sweep complete")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
