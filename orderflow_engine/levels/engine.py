"""LevelsEngine (Module R4) — replayer Consumer for the INTRADAY path.

Per instrument, from the SAME classified trade stream R3 uses (tape.TradeExtractor):
running session VWAP (+bands) and a developing volume profile (POC/VAH/VAL, plus
inert HVN/LVN). Emits periodic VWAP snapshots and, at finalize, an intraday
LevelRegistry per instrument. Daily/pivot levels are merged on top in levels.run
(they come from the historical path, not the tick stream).

Deterministic: given the replayer's deterministic stream, outputs are identical.
"""

from __future__ import annotations

from levels.config import LevelsConfig
from levels.registry import LevelRegistry
from levels.volume_profile import VolumeProfile
from levels.vwap import SessionVWAP
from tape.trades import TradeExtractor


class _InstrumentState:
    def __init__(self, sid: int, symbol: str, cfg: LevelsConfig):
        self.sid = sid
        self.symbol = symbol
        self.extractor = TradeExtractor()          # defaults: volume_delta + lee_ready
        self.vwap = SessionVWAP(cfg.vwap_bands)
        self.profile = VolumeProfile(cfg.bin_size(symbol))
        self.trades = 0
        self.first_price: float | None = None
        self.last_price: float | None = None
        self.snapshots: list[dict] = []


class LevelsEngine:
    def __init__(self, config: LevelsConfig, sym_by_id: dict[int, str] | None = None,
                 date: str = ""):
        self.cfg = config
        self.sym_by_id = sym_by_id or {}
        self.date = date
        self.state: dict[int, _InstrumentState] = {}
        self.counts = {"ticks": 0, "trades": 0, "depth": 0, "events": 0}

    def _st(self, sid: int) -> _InstrumentState:
        st = self.state.get(sid)
        if st is None:
            st = _InstrumentState(sid, self.sym_by_id.get(sid, f"SID{sid}"), self.cfg)
            self.state[sid] = st
        return st

    # -- consumer contract ---------------------------------------------------
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
        if st.first_price is None:
            st.first_price = trade.price
        st.last_price = trade.price
        st.vwap.on_trade(trade)
        st.profile.on_trade(trade)
        if st.trades % self.cfg.snapshot_every_trades == 0:
            self._snap(st)

    def on_depth(self, parsed: dict, ts_recv_ns: int) -> None:
        self.counts["depth"] += 1

    def on_event(self, kind: str, detail: str, value_num) -> None:
        self.counts["events"] += 1

    def _snap(self, st: _InstrumentState) -> None:
        s = st.vwap.snapshot()
        if s is None:
            return
        st.snapshots.append({"security_id": st.sid, "symbol": st.symbol,
                             "seq": len(st.snapshots), "cum_volume": s.cum_volume,
                             "vwap": s.vwap, "std": s.std})

    # -- finalize ------------------------------------------------------------
    def build_registry(self, st: _InstrumentState) -> LevelRegistry:
        reg = LevelRegistry(st.sid, st.symbol, self.date)
        snap = st.vwap.snapshot()
        if snap is not None:
            reg.add("VWAP", snap.vwap, {"std": snap.std})
            for name, price in snap.bands.items():
                reg.add(f"VWAP_{name.upper()}", price)
        prof = st.profile.result(self.cfg.value_area_pct,
                                 self.cfg.hvn_threshold, self.cfg.lvn_threshold)
        reg.add("POC", prof.poc)
        reg.add("VAH", prof.vah)
        reg.add("VAL", prof.val)
        for p in prof.hvn:
            reg.add("HVN", p)
        for p in prof.lvn:
            reg.add("LVN", p)
        reg.set_context("session_open", st.first_price)
        reg.set_context("session_last", st.last_price)
        reg.set_context("value_area_pct", self.cfg.value_area_pct)
        return reg

    def finalize(self) -> dict:
        registries: dict[int, LevelRegistry] = {}
        per = {}
        for sid, st in sorted(self.state.items()):
            self._snap(st)   # final snapshot
            reg = self.build_registry(st)
            registries[sid] = reg
            snap = st.vwap.snapshot()
            prof = st.profile.result(self.cfg.value_area_pct)
            per[st.symbol] = {
                "security_id": sid, "trades": st.trades,
                "vwap": snap.vwap if snap else None,
                "poc": prof.poc, "vah": prof.vah, "val": prof.val,
                "levels": len(reg.levels()),
            }
        self.registries = registries
        return {
            "instruments": len(self.state), "counts": dict(self.counts),
            "per_instrument": per, "uncalibrated_knobs": self.cfg.uncalibrated(),
        }
