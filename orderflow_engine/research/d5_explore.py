"""D5 EXPLORATION BACKTEST (2026-07-25) — IN-SAMPLE, DESCRIPTIVE ONLY, NO ADOPTION.

Implements the SEALED D5 spec (docs/designs/D5_BREAKOUT_FAMILY_DESIGN_DRAFT.md, sealed
39539e7; ledger R2-18) on pre-window burned days per the frozen window rule (4fb7cdf).
Founder rulings (2026-07-25): G4 = DQ + standing 3-bucket time gate ONLY (spread and
OR-width sub-gates UNSEALED-OMITTED — weaker G4 => more passers, labeled); 07-13 =
burn-in (reference-only, no trades); 15:15 flatten sealed-by-instruction.

SEALED SOURCES REUSED (zero duplication):
  * OR levels = R4's Initial-Balance definition via lar_study's own construction
    (ORH/ORL fixed at IB end, 60 min — "no second opening-range definition exists").
  * G1 = UNSIGNED response efficiency |close-open|/tick / bar TOTAL volume (the D5 /
    FEED_PHYSICS-blessed unsigned variant), on 1-MIN TIME BARS (FEED_PHYSICS: tick-bar
    clock is a saturating packet clock). Threshold = 80th percentile (sealed) of the
    SAME-TIME-BUCKET distribution from TRAILING PRIOR runnable days only (anchored,
    P2 pattern — day t uses days < t; no same-day data).
  * G2 = research.depth_proxies DepthProxyEngine (existing frozen definitions):
    up-break PASS = >=1 vanishing-'wall' event on the ASK side during the break
    minute AND no 'refill' event on the ASK side in that minute (mirror for down).
    Depth absent => G2 = UNAVAILABLE (day runs PARTIAL-GATE, never pooled with full).
  * G3 = research.lar_study LevelMachine on the broken level (its own STUDY_CONFIG,
    K = sweep_to_absorption_bars = 10 tick-100 bars): FAKE = first post-break
    transition into ABSORPTION_CANDIDATE/FLOW_FLIPPED/RECLAIMED/ARMED/TRIGGERED
    (the sweep->reclaim-AGAINST path). Machine 'FAILED: breakout not sweep' = REAL.
    Before entry -> BLOCK; while open -> EXIT (reason LAR-veto).
  * Exits FROZEN: stop -1R, target +1.5R, 15:15 IST flatten. R-UNIT = entry price ->
    broken-level distance (level-anchored; UNSEALED-DEFINED-BY-ANCHOR, re-freeze at
    Round-2). Degenerate R < 2 ticks => trade skipped, counted.
  * Cost = signals.costs atm_option_delta/premium + trade_net_r fed from the RECORDED
    analysis/<day>/chain_<INDEX>.parquet rows (recorded-greeks path, fallback flagged).
One position per instrument; re-entry only after flat AND a fresh break episode
(price 1-min-closed back inside the OR between breaks).
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

IST = timezone(timedelta(hours=5, minutes=30))
NS = 1_000_000_000
TICK = 0.05
HERE = Path(__file__).resolve().parent.parent
G1_PCTILE = 80.0                     # sealed (D5 freeze-list value)
FAKE_STATES = {"ABSORPTION_CANDIDATE", "FLOW_FLIPPED", "RECLAIMED", "ARMED", "TRIGGERED"}
BUCKETS = [("0915_1030", 9, 15, 10, 30), ("1030_1300", 10, 30, 13, 0),
           ("1300_1530", 13, 0, 15, 30)]
FLATTEN_HHMM = (15, 15)              # sealed-by-instruction
MIN_R_TICKS = 2                      # degenerate-R guard (objective, counted)


def _bnd(day, h, m):
    d = datetime.fromisoformat(day)
    return int(datetime(d.year, d.month, d.day, h, m, tzinfo=IST).timestamp() * 1e9)


def bucket_of(day: str, ts: int) -> Optional[str]:
    for nm, h1, m1, h2, m2 in BUCKETS:
        if _bnd(day, h1, m1) <= ts < _bnd(day, h2, m2):
            return nm
    return None


def pctile(xs, p):
    if not xs:
        return None
    s = sorted(xs)
    return s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))]


# ============================ per-day capture ================================
def capture(day: str, sym: str, *, root: Path) -> dict:
    """One replay (futures-only): 1-min bars, tick-100 bars + LAR feats (lar_study's own
    construction), depth-proxy events (if depth present). Read-only."""
    from replayer.engine import ReplayEngine
    from replayer.source import ReplaySource
    from tape.config import load_tape_config
    from tape.engine import TapeEngine
    from tape.trades import TradeExtractor
    from levels.config import load_levels_config
    from signals.pipeline import build_meta
    from recorder.depth_schema import SIDE_BID
    from research.price_efficiency import rolling_efficiency
    from research.depth_proxies import DepthProxyEngine, aggregate, snapshot_to_book
    from research.lar_study import STUDY_CONFIG

    dd = root / "data" / day
    meta = build_meta(dd)
    symmap = {s: m["symbol"] for s, m in meta.items()}
    sid = next(s for s, m in meta.items() if m["symbol"] == sym)
    has_depth = (dd / "depth").exists() and any(
        f.name.startswith(sym) for f in (dd / "depth").glob("*.parquet"))
    ib_min = load_levels_config().initial_balance_minutes

    tape = TapeEngine(load_tape_config(), symmap)
    dpe = DepthProxyEngine()
    extract = TradeExtractor()
    trades: list[tuple[int, float, int]] = []       # (ts, price, qty) for 1-min bars

    class _C:
        def on_packet(self, parsed, ts):
            tape.on_packet(parsed, ts)
            if parsed.get("is_tick") and parsed.get("security_id") == sid:
                tr = extract.on_tick(parsed)
                if tr is not None:
                    trades.append((tr.ts_ns, tr.price, tr.size))
                    dpe.on_trade(tr.ts_ns, tr.price, tr.size)
        def on_depth(self, parsed, ts):
            tape.on_depth(parsed, ts)
            if parsed.get("security_id") == sid:
                dpe.on_snapshot(ts, "bid" if parsed.get("side") == SIDE_BID else "ask",
                                snapshot_to_book(parsed))
        def on_event(self, k, d, v):
            tape.on_event(k, d, v)

    ReplayEngine(ReplaySource(dd, instruments=[sym])).drive(_C(), speed="max")

    # 1-min bars (session 09:15-15:30)
    a0, a3 = _bnd(day, 9, 15), _bnd(day, 15, 30)
    W = 60 * NS
    m1: dict[int, list] = {}
    for T, P, V in trades:
        if not (a0 <= T <= a3):
            continue
        gi = (T - a0) // W
        b = m1.get(gi)
        if b is None:
            m1[gi] = [P, P, P, P, V]
        else:
            b[1] = max(b[1], P); b[2] = min(b[2], P); b[3] = P; b[4] += V
    bars1 = [{"ts": a0 + gi * W, "end": a0 + (gi + 1) * W,
              "open": v[0], "high": v[1], "low": v[2], "close": v[3], "vol": v[4]}
             for gi, v in sorted(m1.items())]

    # tick-100 bars + LAR feats (lar_study's own construction, verbatim pattern)
    tbars = sorted([b for b in tape.bar_rows
                    if b["security_id"] == sid and b["bar_type"] == "tick"],
                   key=lambda b: b["end_ts_ns"])
    eff = rolling_efficiency(tbars, window=STUDY_CONFIG["eff_window"]) if tbars else []
    prows = aggregate(dpe.events, [(b["start_ts_ns"], b["end_ts_ns"]) for b in tbars],
                      window=STUDY_CONFIG["proxy_window"]) if (has_depth and tbars) else None
    session0 = tbars[0]["start_ts_ns"] if tbars else a0
    ib_end = session0 + ib_min * 60 * NS
    orh = orl = None
    feats = []
    trs, vols = [], []
    eff_hist: list[float] = []
    prev_close = None
    for i, b in enumerate(tbars):
        tr = (b["high"] - b["low"]) if prev_close is None else \
            max(b["high"] - b["low"], abs(b["high"] - prev_close), abs(b["low"] - prev_close))
        trs.append(tr); prev_close = b["close"]; vols.append(float(b["volume"]))
        atr = sum(trs[-STUDY_CONFIG["atr_bars"]:]) / min(len(trs), STUDY_CONFIG["atr_bars"])
        vm = sorted(vols[-STUDY_CONFIG["vol_median_bars"]:])
        if b["end_ts_ns"] <= ib_end:
            orh = b["high"] if orh is None else max(orh, b["high"])
            orl = b["low"] if orl is None else min(orl, b["low"])
        e = eff[i]
        f = {"ts": b["end_ts_ns"], "open": b["open"], "high": b["high"],
             "low": b["low"], "close": b["close"], "atr": atr,
             "vol": float(b["volume"]), "vol_med20": vm[len(vm) // 2],
             "delta": b["delta"], "book_ofi": None,
             "eff_up_w": e["up_w"], "eff_dn_w": e["dn_w"],
             "refills_w_bid": (prows[i]["bid_refills_w"] if prows else None),
             "refills_w_ask": (prows[i]["ask_refills_w"] if prows else None),
             "has_depth": has_depth, "ib_fixed": b["end_ts_ns"] > ib_end,
             "orh": orh, "orl": orl}
        # lar_study's own aligned-efficiency history (verbatim pattern)
        eff_hist.append(min(e["up_w"], e["dn_w"]))
        s_hist = sorted(eff_hist)
        f["eff_p25_aligned"] = s_hist[max(0, int(0.25 * (len(s_hist) - 1)))] if len(s_hist) >= 20 else None
        feats.append(f)
    return {"day": day, "sym": sym, "bars1": bars1, "feats": feats,
            "events": list(dpe.events), "has_depth": has_depth, "ib_end": ib_end,
            "orh": orh, "orl": orl}


# ============================ gates ==========================================
def g1_values(cap: dict, day: str) -> dict[str, list[float]]:
    """Per-bucket unsigned response efficiencies of ALL 1-min bars (reference source)."""
    out: dict[str, list[float]] = {}
    for b in cap["bars1"]:
        bk = bucket_of(day, b["ts"])
        if bk is None or b["vol"] <= 0:
            continue
        out.setdefault(bk, []).append(abs(b["close"] - b["open"]) / TICK / b["vol"])
    return out


def g2_check(cap: dict, break_bar: dict, direction: str) -> Optional[dict]:
    """None if depth unavailable. up-break: ASK wall-vanish AND no ASK refill in the
    break minute (mirror bid for down). depth_proxies' frozen event definitions."""
    if not cap["has_depth"]:
        return None
    side = "ask" if direction == "up" else "bid"
    evs = [e for e in cap["events"]
           if break_bar["ts"] <= e.ts_ns < break_bar["end"] and e.side == side]
    wall = any(e.kind == "wall" for e in evs)
    refill = any(e.kind == "refill" for e in evs)
    return {"wall_vanish": wall, "refill_into_break": refill,
            "passed": wall and not refill}


