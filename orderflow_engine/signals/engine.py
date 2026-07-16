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


def momentum_flow_flags(md: dict, side: str, cvd_slope: float,
                        ofi: float | None, ofi_enabled: bool) -> dict:
    """Momentum-death flow flags — each True means flow turned AGAINST the OPEN
    position (SIDE-AWARE; a winning position is never flagged). Only genuinely-LIVE
    signals are emitted, so the death-count denominator is honest:
      * ``cvd_flip`` — CVD slope against the position (long: slope<0, short: slope>0).
      * ``ofi_flip`` — per-bar book-OFI against the position; emitted ONLY when depth
        OFI is enabled (else omitted, so it cannot be counted).
    DROPPED (not emitted) until each is real — do NOT re-add without raising
    conditions_required to match:
      * velocity_die — was ``not velocity_spike``, true ~94% of bars because the spike
        threshold is UNCALIBRATED: an always-on constant, not a death signal.
      * big_print_opposite — big-print detection is INERT (notional_threshold=0) → can
        never fire.
      * level_reject — needs level context threaded into the sim; not built.
    Consequence: with OFI off only ``cvd_flip`` is live (1 flag) < conditions_required
    (2), so momentum-death is DORMANT — stop/partial/trail/sleeper carry the exits —
    until OFI (or another calibrated signal) brings a 2nd live flag online."""
    sign = 1 if side == "long" else -1
    flags: dict = {}
    if md.get("cvd_flip", True):
        flags["cvd_flip"] = (cvd_slope * sign) < 0
    if md.get("ofi_flip", True) and ofi_enabled:
        flags["ofi_flip"] = (float(ofi or 0.0) * sign) < 0
    return flags


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
        self._atr_tr: dict[int, deque] = {}          # rolling True Range per sid
        self._atr_prev_close: dict[int, float] = {}
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
                                      bar["close"], self._flow_flags(sid, bar, pos.p.side)))
            if outcome is not None:
                self._close_position(sid, outcome)
        # 2) trend MA
        maq = self._ma.setdefault(sid, deque(maxlen=int(self.cfg.regime["trend_ma_bars"])))
        maq.append(bar["close"])
        # 2b) rolling ATR (True Range over atr_bars) — the stop-floor input. Updated
        # through the current bar so a fire on this bar sees ATR incl. this bar.
        self._update_atr(sid, bar)
        # 3) evaluate a fresh candidate
        self._evaluate(sid, bar, ts)

    def _update_atr(self, sid: int, bar: dict) -> None:
        prev = self._atr_prev_close.get(sid)
        h, l, c = bar["high"], bar["low"], bar["close"]
        tr = (h - l) if prev is None else max(h - l, abs(h - prev), abs(l - prev))
        q = self._atr_tr.setdefault(
            sid, deque(maxlen=int(self.cfg.exits.get("atr_bars", 14))))
        q.append(tr)
        self._atr_prev_close[sid] = c

    def _atr(self, sid: int) -> float | None:
        q = self._atr_tr.get(sid)
        return (sum(q) / len(q)) if q else None

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

    def _flow_flags(self, sid: int, bar: dict, side: str) -> dict:
        """Side-aware momentum-death flags for the OPEN position (see
        ``momentum_flow_flags``). ``side`` is the position's side, so a winning
        position is never flagged as dying."""
        return momentum_flow_flags(
            self.cfg.exits.get("momentum_death", {}), side,
            bar.get("cvd_slope", 0.0), bar.get("ofi"),
            self.tape.cfg.depth_ofi_enabled)

    # -- context builders ----------------------------------------------------
    def _build_context(self, sid: int, bar: dict, ts: int) -> SignalContext:
        m = self.meta.get(sid, {})
        index = m.get("index", "")
        st_t = self.tape.state.get(sid)
        ctx = SignalContext(
            instrument=m.get("symbol", str(sid)), index=index, sid=sid, ts_ns=ts,
            price=bar["close"], session_start_ns=self._first_ts or 0,
            cvd=(st_t.cvd.running if st_t else 0.0), cvd_slope=bar.get("cvd_slope", 0.0),
            book_ofi=(bar.get("ofi") if self.tape.cfg.depth_ofi_enabled else None),
            bar_delta=bar.get("delta", 0), bar_high=bar.get("high"), bar_low=bar.get("low"),
            velocity_spike=bool(bar.get("velocity_spike")),
            velocity_ratio=bar.get("velocity_ratio"),
            vix=self.vix, ma_slope=self._ma_slope(sid), atr=self._atr(sid),
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
