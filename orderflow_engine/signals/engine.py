"""SignalEngine (Module R6) — the brain, a replayer Consumer.

Runs LAST in the composite (after tape/levels/chain have updated for a packet). On
each tick-bar close of a tradeable instrument it: builds a live SignalContext from
R3/R4/R5 state, computes the regime, scores long + short, applies the asymmetric
gate + entry gates, and — on a fire — builds a Brahmastra-2.0 exit plan and opens a
simulated position. Every candidate is logged (glass box); open positions are
stepped bar-by-bar to a deterministic R outcome.
"""

from __future__ import annotations

import json
from collections import deque
from datetime import date

from chain import analytics as chain_analytics
from chain import gex as chain_gex

from signals.config import SignalConfig
from signals.context import SignalContext
from signals.exits import SimBar, SimPosition, build_exit_plan
from signals.gates import GateState, apply_gates
from signals.regime import apply_asymmetric, compute_regime
from signals.scorer import evaluate

_BIG_PRINT_KINDS = {"BIG_PRINT", "BIG_PRINT_CLUSTER"}


class SignalEngine:
    def __init__(self, cfg: SignalConfig, tape, levels, chain, meta_by_id: dict[int, dict],
                 session_date: date, events: list | None = None,
                 daily_levels: dict[int, dict] | None = None,
                 sides: tuple[str, ...] = ("long", "short")):
        self.cfg = cfg
        self.tape, self.levels, self.chain = tape, levels, chain
        self.meta = meta_by_id
        self.session_date = session_date
        self.events = events or []
        self.daily_levels = daily_levels or {}
        self.sides = sides
        # tradeable sid <-> symbol
        self.sym_by_id = {sid: m.get("symbol", "") for sid, m in meta_by_id.items()}
        want = set(cfg.tradeable)
        self.tradeable = {sid for sid, m in meta_by_id.items() if m.get("symbol") in want}
        self.vix_sid = next((sid for sid, m in meta_by_id.items()
                             if m.get("symbol") == "INDIA_VIX"), None)
        # per-instrument state
        self._last_bars: dict[int, int] = {}
        self._ma: dict[int, deque] = {}
        self._gate: dict[int, GateState] = {}
        self._pos: dict[int, SimPosition] = {}
        self._pos_row: dict[int, dict] = {}
        self.vix: float | None = None
        self.rows: list[dict] = []
        self.fires: list[dict] = []
        self.counts = {"candidates": 0, "fired": 0}
        self.gate_rejects: dict[str, int] = {}
        self._first_ts: int | None = None

    # -- consumer contract ---------------------------------------------------
    def on_packet(self, parsed: dict, ts: int) -> None:
        if not parsed.get("is_tick"):
            return
        if self._first_ts is None:
            self._first_ts = ts
        sid = parsed.get("security_id")
        if sid == self.vix_sid and parsed.get("ltp") is not None:
            self.vix = float(parsed["ltp"])
        for tsid in self.tradeable:
            st = self.tape.state.get(tsid)
            if st is None:
                continue
            if st.bars != self._last_bars.get(tsid, 0):
                self._last_bars[tsid] = st.bars
                bar = self._last_tick_bar(tsid)
                if bar is not None:
                    self._on_new_bar(tsid, bar, ts)

    def on_depth(self, parsed, ts):  # noqa: D401 - depth handled by R5
        pass

    def on_event(self, kind, detail, value_num):
        pass

    # -- per-bar -------------------------------------------------------------
    def _last_tick_bar(self, sid: int) -> dict | None:
        for r in reversed(self.tape.bar_rows):
            if r["security_id"] == sid and r["bar_type"] == "tick":
                return r
        return None

    def _gate_state(self, sid: int) -> GateState:
        gs = self._gate.get(sid)
        if gs is None:
            m = self.meta.get(sid, {})
            dte = self._days_to_expiry(m.get("expiry"))
            gs = GateState(session_start_ns=self._first_ts or 0,
                           is_expiry_day=(dte == 0), events=self.events)
            self._gate[sid] = gs
        return gs

    def _days_to_expiry(self, expiry) -> int | None:
        try:
            return (date.fromisoformat(expiry) - self.session_date).days
        except (ValueError, TypeError):
            return None

    def _on_new_bar(self, sid: int, bar: dict, ts: int) -> None:
        # 1) step an open simulated position on the new bar
        pos = self._pos.get(sid)
        if pos is not None and not pos.closed:
            outcome = pos.step(SimBar(bar["end_ts_ns"], bar["high"], bar["low"],
                                      bar["close"], self._flow_flags(sid, bar)))
            if outcome is not None:
                self._close_position(sid, outcome)
        # 2) trend MA
        maq = self._ma.setdefault(sid, deque(maxlen=int(self.cfg.regime["trend_ma_bars"])))
        maq.append(bar["close"])
        # 3) evaluate a fresh candidate
        self._evaluate(sid, bar, ts)

    def _evaluate(self, sid: int, bar: dict, ts: int) -> None:
        ctx = self._build_context(sid, bar, bar["end_ts_ns"])
        reg = compute_regime(ctx, self.cfg)
        ctx.regime_direction, ctx.regime_vol_band = reg.direction, reg.vol_band
        scored = evaluate(ctx, self.cfg)
        gs = self._gate_state(sid)
        for side in self.sides:
            s = scored[side]
            base_thr = s["threshold"]
            adj_thr = self._asymmetric_threshold(base_thr, side, reg)
            allow, reason = apply_gates(ctx, gs, self.cfg)
            fired = adj_thr < 999_999 and s["score"] >= adj_thr and allow
            row = {
                "ts_ns": ctx.ts_ns, "index": ctx.index, "instrument": ctx.instrument,
                "side": side, "price": ctx.price, "score": s["score"],
                "threshold": adj_thr, "base_threshold": base_thr, "fired": fired,
                "gate_reason": "" if allow else reason,
                "regime_direction": reg.direction, "regime_vol_band": reg.vol_band,
                "breakdown": json.dumps(s["breakdown"], sort_keys=True),
                "entry": None, "stop": None, "target": None, "r_value": None,
                "exit_reason": None, "realized_r": None,
            }
            self.counts["candidates"] += 1
            if not allow:
                self.gate_rejects[reason] = self.gate_rejects.get(reason, 0) + 1
            if fired:
                self._fire(sid, ctx, side, row, gs)
            self.rows.append(row)

    def _asymmetric_threshold(self, base: float, side: str, reg) -> float:
        return apply_asymmetric(base, side, reg.direction, self.cfg.asymmetric_gate)

    def _fire(self, sid: int, ctx, side: str, row: dict, gs: GateState) -> None:
        plan = build_exit_plan(ctx, self.cfg, side)
        pos = SimPosition(plan, ctx.ts_ns)
        self._pos[sid] = pos
        self._pos_row[sid] = row
        row.update(entry=plan.entry, stop=plan.stop, target=plan.target_1r,
                   r_value=plan.r_value)
        gs.trades_today += 1
        gs.has_open_position = True
        gs.last_signal_ts_ns = ctx.ts_ns
        self.counts["fired"] += 1
        self.fires.append({"instrument": ctx.instrument, "side": side, "ts_ns": ctx.ts_ns,
                           "score": row["score"], "entry": plan.entry})

    def _close_position(self, sid: int, outcome) -> None:
        row = self._pos_row.get(sid)
        if row is not None:
            row["exit_reason"] = outcome.exit_reason
            row["realized_r"] = outcome.realized_r
        gs = self._gate.get(sid)
        if gs is not None:
            gs.has_open_position = False
        self._pos.pop(sid, None)
        self._pos_row.pop(sid, None)

    def _flow_flags(self, sid: int, bar: dict) -> dict:
        md = self.cfg.exits.get("momentum_death", {})
        st = self.tape.state.get(sid)
        cvd_slope = bar.get("cvd_slope", 0.0)
        return {
            "cvd_flip": bool(md.get("cvd_flip")) and cvd_slope < 0,
            "velocity_die": bool(md.get("velocity_die")) and not bar.get("velocity_spike"),
            "big_print_opposite": False,   # wired; refined once depth/flow direction is calibrated
            "ofi_flip": False,             # STUB until R1 depth
            "level_reject": False,
        }

    # -- context builders ----------------------------------------------------
    def _build_context(self, sid: int, bar: dict, ts: int) -> SignalContext:
        m = self.meta.get(sid, {})
        index = m.get("index", "")
        st_t = self.tape.state.get(sid)
        ctx = SignalContext(
            instrument=m.get("symbol", str(sid)), index=index, sid=sid, ts_ns=ts,
            price=bar["close"], session_start_ns=self._first_ts or 0,
            cvd=(st_t.cvd.running if st_t else 0.0), cvd_slope=bar.get("cvd_slope", 0.0),
            bar_delta=bar.get("delta", 0), bar_high=bar.get("high"), bar_low=bar.get("low"),
            velocity_spike=bool(bar.get("velocity_spike")),
            velocity_ratio=bar.get("velocity_ratio"),
            vix=self.vix, ma_slope=self._ma_slope(sid),
            days_to_expiry=self._days_to_expiry(m.get("expiry")),
        )
        ctx.recent_big_print_side = self._recent_print_side(sid, ts)
        self._fill_levels(ctx, sid)
        self._fill_chain(ctx, index)
        return ctx

    def _ma_slope(self, sid: int) -> float | None:
        q = self._ma.get(sid)
        if not q or len(q) < 2:
            return None
        return (q[-1] - q[0]) / (len(q) - 1)

    def _recent_print_side(self, sid: int, ts: int) -> int | None:
        window = int(float(self.cfg.param("big_print_window_s", 30)) * 1e9)
        found = None
        for e in reversed(self.tape.event_rows):
            if e.get("security_id") != sid:
                continue
            if e["kind"] in _BIG_PRINT_KINDS and ts - e["ts_ns"] <= window:
                found = e.get("side")
                break
        return found

    def _fill_levels(self, ctx: SignalContext, sid: int) -> None:
        st_l = self.levels.state.get(sid)
        if st_l is None:
            return
        reg = self.levels.build_registry(st_l)
        for lt, price in self.daily_levels.get(sid, {}).items():
            reg.add(lt, price)
        ctx.registry = reg
        snap = st_l.vwap.snapshot()
        if snap is not None:
            ctx.vwap, ctx.vwap_bands = snap.vwap, snap.bands
        prof = st_l.profile.result(self.levels.cfg.value_area_pct)
        ctx.poc, ctx.vah, ctx.val = prof.poc, prof.vah, prof.val
        ctx.ib_high, ctx.ib_low = st_l.ib_high, st_l.ib_low

    def _fill_chain(self, ctx: SignalContext, index: str) -> None:
        rows = [r for r in self.chain.rows if r["index"] == index]
        if not rows:
            return
        last_ts = max(r["snapshot_ts_ns"] for r in rows)
        dedup = {}
        for r in rows:
            if r["snapshot_ts_ns"] == last_ts:
                dedup[(r["right"], r["strike"])] = r
        fr = list(dedup.values())
        cs = self.chain.cfg.contract_size(index)
        spot = self.chain.spot.get(index, (None,))[0]
        ctx.net_gex = chain_gex.net_gex(fr, cs)
        ctx.gamma_flip = chain_gex.gamma_flip(fr, cs)
        ctx.pcr_oi = chain_analytics.pcr_oi(fr)
        ctx.max_pain = chain_analytics.max_pain(fr)
        ctx.atm_iv = chain_analytics.atm_iv(fr, spot)

    # -- finalize ------------------------------------------------------------
    def finalize(self) -> dict:
        for sid, pos in list(self._pos.items()):
            if not pos.closed:
                bar = self._last_tick_bar(sid)
                px = bar["close"] if bar else pos.p.entry
                self._close_position(sid, pos.force_close(pos.entry_ts, px))
        net_r = sum(r["realized_r"] for r in self.rows if r["realized_r"] is not None)
        return {
            "instruments": len(self.tradeable),
            "counts": dict(self.counts),
            "gate_rejects": dict(self.gate_rejects),
            "net_simulated_r": round(net_r, 4),
            "fires": self.fires,
            "uncalibrated_knobs": self.cfg.uncalibrated(),
        }
