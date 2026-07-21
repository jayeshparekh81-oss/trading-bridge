"""LAR STUDY MODE (P7, 2026-07-21) — reference-level state machine, COUNTING ONLY.

Per instrument, per reference level (PDH, PDL, ORH, ORL — OR reuses R4's INITIAL BALANCE
definition, levels/engine.py:33/76/115, so no second opening-range definition exists),
a strictly causal state machine:

  FAR → APPROACHING → TOUCHED → SWEPT → ABSORPTION_CANDIDATE → FLOW_FLIPPED
      → RECLAIMED → ARMED → TRIGGERED | FAILED | EXPIRED

No trading, no weights, no scorer/config change: TRIGGERED records a VIRTUAL marker only
(trigger price, stop = sweep extreme, forward gross R at fixed horizons; net R is emitted
ONLY when chain cost inputs are supplied — never estimated, absent = flagged).

THRESHOLD DEFAULTS (STUDY_CONFIG below) are reasoned from EXISTING config conventions —
ATR windows (exits.atr_bars 14, min_stop_atr 0.3), the 2-tick convention
(exits.stop_slippage_ticks 2), 20-bar baselines (velocity/cvd/regime windows), and
percentile cuts (bigprint's percentile machinery) — not invented magic numbers. The full
config block is logged into EVERY output file.

Absorption inputs REUSE P5 (research.price_efficiency.rolling_efficiency) and P6
(research.depth_proxies.DepthProxyEngine + aggregate) — never duplicated. Depth-less days
run with data_quality='no_depth' (absorption uses P5-only, flagged per transition).

DEFAULT OFF: computed only via this module/CLI; NEW analysis/<day>/lar_study_<sym>.json
files + one cross-day summary; nothing in the pipeline reads any of it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

NS = 1_000_000_000

STUDY_CONFIG = {
    # transition thresholds — every value carries its reasoning
    "approach_atr": 0.5,        # within 0.5×ATR14 of the level = APPROACHING (ATR14 = exits.atr_bars; half the stop-floor convention 0.3 is too tight for an approach zone)
    "touch_ticks": 2,           # within 2 ticks = TOUCHED (the repo's 2-tick convention: exits.stop_slippage_ticks)
    "sweep_min_ticks": 2,       # extreme pierces >= 2 ticks beyond the level = SWEPT (same convention)
    "sweep_max_atr": 1.0,       # pierce deeper than 1×ATR = breakout regime, not a sweep -> FAILED
    "elevated_vol_mult": 1.5,   # sweep bar volume >= 1.5× rolling-20 median = elevated activity (20-bar baseline family: velocity.baseline_bars)
    "low_eff_pct": 0.25,        # P5 aligned rolling efficiency <= p25 of session-so-far = low-efficiency (absorption evidence; percentile-cut convention from bigprint)
    "defense_refills_min": 1,   # >=1 P6 refill event on the defense side in the rolling window = depth-hold evidence (skipped+flagged when no depth)
    "reclaim_K": 3,             # 3 consecutive closes back on the defense side = RECLAIMED (persistence, not a single print)
    "trigger_ticks": 1,         # break of the ARMED bar's micro swing by >= 1 tick = TRIGGERED
    "tick": 0.05,
    # expiry timers (bars, tick-100): generous multiples of the 20-bar baseline
    "approach_expiry_bars": 20,
    "sweep_to_absorption_bars": 10,
    "absorption_to_flip_bars": 10,
    "flip_to_reclaim_bars": 10,
    "armed_expiry_bars": 10,
    "total_expiry_bars": 60,
    "horizons_bars": [5, 10, 20],   # forward gross-R marks for TRIGGERED (virtual only)
    "eff_window": 10, "proxy_window": 10, "atr_bars": 14, "vol_median_bars": 20,
}

SUPPORT = {"PDL", "ORL"}            # sweep DOWN, reclaim UP, long trigger
RESISTANCE = {"PDH", "ORH"}         # mirror short

ORDER = ["FAR", "APPROACHING", "TOUCHED", "SWEPT", "ABSORPTION_CANDIDATE",
         "FLOW_FLIPPED", "RECLAIMED", "ARMED", "TRIGGERED", "FAILED", "EXPIRED"]


@dataclass
class Transition:
    ts_ns: int
    old: str
    new: str
    reason: str
    snapshot: dict
    data_quality: str = "ok"


@dataclass
class LevelMachine:
    level_name: str
    level_price: float
    cfg: dict = field(default_factory=lambda: dict(STUDY_CONFIG))
    state: str = "FAR"
    transitions: list = field(default_factory=list)
    _bars_in_seq: int = 0
    _bars_in_state: int = 0
    _sweep_extreme: Optional[float] = None
    _reclaim_run: int = 0
    _armed_swing: Optional[float] = None
    outcome: Optional[dict] = None            # set on TRIGGERED (virtual marker)

    def _is_support(self) -> bool:
        return self.level_name in SUPPORT

    def _move(self, ts, new, reason, snap, dq="ok"):
        self.transitions.append(Transition(ts, self.state, new, reason, snap, dq))
        self.state = new
        self._bars_in_state = 0

    def terminal(self) -> bool:
        return self.state in ("TRIGGERED", "FAILED", "EXPIRED")

    def on_bar(self, f: dict) -> None:
        """f: causal per-bar features — ts, open/high/low/close, atr, vol, vol_med20,
        delta, book_ofi (None ok), eff_up_w, eff_dn_w, eff_p25_aligned (session-so-far),
        refills_w_bid, refills_w_ask, has_depth."""
        if self.terminal():
            return
        c = self.cfg
        L = self.level_price
        sup = self._is_support()
        tick = c["tick"]
        dq = "ok" if f.get("has_depth") else "no_depth"
        self._bars_in_seq += 1 if self.state != "FAR" else 0
        self._bars_in_state += 1
        if self.state != "FAR" and self._bars_in_seq > c["total_expiry_bars"]:
            self._move(f["ts"], "EXPIRED", f"total_expiry {c['total_expiry_bars']} bars", f, dq)
            return
        dist = abs(f["close"] - L)
        pierced = (L - f["low"]) if sup else (f["high"] - L)          # how far beyond the level
        eff_aligned = f["eff_dn_w"] if sup else f["eff_up_w"]         # efficiency of the BREAK side
        defense_refills = f["refills_w_bid"] if sup else f["refills_w_ask"]
        flip_dir = 1 if sup else -1                                   # flow toward reclaim side

        if self.state == "FAR":
            if f["atr"] and dist <= c["approach_atr"] * f["atr"]:
                self._move(f["ts"], "APPROACHING", f"dist {dist:.2f} <= {c['approach_atr']}*ATR", f, dq)
                self._bars_in_seq = 1
        elif self.state == "APPROACHING":
            if dist <= c["touch_ticks"] * tick or pierced > 0:
                self._move(f["ts"], "TOUCHED", f"within {c['touch_ticks']} ticks", f, dq)
            elif self._bars_in_state > c["approach_expiry_bars"]:
                self._move(f["ts"], "FAR", "approach_expiry (re-set, not terminal)", f, dq)
                self._bars_in_seq = 0
        elif self.state == "TOUCHED":
            if pierced >= c["sweep_min_ticks"] * tick:
                if f["atr"] and pierced > c["sweep_max_atr"] * f["atr"]:
                    self._move(f["ts"], "FAILED", f"pierce {pierced:.2f} > {c['sweep_max_atr']}*ATR = breakout not sweep", f, dq)
                else:
                    self._sweep_extreme = f["low"] if sup else f["high"]
                    self._move(f["ts"], "SWEPT", f"pierced {pierced:.2f} (>= {c['sweep_min_ticks']} ticks)", f, dq)
            elif self._bars_in_state > c["approach_expiry_bars"]:
                self._move(f["ts"], "EXPIRED", "touched but never swept (timer)", f, dq)
        elif self.state == "SWEPT":
            self._sweep_extreme = min(self._sweep_extreme, f["low"]) if sup else max(self._sweep_extreme, f["high"])
            elevated = f["vol"] >= c["elevated_vol_mult"] * max(f["vol_med20"], 1.0)
            low_eff = f["eff_p25_aligned"] is not None and eff_aligned is not None \
                and eff_aligned <= f["eff_p25_aligned"]
            depth_hold = (defense_refills or 0) >= c["defense_refills_min"] if f.get("has_depth") else False
            if low_eff and (elevated or depth_hold):
                why = f"low_eff(<=p25) + {'depth_refill' if depth_hold else 'elevated_vol'}"
                self._move(f["ts"], "ABSORPTION_CANDIDATE", why, f, dq)
            elif self._bars_in_state > c["sweep_to_absorption_bars"]:
                self._move(f["ts"], "FAILED", "no absorption within window (efficient break)", f, dq)
        elif self.state == "ABSORPTION_CANDIDATE":
            ofi_flip = f.get("book_ofi") is not None and (f["book_ofi"] * flip_dir) > 0
            delta_flip = (f["delta"] * flip_dir) > 0
            if ofi_flip or delta_flip:
                src = "book_ofi" if ofi_flip else "delta"
                self._move(f["ts"], "FLOW_FLIPPED", f"flow flipped toward reclaim via {src}", f,
                           dq if ofi_flip else ("delta_only" if dq == "ok" else dq))
            elif self._bars_in_state > c["absorption_to_flip_bars"]:
                self._move(f["ts"], "FAILED", "absorption without flow flip (timer)", f, dq)
        elif self.state == "FLOW_FLIPPED":
            back_inside = (f["close"] > L) if sup else (f["close"] < L)
            self._reclaim_run = self._reclaim_run + 1 if back_inside else 0
            if self._reclaim_run >= c["reclaim_K"]:
                self._move(f["ts"], "RECLAIMED", f"{c['reclaim_K']} consecutive closes back inside", f, dq)
            elif self._bars_in_state > c["flip_to_reclaim_bars"]:
                self._move(f["ts"], "FAILED", "flip without reclaim (timer)", f, dq)
        elif self.state == "RECLAIMED":
            holds = (f["low"] >= L) if sup else (f["high"] <= L)      # retest holds the level
            if holds:
                self._armed_swing = f["high"] if sup else f["low"]
                self._move(f["ts"], "ARMED", "retest holds level; micro swing set", f, dq)
            elif ((f["close"] < L) if sup else (f["close"] > L)):
                self._move(f["ts"], "FAILED", "reclaim lost (close back beyond level)", f, dq)
        elif self.state == "ARMED":
            trig = self._armed_swing + c["trigger_ticks"] * tick if sup \
                else self._armed_swing - c["trigger_ticks"] * tick
            hit = (f["high"] >= trig) if sup else (f["low"] <= trig)
            if hit:
                self.outcome = {"trigger_ts": f["ts"], "trigger_price": round(trig, 2),
                                "stop": round(self._sweep_extreme, 2), "side": "long" if sup else "short",
                                "r_unit": round(abs(trig - self._sweep_extreme), 2)}
                self._move(f["ts"], "TRIGGERED", f"micro swing break @ {trig:.2f}", f, dq)
            elif ((f["close"] < L) if sup else (f["close"] > L)):
                self._move(f["ts"], "FAILED", "armed but level lost", f, dq)
            elif self._bars_in_state > c["armed_expiry_bars"]:
                self._move(f["ts"], "EXPIRED", "armed_expiry (no trigger)", f, dq)


def forward_r(outcome: dict, bars: list[dict], trigger_idx: int, horizons: list[int]) -> dict:
    """Virtual forward marks: gross R at fixed horizons; stop = sweep extreme (marker only —
    NOT an order; no partial/trail machinery, deliberately simpler than the sim)."""
    r_unit = max(outcome["r_unit"], 1e-9)
    sgn = 1 if outcome["side"] == "long" else -1
    out = {}
    for h in horizons:
        j = trigger_idx + h
        if j >= len(bars):
            out[f"r_{h}b"] = None
            continue
        out[f"r_{h}b"] = round(sgn * (bars[j]["close"] - outcome["trigger_price"]) / r_unit, 3)
    return out


def snapshot_of(f: dict) -> dict:
    keep = ("close", "atr", "vol", "delta", "book_ofi", "eff_up_w", "eff_dn_w",
            "refills_w_bid", "refills_w_ask")
    return {k: f.get(k) for k in keep}


# ---------------------------------------------------------------- day driver (CLI)
def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="research.lar_study")
    ap.add_argument("--date", required=True)
    ap.add_argument("--instruments", default="NIFTY_FUT,BANKNIFTY_FUT")
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv[1:])
    import glob as _glob
    import pyarrow.parquet as pq
    from recorder.depth_schema import SIDE_BID
    from replayer.engine import ReplayEngine
    from replayer.source import ReplaySource
    from tape.config import load_tape_config
    from tape.engine import TapeEngine
    from tape.trades import TradeExtractor
    from levels.config import load_levels_config
    from signals.pipeline import build_meta
    from research.price_efficiency import rolling_efficiency
    from research.depth_proxies import DepthProxyEngine, aggregate, snapshot_to_book

    root = Path(args.root)
    dd = root / "data" / args.date
    meta = build_meta(dd)
    sym = {s: m["symbol"] for s, m in meta.items()}
    sid_by = {v: k for k, v in sym.items()}
    insts = [s.strip() for s in args.instruments.split(",") if s.strip()]
    has_depth = (dd / "depth").exists() and any((dd / "depth").iterdir())
    ib_min = load_levels_config().initial_balance_minutes

    tape = TapeEngine(load_tape_config(), sym)
    dpe: dict[int, DepthProxyEngine] = {}
    extract: dict[int, TradeExtractor] = {}
    for s in insts:
        sid = sid_by.get(s)
        if sid is not None:
            dpe[sid] = DepthProxyEngine()
            extract[sid] = TradeExtractor()

    class _C:
        def on_packet(self, parsed, ts):
            tape.on_packet(parsed, ts)
            sid = parsed.get("security_id")
            if parsed.get("is_tick") and sid in dpe:
                tr = extract[sid].on_tick(parsed)
                if tr is not None:
                    dpe[sid].on_trade(tr.ts_ns, tr.price, tr.size)
        def on_depth(self, parsed, ts):
            tape.on_depth(parsed, ts)
            sid = parsed.get("security_id")
            if sid in dpe:
                dpe[sid].on_snapshot(ts, "bid" if parsed.get("side") == SIDE_BID else "ask",
                                     snapshot_to_book(parsed))
        def on_event(self, k, d, v):
            tape.on_event(k, d, v)

    ReplayEngine(ReplaySource(dd, instruments=insts)).drive(_C(), speed="max")

    def prior_day_hl(inst):
        days = sorted(p.name for p in (root / "data").iterdir()
                      if p.is_dir() and p.name < args.date)
        for d in reversed(days):
            files = _glob.glob(str(root / "data" / d / f"{inst}_*.parquet"))
            if not files:
                continue
            t = pq.read_table(files[0], columns=["ts_recv_ns", "ltp"]).to_pydict()
            pairs = [(a, b) for a, b in zip(t["ts_recv_ns"], t["ltp"]) if b is not None]
            if pairs:
                return d, max(v for _, v in pairs), min(v for _, v in pairs)
        return None, None, None

    for s in insts:
        sid = sid_by.get(s)
        bars = sorted([b for b in tape.bar_rows
                       if b["security_id"] == sid and b["bar_type"] == "tick"],
                      key=lambda b: b["end_ts_ns"])
        if not bars:
            print(f"{s}: no bars — skipped")
            continue
        eff = rolling_efficiency(bars, window=STUDY_CONFIG["eff_window"])
        prows = aggregate(dpe[sid].events, [(b["start_ts_ns"], b["end_ts_ns"]) for b in bars],
                          window=STUDY_CONFIG["proxy_window"]) if has_depth else None
        pd_day, pdh, pdl = prior_day_hl(s)
        session0 = bars[0]["start_ts_ns"]
        ib_end = session0 + ib_min * 60 * NS
        orh = orl = None
        feats: list[dict] = []
        trs: list[float] = []
        vols: list[float] = []
        prev_close = None
        eff_hist: list[float] = []
        for i, b in enumerate(bars):
            tr = (b["high"] - b["low"]) if prev_close is None else \
                max(b["high"] - b["low"], abs(b["high"] - prev_close), abs(b["low"] - prev_close))
            trs.append(tr)
            prev_close = b["close"]
            vols.append(float(b["volume"]))
            atr = sum(trs[-STUDY_CONFIG["atr_bars"]:]) / min(len(trs), STUDY_CONFIG["atr_bars"])
            vm = sorted(vols[-STUDY_CONFIG["vol_median_bars"]:])
            vol_med = vm[len(vm) // 2]
            if b["end_ts_ns"] <= ib_end:
                orh = b["high"] if orh is None else max(orh, b["high"])
                orl = b["low"] if orl is None else min(orl, b["low"])
            e = eff[i]
            f = {"ts": b["end_ts_ns"], "open": b["open"], "high": b["high"], "low": b["low"],
                 "close": b["close"], "atr": atr, "vol": float(b["volume"]), "vol_med20": vol_med,
                 "delta": b["delta"], "book_ofi": None,       # OFI OFF on disk — honest None
                 "eff_up_w": e["up_w"], "eff_dn_w": e["dn_w"],
                 "refills_w_bid": (prows[i]["bid_refills_w"] if prows else None),
                 "refills_w_ask": (prows[i]["ask_refills_w"] if prows else None),
                 "has_depth": bool(has_depth), "ib_fixed": b["end_ts_ns"] > ib_end,
                 "orh": orh, "orl": orl}
            eff_hist.append(min(e["up_w"], e["dn_w"]))
            s_hist = sorted(eff_hist)
            f["eff_p25_aligned"] = s_hist[max(0, int(0.25 * (len(s_hist) - 1)))] if len(s_hist) >= 20 else None
            feats.append(f)
        machines: dict[str, LevelMachine] = {}
        if pdh:
            machines["PDH"] = LevelMachine("PDH", round(pdh, 2))
            machines["PDL"] = LevelMachine("PDL", round(pdl, 2))
        results = {}
        trig_idx: dict[str, int] = {}
        for i, f in enumerate(feats):
            if f["ib_fixed"] and "ORH" not in machines and f["orh"] is not None:
                machines["ORH"] = LevelMachine("ORH", round(f["orh"], 2))
                machines["ORL"] = LevelMachine("ORL", round(f["orl"], 2))
            for name, m in machines.items():
                pre = m.state
                m.on_bar(f)
                if m.state == "TRIGGERED" and pre != "TRIGGERED":
                    trig_idx[name] = i
        for name, m in machines.items():
            entry = {"level": name, "price": m.level_price, "final_state": m.state,
                     "transitions": [{"ts_ns": t.ts_ns, "old": t.old, "new": t.new,
                                      "reason": t.reason, "data_quality": t.data_quality,
                                      "snapshot": snapshot_of(t.snapshot)}
                                     for t in m.transitions]}
            if m.outcome:
                fr = forward_r(m.outcome, feats, trig_idx[name], STUDY_CONFIG["horizons_bars"])
                entry["virtual_outcome"] = {**m.outcome, **fr,
                                            "net_note": "net R requires chain cost inputs — not estimated"}
            results[name] = entry
        out = root / "analysis" / args.date / f"lar_study_{s}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"day": args.date, "symbol": s, "study_config": STUDY_CONFIG,
                                   "prior_day_used": pd_day, "ib_minutes": ib_min,
                                   "data_quality": "ok" if has_depth else "no_depth",
                                   "levels": results}))
        states = {n: r["final_state"] for n, r in results.items()}
        print(f"{s}: levels={states} -> {out}")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
