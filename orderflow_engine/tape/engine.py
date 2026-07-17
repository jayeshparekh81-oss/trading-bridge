"""TapeEngine (Module R3) — a replayer Consumer that builds analysis primitives.

Implements the R2 consumer contract (on_packet / on_depth / on_event). Per
instrument it runs: trade extraction -> classification -> event-time bars ->
CVD + slope + velocity per bar, and big-print detection per trade. Depth packets
feed the (inert-by-default) imbalance/OFI hooks. Deterministic: given the
replayer's deterministic stream, the emitted bars/events are identical every run.
"""

from __future__ import annotations

from recorder.depth_schema import SIDE_ASK, SIDE_BID

import json

from tape.bars import TICK, VOLUME, BarBuilder
from tape.bigprint import BigPrintDetector
from tape.config import TapeConfig
from tape.cvd import CVD, SlopeSeries
from tape.depth_imbalance import book_ofi, book_ok
from tape.footprint import detect_stacked_imbalance
from tape.trades import TradeExtractor
from tape.velocity import TapeVelocity


class _InstrumentState:
    def __init__(self, sid: int, symbol: str, cfg: TapeConfig):
        self.sid = sid
        self.symbol = symbol
        self.extractor = TradeExtractor(cfg.trade_size_mode, cfg.classify_method)
        fp_bin = cfg.footprint_bin_size(symbol)
        self.builders = [BarBuilder(TICK, tick_size=cfg.tick_bar_size, footprint_bin_size=fp_bin)]
        vt = cfg.volume_bar_threshold(symbol)
        if cfg.volume_bar_enabled and vt > 0:
            self.builders.append(BarBuilder(VOLUME, volume_threshold=vt, footprint_bin_size=fp_bin))
        self.cvd = CVD()
        self.slope = {b.bar_type: SlopeSeries(cfg.cvd_slope_window) for b in self.builders}
        self.velocity = {b.bar_type: TapeVelocity(cfg.velocity_baseline_bars,
                                                  cfg.velocity_spike_ratio)
                         for b in self.builders}
        self.bigprint = BigPrintDetector(cfg.bigprint_notional(symbol),
                                         cfg.cluster_k, cfg.cluster_window_s,
                                         mode=cfg.bigprint_mode,
                                         percentile=cfg.bigprint_percentile,
                                         lookback=cfg.bigprint_lookback,
                                         min_samples=cfg.bigprint_min_samples)
        self.trades = 0
        self.bars = 0
        self.big_prints = 0
        self.velocity_spikes = 0
        self.stacked_imbalances = 0
        self.fp_bin = fp_bin
        # depth (R1)
        self.last_bid: dict | None = None
        self.last_ask: dict | None = None
        self.last_bid_ts: int | None = None
        self.last_ask_ts: int | None = None
        self.depth_packets = 0
        # book OFI (Cont/Kukanov/Stoikov, L1) — cumulative accumulator + a
        # per-bar-type baseline so each bar emits its OWN net OFI (mirrors how
        # CVD's SlopeSeries samples the running CVD per bar_type). Inert (stays
        # 0.0) unless depth.ofi_enabled. prev-snapshot state drives the increment.
        self.ofi_running = 0.0
        self.ofi_base = {b.bar_type: 0.0 for b in self.builders}
        self.ofi_prev_bid: dict | None = None
        self.ofi_prev_ask: dict | None = None
        self.ofi_prev_ts: int | None = None
        self.ofi_snap_ts: int | None = None