def run_lar(cap: dict, level_name: str, level_price: float) -> list:
    """The broken level's machine over tick-100 feats (lar_study's own class/config)."""
    from research.lar_study import LevelMachine
    m = LevelMachine(level_name, round(level_price, 2))
    for f in cap["feats"]:
        if not f["ib_fixed"]:
            continue
        m.on_bar(f)
        if m.terminal():
            break
    return m.transitions


def g3_fake_ts(transitions, after_ts: int) -> Optional[int]:
    """First post-break transition into the reclaim-against path -> FAKE ts (else None)."""
    for t in transitions:
        if t.ts_ns > after_ts and t.new in FAKE_STATES:
            return t.ts_ns
    return None


# ============================ episodes + trades ==============================
def break_episodes(cap: dict, day: str) -> list[dict]:
    """Every 1-min-close break beyond ORH/ORL after IB-fix; a NEW episode requires a
    1-min close back inside [ORL, ORH] since the previous break."""
    orh, orl = cap["orh"], cap["orl"]
    if orh is None or orl is None:
        return []
    eps = []
    armed = True
    for b in cap["bars1"]:
        if b["end"] <= cap["ib_end"]:
            continue
        if armed and b["close"] > orh:
            eps.append({"bar": b, "direction": "up", "level": "ORH", "price": orh}); armed = False
        elif armed and b["close"] < orl:
            eps.append({"bar": b, "direction": "dn", "level": "ORL", "price": orl}); armed = False
        elif not armed and orl <= b["close"] <= orh:
            armed = True
    return eps


