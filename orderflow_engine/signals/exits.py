"""Brahmastra 2.0 exit planner + simulator (Module R6).

For each fired signal we build a full exit plan (thesis-stop from the R4 registry,
1R partial, Chandelier trail, momentum-death 2-of-5, 60-min sleeper) and SIMULATE
it forward on the replay bars so calibration can measure expectancy in R — with NO
broker. Execution of these plans is R8's job; here they are signal-side specs +
a deterministic simulation.

Convention: R = |entry - stop|. Outcomes are in R multiples. Long shown; short is
the mirror (stop above, target below, trail from the lowest low).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExitPlan:
    side: str                 # long | short
    entry: float
    stop: float
    r_value: float
    target_1r: float
    partial_fraction: float
    chandelier_k: float
    sleeper_ns: int
    momentum_required: int
    stop_source: str = ""


def _risk_levels(registry, price: float, side: str) -> list[float]:
    if registry is None:
        return []
    if side == "long":
        return [l.price for l in registry.levels() if l.price < price]
    return [l.price for l in registry.levels() if l.price > price]


def build_exit_plan(ctx, cfg, side: str) -> ExitPlan:
    ex = cfg.exits
    entry = ctx.price
    buf = float(ex.get("thesis_stop_buffer_ticks", 0))
    lvls = _risk_levels(ctx.registry, entry, side)
    if side == "long":
        base = max(lvls) if lvls else entry * 0.995
        stop = base - buf
    else:
        base = min(lvls) if lvls else entry * 1.005
        stop = base + buf
    r = abs(entry - stop)
    target = entry + r if side == "long" else entry - r
    md = ex.get("momentum_death", {})
    return ExitPlan(
        side=side, entry=entry, stop=stop, r_value=r, target_1r=target,
        partial_fraction=float(ex.get("partial_fraction", 0.5)),
        chandelier_k=float(ex.get(f"chandelier_k_{side}", 3.0)),
        sleeper_ns=int(float(ex.get("sleeper_minutes", 60)) * 60 * 1e9),
        momentum_required=int(md.get("conditions_required", 2)),
        stop_source="registry" if lvls else "fallback_pct",
    )


@dataclass
class SimBar:
    ts_ns: int
    high: float
    low: float
    close: float
    flow: dict = field(default_factory=dict)   # momentum-death flags


@dataclass
class ExitOutcome:
    exit_ts_ns: int
    exit_reason: str
    realized_r: float
    partial_taken: bool


class SimPosition:
    """Steps a fired plan forward bar-by-bar to a deterministic R outcome."""

    def __init__(self, plan: ExitPlan, entry_ts_ns: int):
        self.p = plan
        self.entry_ts = entry_ts_ns
        self.long = plan.side == "long"
        self.stop = plan.stop
        self.remaining = 1.0
        self.realized_r = 0.0
        self.partial_done = False
        self.extreme = plan.entry           # highest-high (long) / lowest-low (short)
        self.closed = False

    def _r_at(self, price: float) -> float:
        return ((price - self.p.entry) if self.long else (self.p.entry - price)) / self.p.r_value

    def _close(self, ts, reason, price) -> ExitOutcome:
        self.realized_r += self.remaining * self._r_at(price)
        self.remaining = 0.0
        self.closed = True
        return ExitOutcome(ts, reason, round(self.realized_r, 6), self.partial_done)

    def step(self, bar: SimBar) -> Optional[ExitOutcome]:
        if self.closed:
            return None
        # 1) stop / trailing stop (worst case first)
        hit = bar.low <= self.stop if self.long else bar.high >= self.stop
        if hit:
            return self._close(bar.ts_ns, "stop", self.stop)
        # 2) 1R partial + move stop to breakeven
        tgt_hit = (bar.high >= self.p.target_1r) if self.long else (bar.low <= self.p.target_1r)
        if not self.partial_done and tgt_hit:
            self.realized_r += self.p.partial_fraction * 1.0
            self.remaining -= self.p.partial_fraction
            self.partial_done = True
            self.stop = self.p.entry                     # breakeven
        # 3) Chandelier trail from the running extreme
        self.extreme = max(self.extreme, bar.high) if self.long else min(self.extreme, bar.low)
        chand = (self.extreme - self.p.chandelier_k * self.p.r_value) if self.long \
            else (self.extreme + self.p.chandelier_k * self.p.r_value)
        self.stop = max(self.stop, chand) if self.long else min(self.stop, chand)
        # 4) momentum death (2-of-N flow flags)
        deaths = sum(1 for v in bar.flow.values() if v)
        if self.partial_done and deaths >= self.p.momentum_required:
            return self._close(bar.ts_ns, "momentum_death", bar.close)
        # 5) sleeper time-exit
        if bar.ts_ns - self.entry_ts >= self.p.sleeper_ns:
            return self._close(bar.ts_ns, "sleeper", bar.close)
        return None

    def force_close(self, ts_ns: int, price: float) -> ExitOutcome:
        return self._close(ts_ns, "session_end", price)
