"""DELTA+VWAP-SIDE REAL-DATA EVALUATOR (2026-07-21) — the ONE stress-test survivor,
wired as a walk-forward Evaluator. RESEARCH LANE ONLY: read-only over recorded days,
in-memory replay, writes nothing, touches no live/recorder path, R2 hash untouched.

THE FROZEN RULE (founder decision 2026-07-21 — do not deviate):
  fire(candidate) :=  delta_al  STRICTLY >  median(delta_al | same instrument,
                                                   TRAINING WINDOW ONLY)
                 AND  vwap_dist_al STRICTLY > 0
  with  delta_al    = bar_delta        * (+1 long / -1 short)
        vwap_dist_al = (price - VWAP)  * (+1 long / -1 short)
  exactly as first found in the 3-day deep-dive (scratch dd_analyze.py:78-82,93).

INHERITED QUIRKS — PRESERVED DELIBERATELY, do not "fix" (they are part of the rule
as originally found; a candidate exactly at the median or exactly at VWAP does NOT
pass):
  * delta:  None -> no fire; otherwise STRICT > (a tie at the median fails).
    delta_al == 0.0 is a real value and compares normally (dd_analyze ``good()``).
  * vwap:   the original ``(feat.get("vwap_dist_al", -1) or -1) > 0`` — ``or`` makes
    BOTH None and exactly-0.0 falsy, so price exactly AT VWAP does not fire.
  * median: dd_analyze ``med()`` — true median (mean of middle two on even N).

MEDIAN POPULATION: every candidate row (both sides, fired or not) of the instrument
over the training-window days — the committed generalization of the original
53-qualified-candidate pool. CONSEQUENCE (not a deviation): each bar emits a long
row (+delta) and a short row (-delta), so the pooled per-window median sits at ~0 by
construction and the gate degenerates in practice to "delta on your side AND price
on your side of VWAP" — which is exactly the plain-English survivor in TAPE_NOTES
("bar delta + price on correct side of VWAP"). The median machinery is kept anyway:
it is the frozen text, it flows through the audited split boundaries, and it guards
any future population change.

LEAK CONTRACT: the median for any evaluated day comes ONLY from days STRICTLY
BEFORE it (``make_evaluator``: anchored, embargo 0 — the P2-audited day-granular
boundary, walkforward.py:123-139) or from an explicit ``Split.train_days``
(``median_for_split`` — reuses walk_forward_splits' purge+embargo construction,
never reinvents it). Planted-leak tested.

HYPOTHETICAL PRICING = THE LIVE PATH, NOT AN APPROXIMATION: rule-fired candidates
are priced with the same objects a live fire uses — build_exit_plan + SimPosition
(signals/exits.py; engine.py:258-264 imports the identical functions), stepped on
CLOSED tick bars only with the engine's own momentum_flow_flags, force-closed at
the last closed bar (engine.py:431-436). Deliberately NO tape.finalize() here —
unlike the P5 spine, the live SignalEngine never sees the trailing partial bar.
Costs replicate _apply_costs verbatim (trade_net_r on inputs captured DURING the
replay at each candidate's own bar, so chain state is as-of, not end-of-day); a
missing cost input -> net is None, never estimated. Candidates are priced
INDEPENDENTLY (no cooldown/one-position portfolio effects), same as the deep-dive.

STATUS: DEFAULT OFF — nothing imports this; CLI/explicit call only.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

from research.walkforward import Split, Trade

R_FIELDS = ("realized_r", "realized_r_net")


# ============================ the frozen rule ================================
def med(vals: Sequence[float]) -> float:
    """dd_analyze.py ``med()`` verbatim: true median, mean of middle two on even N."""
    s = sorted(vals)
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2


def rule_fires(delta_al: Optional[float], vwap_dist_al: Optional[float],
               dmed: Optional[float]) -> bool:
    """The frozen gate. ``dmed`` None (no training data) -> never fires."""
    if dmed is None or delta_al is None:
        return False
    if not (delta_al > dmed):                 # STRICT: a tie at the median fails
        return False
    return (vwap_dist_al or -1) > 0           # None OR exactly-0.0 -> falsy -> no fire


# ============================ per-day capture ================================
@dataclass
class DayCapture:
    """Everything one recorded day contributes: candidates (== signals.parquet rows,
    regenerated in-memory by the same deterministic pipeline) + what pricing needs."""
    day: str
    candidates: list = field(default_factory=list)   # {ts_ns, sid, instrument, side,
    #                                                  fired, score, delta_al, vwap_dist_al}
    ctx: dict = field(default_factory=dict)          # (sid, ts_ns) -> SignalContext
    bars: dict = field(default_factory=dict)         # sid -> CLOSED tick bars, ts order
    cost_inputs: dict = field(default_factory=dict)  # (sid, ts_ns, side) -> ci dict
    sig_cfg: object = None
    depth_ofi_enabled: bool = False


def capture_day(day: str, *, root: str | Path = ".",
                instruments: list[str] | None = None,
                config_path: str | Path | None = None) -> DayCapture:
    """One full-day replay through the EVENING PIPELINE'S OWN constructor
    (signals/pipeline.build_pipeline — engines, order and config identical to what
    wrote signals.parquet), instrumented in-memory to also keep, per candidate:
    its SignalContext, and cost inputs captured at that bar (chain state as-of).
    ``instruments=None`` replays every file (pipeline-identical; needed for chain/
    VIX); pass a filter only for tests/lean runs. ``config_path=None`` = the frozen
    tape_config.yaml (real runs); tests pass a fixture config."""
    from replayer.engine import ReplayEngine
    from replayer.source import ReplaySource
    from signals.config import load_signal_config
    from signals.pipeline import build_pipeline

    dd = Path(root) / "data" / day
    multi, parts = build_pipeline(dd, load_signal_config(config_path),
                                  config_path=config_path)
    sig, tape, meta = parts["signal"], parts["tape"], parts["meta"]
    ctxs: dict = {}
    costs: dict = {}
    orig_bc = sig._build_context                     # instance-level instrumentation only —
    def _bc(sid, bar, ts):                           # signals/ code itself is untouched
        c = orig_bc(sid, bar, ts)
        ctxs[(sid, c.ts_ns)] = c
        return c
    sig._build_context = _bc
    orig_ev = sig._evaluate
    def _ev(sid, bar, ts):
        orig_ev(sid, bar, ts)
        c = ctxs.get((sid, bar["end_ts_ns"]))
        if c is not None:                            # cost inputs AT the bar (as-of chain)
            for side in sig.sides:
                costs[(sid, c.ts_ns, side)] = sig._capture_cost_inputs(c, side)
    sig._evaluate = _ev

    ReplayEngine(ReplaySource(dd, instruments=instruments)).drive(multi, speed="max")
    sig.finalize()

    bars: dict = {}
    for b in tape.bar_rows:                          # CLOSED bars only — see module doc:
        if b["bar_type"] == "tick":                  # live stepping never sees the trailing
            bars.setdefault(b["security_id"], []).append(b)   # partial (NO tape.finalize())
    for arr in bars.values():
        arr.sort(key=lambda b: b["end_ts_ns"])

    sid_by = {m["symbol"]: s for s, m in meta.items()}
    cands = []
    for r in sig.rows:                               # sig.rows == the day's signals.parquet
        sid = sid_by.get(r["instrument"])
        c = ctxs.get((sid, r["ts_ns"]))
        sgn = 1 if r["side"] == "long" else -1
        cands.append({
            "ts_ns": r["ts_ns"], "sid": sid, "instrument": r["instrument"],
            "side": r["side"], "fired": bool(r["fired"]), "score": r["score"],
            "delta_al": (c.bar_delta * sgn) if c is not None else None,
            "vwap_dist_al": ((c.price - c.vwap) * sgn)
                            if (c is not None and c.vwap is not None) else None,
        })
    return DayCapture(day=day, candidates=cands, ctx=ctxs, bars=bars,
                      cost_inputs=costs, sig_cfg=sig.cfg,
                      depth_ofi_enabled=tape.cfg.depth_ofi_enabled)


def verify_against_disk(cap: DayCapture, analysis_root: str | Path) -> dict:
    """Optional cross-check: the regenerated candidates must match the day's
    signals.parquet 1:1 on (ts_ns, instrument, side, fired). Read-only."""
    import pyarrow.parquet as pq
    p = Path(analysis_root) / cap.day / "signals.parquet"
    if not p.exists():
        return {"day": cap.day, "checked": False, "reason": "no signals.parquet"}
    t = pq.read_table(str(p), columns=["ts_ns", "instrument", "side", "fired"])
    disk = {(int(a), b, c, bool(d)) for a, b, c, d in
            zip(*(t.column(k).to_pylist() for k in ("ts_ns", "instrument", "side", "fired")))}
    mem = {(int(c["ts_ns"]), c["instrument"], c["side"], c["fired"]) for c in cap.candidates}
    return {"day": cap.day, "checked": True, "disk_rows": len(disk), "mem_rows": len(mem),
            "match": disk == mem}


# ============================ training-window median =========================
def median_delta_al(captures: dict[str, DayCapture], days: Sequence[str],
                    instrument: str) -> Optional[float]:
    """median(delta_al) over ALL candidate rows of ``instrument`` across ``days``.
    The caller decides the window; the leak contract lives in the two wrappers below."""
    vals = [c["delta_al"] for d in days for c in captures[d].candidates
            if c["instrument"] == instrument and c["delta_al"] is not None]
    return med(vals) if vals else None


def median_for_split(split: Split, captures: dict[str, DayCapture],
                     instrument: str) -> Optional[float]:
    """The split-faithful form: TRAIN DAYS ONLY (walk_forward_splits already excludes
    the embargo gap and the test window — P2's audited boundaries, reused not reinvented)."""
    return median_delta_al(captures, split.train_days, instrument)


def rule_decisions(cap: DayCapture, instrument: str,
                   dmed: Optional[float]) -> list[tuple[dict, bool]]:
    """(candidate, fires?) for every candidate of ``instrument`` on the day."""
    return [(c, rule_fires(c["delta_al"], c["vwap_dist_al"], dmed))
            for c in cap.candidates if c["instrument"] == instrument]


# ============================ hypothetical pricing ===========================
def price_candidate(cap: DayCapture, cand: dict) -> Optional[dict]:
    """Price ONE candidate as a live fire would (see module doc). Returns None when
    unpriceable (no ctx / degenerate plan / no bar after entry)."""
    from signals.costs import CostConfig, trade_net_r
    from signals.engine import momentum_flow_flags
    from signals.exits import SimBar, SimPosition, build_exit_plan

    ctx = cap.ctx.get((cand["sid"], cand["ts_ns"]))
    if ctx is None:
        return None
    side, cfg = cand["side"], cap.sig_cfg
    plan = build_exit_plan(ctx, cfg, side)           # the fire path, engine.py:259
    if plan.r_value <= 0:
        return None
    pos = SimPosition(plan, ctx.ts_ns)
    md = cfg.exits.get("momentum_death", {})
    out, last = None, None
    for b in cap.bars.get(cand["sid"], []):
        if b["end_ts_ns"] <= cand["ts_ns"]:          # first step = the NEXT closed bar,
            continue                                 # same as live _on_new_bar step order
        flow = momentum_flow_flags(md, side, b.get("cvd_slope", 0.0), b.get("ofi"),
                                   cap.depth_ofi_enabled)      # == engine._flow_flags
        out = pos.step(SimBar(b["end_ts_ns"], b["high"], b["low"], b["close"], flow))
        last = b
        if out is not None:
            break
    if out is None:
        if last is None:
            return None
        # live finalize: force-close at the last CLOSED bar's close (engine.py:431-436).
        # exit_ns = that bar's ts (live labels it entry_ts — price/R identical either way).
        out = pos.force_close(last["end_ts_ns"], last["close"])
    rec = {"entry": plan.entry, "stop": plan.stop, "target": plan.target_1r,
           "r_value": plan.r_value, "stop_source": plan.stop_source,
           "exit_reason": out.exit_reason, "realized_r": out.realized_r,
           "entry_ns": ctx.ts_ns, "exit_ns": out.exit_ts_ns,
           "cost_r": None, "realized_r_net": None}
    ci = cap.cost_inputs.get((cand["sid"], cand["ts_ns"], side))
    # _apply_costs guards verbatim (engine.py:317-330): any missing input -> gross only
    if ci and rec["realized_r"] is not None and rec["r_value"] \
            and ci.get("lot") and ci.get("premium"):
        net, cost_r, _ = trade_net_r(
            realized_r=rec["realized_r"], r_unit_pts=rec["r_value"],
            entry_premium=ci["premium"], delta=ci["delta"],
            delta_source=ci["delta_source"], lot_size=ci["lot"],
            cfg=CostConfig.from_dict(cfg.cost_model))
        rec["cost_r"] = round(cost_r, 4)
        rec["realized_r_net"] = round(net, 4)
    return rec


# ============================ evaluator seam =================================
def day_trades(cap: DayCapture, instrument: str, dmed: Optional[float],
               r_field: str = "realized_r") -> tuple[list[Trade], dict]:
    """Apply the frozen rule to one day and price the passers. ``r_field`` picks the
    Trade outcome metric: gross ``realized_r`` (always present) or ``realized_r_net``
    (trades missing cost inputs are SKIPPED and counted — never estimated)."""
    if r_field not in R_FIELDS:
        raise ValueError(f"r_field must be one of {R_FIELDS}")
    trades: list[Trade] = []
    audit = {"day": cap.day, "candidates": 0, "rule_fires": 0, "priced": 0,
             "skipped_unpriceable": 0, "skipped_no_net": 0}
    for cand, fires in rule_decisions(cap, instrument, dmed):
        audit["candidates"] += 1
        if not fires:
            continue
        audit["rule_fires"] += 1
        rec = price_candidate(cap, cand)
        if rec is None:
            audit["skipped_unpriceable"] += 1
            continue
        r = rec.get(r_field)
        if r is None:
            audit["skipped_no_net"] += 1
            continue
        audit["priced"] += 1
        trades.append(Trade(day=cap.day, entry_ns=rec["entry_ns"],
                            exit_ns=rec["exit_ns"], r=r))
    return trades, audit


def split_test_trades(split: Split, captures: dict[str, DayCapture], instrument: str,
                      r_field: str = "realized_r") -> list[Trade]:
    """Test-window trades for one split, median frozen from split.train_days ONLY."""
    dmed = median_for_split(split, captures, instrument)
    out: list[Trade] = []
    for d in split.test_days:
        out.extend(day_trades(captures[d], instrument, dmed, r_field)[0])
    return out


def make_evaluator(calendar_days: Sequence[str], captures: dict[str, DayCapture],
                   instrument: str, r_field: str = "realized_r"):
    """The walkforward.py Evaluator seam (walkforward.py:58), instrument-filtered so
    NIFTY and BANKNIFTY run as fully separate invocations. The sweep param is accepted
    and IGNORED — the rule is single and frozen, there is no knob to sweep.

    Leak contract: each evaluated day's median uses ONLY calendar days STRICTLY before
    it (anchored, embargo 0 == the P2-audited boundary). The first calendar day has no
    prior data -> dmed None -> zero trades, by design."""
    cal = sorted(calendar_days)

    def evaluator(_param_value, days: Sequence[str]) -> list[Trade]:
        out: list[Trade] = []
        for d in days:
            train = [x for x in cal if x < d]
            dmed = median_delta_al(captures, train, instrument)
            out.extend(day_trades(captures[d], instrument, dmed, r_field)[0])
        return out

    return evaluator


# ============================ CLI (explicit only) ============================
def main(argv: list[str]) -> int:
    """EXPLICIT-ONLY research CLI: capture the given days, run the anchored
    per-instrument evaluation, print per-day audits + trades as JSON. Heavy
    (full-day replays incl. option chain) — run one instrument at a time on the
    3.8GB host and NEVER while live recorders are under memory pressure."""
    import argparse
    ap = argparse.ArgumentParser(prog="research.delta_vwap_evaluator")
    ap.add_argument("--days", required=True, help="comma-separated, ascending")
    ap.add_argument("--instrument", required=True,
                    choices=["NIFTY_FUT", "BANKNIFTY_FUT"])
    ap.add_argument("--r-field", default="realized_r", choices=list(R_FIELDS))
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv[1:])
    days = [d for d in args.days.split(",") if d.strip()]
    captures = {}
    for d in days:
        captures[d] = capture_day(d, root=args.root)
        print(f"captured {d}: {len(captures[d].candidates)} candidates", file=sys.stderr)
    ev = make_evaluator(days, captures, args.instrument, args.r_field)
    report = []
    for d in days:
        train = [x for x in days if x < d]
        dmed = median_delta_al(captures, train, args.instrument)
        trades, audit = day_trades(captures[d], args.instrument, dmed, args.r_field)
        audit["train_median"] = dmed
        audit["trades"] = [{"entry_ns": t.entry_ns, "exit_ns": t.exit_ns, "r": t.r}
                           for t in trades]
        report.append(audit)
    print(json.dumps({"instrument": args.instrument, "r_field": args.r_field,
                      "days": report}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