def cost_for(day: str, sym: str, entry_ts: int, entry_px: float, direction: str,
             gross_r: float, r_pts: float, *, analysis_root: Path) -> dict:
    from signals.costs import CostConfig, atm_option_delta, atm_option_premium, trade_net_r
    import pyarrow.parquet as pq
    index = "NIFTY" if sym.startswith("NIFTY") else "BANKNIFTY"
    p = analysis_root / day / f"chain_{index}.parquet"
    if not p.exists():
        return {"cost_r": None, "net_r": None, "note": "no chain parquet"}
    t = pq.read_table(str(p))
    rows = [dict(zip(t.column_names, r)) for r in zip(*[t.column(c).to_pylist()
                                                        for c in t.column_names])]
    for r in rows:
        r["index"] = index
    cfg = CostConfig.from_dict({})
    side = "long" if direction == "up" else "short"
    delta, dsrc = atm_option_delta(rows, entry_ts, entry_px, side, cfg)
    prem = atm_option_premium(rows, entry_ts, entry_px, side)
    lot = 65 if index == "NIFTY" else 30                     # dated scrip-master values
    if not prem:
        return {"cost_r": None, "net_r": None, "note": "no premium at ts"}
    net, cost_r, _ = trade_net_r(realized_r=gross_r, r_unit_pts=r_pts, entry_premium=prem,
                                 delta=delta, delta_source=dsrc, lot_size=lot, cfg=cfg)
    return {"cost_r": round(cost_r, 3), "net_r": round(net, 3), "note": dsrc}