class TapeEngine:
    def __init__(self, config: TapeConfig, sym_by_id: dict[int, str] | None = None):
        self.cfg = config
        self.sym_by_id = sym_by_id or {}
        self.state: dict[int, _InstrumentState] = {}
        self.bar_rows: list[dict] = []
        self.event_rows: list[dict] = []
        self.counts = {"ticks": 0, "trades": 0, "depth": 0, "events": 0}

    # -- consumer contract ---------------------------------------------------
    def _st(self, sid: int) -> _InstrumentState:
        st = self.state.get(sid)
        if st is None:
            st = _InstrumentState(sid, self.sym_by_id.get(sid, f"SID{sid}"), self.cfg)
            self.state[sid] = st
        return st

    def on_packet(self, parsed: dict, ts_recv_ns: int) -> None:
        if not parsed.get("is_tick"):
            return
        self.counts["ticks"] += 1
        sid = parsed.get("security_id")
        if sid is None:
            return
        st = self._st(int(sid))
        trade = st.extractor.on_tick(parsed)
        if trade is None:
            return
        self.counts["trades"] += 1
        st.trades += 1
        st.cvd.on_trade(trade)
        for ev in st.bigprint.on_trade(trade):
            st.big_prints += 0 if ev.is_cluster else 1
            self.event_rows.append(self._bigprint_row(st, ev))
        for builder in st.builders:
            bar = builder.on_trade(trade)
            if bar is not None:
                self._close_bar(st, bar)

    def on_depth(self, parsed: dict, ts_recv_ns: int) -> None:
        self.counts["depth"] += 1
        sid = parsed.get("security_id")
        if sid is None:
            return
        st = self._st(int(sid))
        st.depth_packets += 1
        side = parsed.get("side")
        if side == SIDE_BID:
            st.last_bid, st.last_bid_ts = parsed, ts_recv_ns
        elif side == SIDE_ASK:
            st.last_ask, st.last_ask_ts = parsed, ts_recv_ns
        else:
            return
        # Book OFI accumulation. INERT unless depth.ofi_enabled (default off), so
        # a disabled run is byte-identical to before. A book snapshot completes
        # when both sides are present at the SAME ts (Dhan sends bid+ask paired);
        # compute the L1 OFI increment vs the previous complete snapshot, skipping
        # empty/crossed books (book_ok) and increments across a lull larger than
        # ofi_gap_guard_s (the 2026-07-15 445s gap must not emit a spike).
        if not self.cfg.depth_ofi_enabled:
            return
        if (st.last_bid is None or st.last_ask is None
                or st.last_bid_ts != st.last_ask_ts
                or st.last_bid_ts == st.ofi_snap_ts):
            return
        snap_ts, curr_bid, curr_ask = st.last_bid_ts, st.last_bid, st.last_ask
        st.ofi_snap_ts = snap_ts                      # mark this ts processed
        if not book_ok(curr_bid, curr_ask):
            return                                    # skip empty/crossed; keep last valid prev
        if st.ofi_prev_bid is not None:               # prev is always a valid book
            dt_ok = (snap_ts - st.ofi_prev_ts) <= self.cfg.depth_ofi_gap_guard_ns
            if dt_ok:
                inc = book_ofi(st.ofi_prev_bid, st.ofi_prev_ask, curr_bid, curr_ask)
                if inc is not None:
                    st.ofi_running += inc
        st.ofi_prev_bid, st.ofi_prev_ask, st.ofi_prev_ts = curr_bid, curr_ask, snap_ts

    def on_event(self, kind: str, detail: str, value_num) -> None:
        self.counts["events"] += 1

    # -- helpers -------------------------------------------------------------
    def _close_bar(self, st: _InstrumentState, bar) -> None:
        cvd_val = st.cvd.running
        slope = st.slope[bar.bar_type].sample(cvd_val)
        vel = st.velocity[bar.bar_type].on_bar_duration(bar.duration_s)
        # per-bar net OFI = running OFI since this bar_type last closed (0.0 when
        # ofi_enabled is off, so bars are unchanged in the inert default).
        bar_ofi = st.ofi_running - st.ofi_base[bar.bar_type]
        st.ofi_base[bar.bar_type] = st.ofi_running
        st.bars += 1
        self.bar_rows.append({
            "security_id": st.sid, "symbol": st.symbol, "bar_type": bar.bar_type,
            "bar_index": bar.bar_index, "start_ts_ns": bar.start_ts_ns,
            "end_ts_ns": bar.end_ts_ns, "duration_s": bar.duration_s,
            "open": bar.open, "high": bar.high, "low": bar.low, "close": bar.close,
            "volume": bar.volume, "buy_vol": bar.buy_vol, "sell_vol": bar.sell_vol,
            "delta": bar.delta, "trade_count": bar.trade_count,
            "cvd_running": cvd_val, "cvd_slope": slope, "ofi": bar_ofi,
            "velocity_baseline_s": vel.baseline_s, "velocity_ratio": vel.ratio,
            "velocity_spike": vel.spike,
            "footprint": json.dumps(bar.footprint, sort_keys=True) if bar.footprint else "",
        })
        # stacked-imbalance detector (INERT until footprint.imbalance_ratio > 0)
        for si in detect_stacked_imbalance(bar.footprint, st.fp_bin,
                                           self.cfg.footprint_imbalance_ratio,
                                           self.cfg.footprint_stacked_min_levels):
            st.stacked_imbalances += 1
            self.event_rows.append({
                "ts_ns": bar.end_ts_ns, "security_id": st.sid, "symbol": st.symbol,
                "kind": "STACKED_IMBALANCE", "side": 1 if si.side == "buy" else -1,
                "notional": None, "price": bar.close, "size": None,
                "detail": f"{si.side} x{si.levels} [{si.price_low}..{si.price_high}]",
            })
        if vel.spike:
            st.velocity_spikes += 1
            self.event_rows.append({
                "ts_ns": bar.end_ts_ns, "security_id": st.sid, "symbol": st.symbol,
                "kind": "VELOCITY_SPIKE", "side": None, "notional": None,
                "price": bar.close, "size": None,
                "detail": f"{bar.bar_type} ratio={vel.ratio:.3f} "
                          f"baseline={vel.baseline_s:.3f}s",
            })

    def _bigprint_row(self, st: _InstrumentState, ev) -> dict:
        return {
            "ts_ns": ev.ts_ns, "security_id": st.sid, "symbol": st.symbol,
            "kind": "BIG_PRINT_CLUSTER" if ev.is_cluster else "BIG_PRINT",
            "side": ev.side, "notional": ev.notional, "price": ev.price, "size": ev.size,
            "strength": ev.strength,          # [0,1] graded tail position (percentile mode)
            "detail": f"cluster of {ev.cluster_count}" if ev.is_cluster else "",
        }

    def finalize(self) -> dict:
        """Flush trailing partial bars and return a per-instrument summary."""
        for st in self.state.values():
            for builder in st.builders:
                bar = builder.flush()
                if bar is not None:
                    self._close_bar(st, bar)
        return self.summary()

    def summary(self) -> dict:
        per = {}
        for sid, st in sorted(self.state.items()):
            per[st.symbol] = {
                "security_id": sid, "trades": st.trades, "bars": st.bars,
                "cvd_final": st.cvd.running, "big_prints": st.big_prints,
                "velocity_spikes": st.velocity_spikes,
                "stacked_imbalances": st.stacked_imbalances,
                "depth_packets": st.depth_packets,
            }
        return {
            "instruments": len(self.state),
            "counts": dict(self.counts),
            "totals": {
                "bars": len(self.bar_rows),
                "events": len(self.event_rows),
                "big_prints": sum(s["big_prints"] for s in per.values()),
                "velocity_spikes": sum(s["velocity_spikes"] for s in per.values()),
                "stacked_imbalances": sum(s["stacked_imbalances"] for s in per.values()),
            },
            "per_instrument": per,
            "uncalibrated_knobs": self.cfg.uncalibrated(),
        }