def would_outcome(cap: dict, ep: dict, r_pts: float, day: str) -> str:
    """Post-break path regardless of gates: +1.5R-first / -1R-first / neither (flatten)."""
    entry = ep["bar"]["close"]; d = 1 if ep["direction"] == "up" else -1
    stop = entry - d * r_pts; tgt = entry + d * 1.5 * r_pts
    fl = _bnd(day, *FLATTEN_HHMM)
    for b in cap["bars1"]:
        if b["ts"] < ep["bar"]["end"]:
            continue
        if b["ts"] >= fl:
            break
        if (d > 0 and b["low"] <= stop) or (d < 0 and b["high"] >= stop):
            return "stop_first"
        if (d > 0 and b["high"] >= tgt) or (d < 0 and b["low"] <= tgt):
            return "target_first"
    return "neither_flatten"


def run_day(day: str, *, root: Path, analysis_root: Path,
            refs: dict, trade_allowed: bool = True) -> dict:
    """One day both instruments: episodes, gates, trades. refs[(sym,bucket)] = prior
    days' G1 values (CAUSAL — this day's values are appended only AFTER decisions)."""
    out = {"day": day, "episodes": [], "trades": [], "g1_day_values": {}}
    for sym in ("NIFTY_FUT", "BANKNIFTY_FUT"):
        cap = capture(day, sym, root=root)
        day_vals = g1_values(cap, day)
        out["g1_day_values"][sym] = day_vals
        lar_cache: dict[str, list] = {}
        position_until = 0
        for ep in break_episodes(cap, day):
            b = ep["bar"]; bk = bucket_of(day, b["ts"])
            ref = refs.get((sym, bk), [])
            thr = pctile(ref, G1_PCTILE)
            effv = abs(b["close"] - b["open"]) / TICK / b["vol"] if b["vol"] else 0.0
            g1 = {"eff": round(effv, 8), "thr": (round(thr, 8) if thr is not None else None),
                  "ref_n": len(ref), "passed": (thr is not None and effv >= thr)}
            g2 = g2_check(cap, b, ep["direction"])
            if ep["level"] not in lar_cache:
                lar_cache[ep["level"]] = run_lar(cap, ep["level"], ep["price"])
            fk = g3_fake_ts(lar_cache[ep["level"]], b["end"])
            g4 = {"dq": True, "bucket": bk, "passed": bk is not None,
                  "note": "spread+OR-width UNSEALED-OMITTED"}
            r_pts = abs(b["close"] - ep["price"])
            degenerate = r_pts < MIN_R_TICKS * TICK
            gates_pass = bool(g1["passed"] and (g2 is None or g2["passed"]) and g4["passed"]
                              and not (fk is not None and fk <= b["end"]))
            wo = would_outcome(cap, ep, r_pts, day) if not degenerate else "degenerate_r"
            rec = {"day": day, "sym": sym, "time": datetime.fromtimestamp(b["end"]/1e9, IST).strftime("%H:%M"),
                   "direction": ep["direction"], "level": ep["level"], "level_px": ep["price"],
                   "break_close": b["close"], "bucket": bk, "g1": g1,
                   "g2": (g2 if g2 is not None else "UNAVAILABLE"),
                   "g3_fake_ts": fk, "g4": g4, "gates_pass": gates_pass,
                   "degenerate_r": degenerate, "would": wo,
                   "gate_class": "FULL" if cap["has_depth"] else "PARTIAL"}
            out["episodes"].append(rec)
            # trade (burn-in day: trade_allowed=False)
            if not (trade_allowed and gates_pass and not degenerate):
                continue
            if b["end"] < position_until:
                rec["skipped"] = "position_open"
                continue
            d = 1 if ep["direction"] == "up" else -1
            entry = b["close"]; stop = entry - d * r_pts; tgt = entry + d * 1.5 * r_pts
            fl = _bnd(day, *FLATTEN_HHMM)
            exit_px = None; reason = None; exit_ts = None
            for nb in cap["bars1"]:
                if nb["ts"] < b["end"]:
                    continue
                if fk is not None and nb["ts"] >= fk:
                    exit_px, reason, exit_ts = nb["open"], "LAR-veto", nb["ts"]; break
                if nb["ts"] >= fl:
                    exit_px, reason, exit_ts = nb["open"], "flatten_1515", nb["ts"]; break
                if (d > 0 and nb["low"] <= stop) or (d < 0 and nb["high"] >= stop):
                    exit_px, reason, exit_ts = stop, "stop", nb["end"]; break
                if (d > 0 and nb["high"] >= tgt) or (d < 0 and nb["low"] <= tgt):
                    exit_px, reason, exit_ts = tgt, "target", nb["end"]; break
            if exit_px is None:
                exit_px, reason, exit_ts = cap["bars1"][-1]["close"], "flatten_1515", cap["bars1"][-1]["end"]
            gross = d * (exit_px - entry) / r_pts
            cost = cost_for(day, sym, b["end"], entry, ep["direction"], gross, r_pts,
                            analysis_root=analysis_root)
            out["trades"].append({"day": day, "sym": sym,
                                  "time": rec["time"], "direction": ep["direction"],
                                  "entry": round(entry, 2), "exit": round(exit_px, 2),
                                  "reason": reason, "gross_r": round(gross, 3),
                                  **cost, "gate_class": rec["gate_class"],
                                  "r_pts": round(r_pts, 2)})
            position_until = exit_ts or fl
    return out
