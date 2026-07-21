"""DEPTH PROXIES (P6, 2026-07-21) — replenishment + cancellation-pressure from 5-level
depth diffs. APPROXIMATIONS, honestly labeled — see KNOWN LIMITS below and in the output.

CRITICAL CORRECTNESS RULE: consecutive snapshots are diffed BY PRICE, never by level
index. When price ticks, level-1 becomes a DIFFERENT price — index-diffing manufactures
fake cancels/refills. Only prices present in BOTH snapshots are qty-diffed. A price seen
in only one snapshot is IGNORED (window entry/exit is not an event) — with ONE documented
exception: the vanishing-wall check treats a previously-quoted price that is ABSENT from
the current snapshot while lying strictly INSIDE the current side's quoted price span as
"emptied to zero" (a price-level book lists every level with resting qty in range).

Per side (bid/ask), strictly causal:
  (a) REPLENISHMENT: qty at price p drops, then refills (qty increases at the same p)
      within ``k_refill`` snapshots while the side's best price stays within
      ``near_ticks`` of p  -> refill event; refill_ratio = qty_restored / qty_removed.
  (b) CANCELLATION-PRESSURE: cancel_proxy = max(qty_removed_at_p − traded_at_p, 0)
      between the same two snapshots (traded qty = interleaved tick-feed trades at
      exactly price p in that interval). Vanishing wall: a level ≥ the rolling P90 of
      observed level sizes disappearing (in-range) with < 20% of it traded.

KNOWN LIMITS (also embedded in every output file):
  * 5 levels only — activity beyond the window is invisible.
  * ~200ms snapshot cadence with documented lulls (a 445s gap on 2026-07-15;
    tape/config.py:169-174) — diffs across a gap > gap_guard are DISCARDED, and all
    pending refill state resets (no stale events).
  * No order IDs — removed-vs-traded is inferred from price matching, so a trade is
    attributed to EITHER side whose diffed price matches; this is a proxy, not
    order-event truth.
  * Distinct from (and not duplicating) book_ofi (L1 net-flow accumulator,
    tape/depth_imbalance.py:61) and queue_imbalance (static qty ratio, :27) — those
    summarize the standing book; these decompose CHANGES into executed vs pulled.

Research-lane, DEFAULT OFF: computed only by this module/CLI; writes NEW
analysis/<day>/depth_proxies_<sym>.json files only; nothing in the pipeline reads it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

NS = 1_000_000_000
APPROXIMATION_NOTES = [
    "5-level window only; beyond-window activity invisible",
    "snapshot-cadence blind spots (~200ms feed, lulls documented; gap-guarded)",
    "no order IDs: executed-vs-cancelled inferred by price matching (proxy, not truth)",
    "diff is BY PRICE; window entry/exit is not an event (vanishing-wall in-range rule documented)",
]


@dataclass
class ProxyEvent:
    ts_ns: int
    side: str            # 'bid' | 'ask'
    kind: str            # 'cancel' | 'refill' | 'wall'
    price: float
    removed: float = 0.0
    traded: float = 0.0
    cancel_qty: float = 0.0
    restored: float = 0.0
    ratio: Optional[float] = None    # refill: restored/removed


@dataclass
class _Pending:                      # a removal awaiting possible refill
    price: float
    removed: float
    snaps_left: int


class DepthProxyEngine:
    """Per-instrument engine. Feed on_trade + on_snapshot in ts order (the replayer's
    total order guarantees this). All state is trailing-only — causal by construction."""

    def __init__(self, *, levels: int = 5, k_refill: int = 5, near_ticks: float = 2.0,
                 tick: float = 0.05, gap_guard_ns: int = 5 * NS,
                 wall_frac: float = 0.2, wall_lookback: int = 500):
        self.levels = levels
        self.k_refill = k_refill
        self.near = near_ticks * tick
        self.gap_guard_ns = gap_guard_ns
        self.wall_frac = wall_frac
        self.wall_lookback = wall_lookback
        self._prev: dict[str, tuple[int, dict[float, float]]] = {}   # side -> (ts, {price: qty})
        self._pending: dict[str, list[_Pending]] = {"bid": [], "ask": []}
        self._trades: list[tuple[int, float, float]] = []            # (ts, price, size)
        self._sizes: list[float] = []                                # rolling level sizes (P90)
        self.events: list[ProxyEvent] = []

    # -- inputs --------------------------------------------------------------
    def on_trade(self, ts_ns: int, price: float, size: float) -> None:
        self._trades.append((ts_ns, price, size))

    def _traded_at(self, price: float, t0: int, t1: int) -> float:
        return sum(s for ts, p, s in self._trades if t0 < ts <= t1 and p == price)

    def _p90(self) -> Optional[float]:
        if len(self._sizes) < 50:                    # too little history — no wall calls
            return None
        s = sorted(self._sizes)
        return s[int(0.9 * (len(s) - 1))]

    def on_snapshot(self, ts_ns: int, side: str, book: dict[float, float]) -> None:
        """``book`` = {price: qty} for the top-``levels`` (zero/absent levels excluded)."""
        prev = self._prev.get(side)
        self._prev[side] = (ts_ns, dict(book))
        for q in book.values():
            self._sizes.append(q)
        if len(self._sizes) > self.wall_lookback:
            del self._sizes[: len(self._sizes) - self.wall_lookback]
        if prev is None:
            return
        t0, pbook = prev
        if ts_ns - t0 > self.gap_guard_ns:           # lull: discard diff + pending state
            self._pending[side] = []
            self._trades = [t for t in self._trades if t[0] > ts_ns]
            return
        best = (max if side == "bid" else min)(book) if book else None
        p90 = self._p90()
        span_lo, span_hi = (min(book), max(book)) if book else (None, None)
        # ---- diff BY PRICE over the intersection --------------------------------
        for price in sorted(set(pbook) & set(book)):
            d = pbook[price] - book[price]
            if d > 0:                                                    # qty removed
                traded = self._traded_at(price, t0, ts_ns)
                cancel = max(d - traded, 0.0)
                if cancel > 0:
                    self.events.append(ProxyEvent(ts_ns, side, "cancel", price,
                                                  removed=d, traded=traded, cancel_qty=cancel))
                self._pending[side].append(_Pending(price, d, self.k_refill))
            elif d < 0:                                                  # qty added — refill?
                restored = -d
                for pend in list(self._pending[side]):
                    if pend.price == price and best is not None \
                            and abs(best - price) <= self.near:
                        self.events.append(ProxyEvent(
                            ts_ns, side, "refill", price, removed=pend.removed,
                            restored=restored,
                            ratio=round(restored / pend.removed, 6) if pend.removed else None))
                        self._pending[side].remove(pend)
                        break
        # ---- vanishing wall: quoted before, absent now, INSIDE current span -----
        if p90 is not None and span_lo is not None:
            for price, q in pbook.items():
                if price not in book and span_lo < price < span_hi and q >= p90:
                    traded = self._traded_at(price, t0, ts_ns)
                    if traded < self.wall_frac * q:
                        self.events.append(ProxyEvent(ts_ns, side, "wall", price,
                                                      removed=q, traded=traded,
                                                      cancel_qty=max(q - traded, 0.0)))
        # ---- age out pending refills + old trades -------------------------------
        keep = []
        for pend in self._pending[side]:
            pend.snaps_left -= 1
            if pend.snaps_left > 0:
                keep.append(pend)
        self._pending[side] = keep
        floor = ts_ns - 2 * self.gap_guard_ns
        self._trades = [t for t in self._trades if t[0] >= floor]


# ---------------------------------------------------------------- aggregation + output
def aggregate(events: list[ProxyEvent], bar_bounds: list[tuple[int, int]],
              *, window: int = 10) -> list[dict]:
    """Per-bar counts/sums + rolling-``window`` sums. ``bar_bounds`` = [(start,end)] ns."""
    rows = []
    for (s, e) in bar_bounds:
        ev = [x for x in events if s < x.ts_ns <= e]
        row = {"start_ts_ns": s, "end_ts_ns": e}
        for side in ("bid", "ask"):
            sv = [x for x in ev if x.side == side]
            ref = [x for x in sv if x.kind == "refill"]
            rem = sum(x.removed for x in ref)
            row[f"{side}_refills"] = len(ref)
            row[f"{side}_refill_ratio"] = round(sum(x.restored for x in ref) / rem, 6) if rem else None
            row[f"{side}_cancel_qty"] = round(sum(x.cancel_qty for x in sv if x.kind == "cancel"), 1)
            row[f"{side}_walls"] = sum(1 for x in sv if x.kind == "wall")
        rows.append(row)
    for i, row in enumerate(rows):                      # trailing rolling sums (causal)
        j0 = max(0, i - window + 1)
        for side in ("bid", "ask"):
            row[f"{side}_cancel_qty_w"] = round(sum(rows[k][f"{side}_cancel_qty"] for k in range(j0, i + 1)), 1)
            row[f"{side}_refills_w"] = sum(rows[k][f"{side}_refills"] for k in range(j0, i + 1))
            row[f"{side}_walls_w"] = sum(rows[k][f"{side}_walls"] for k in range(j0, i + 1))
    return rows


def snapshot_to_book(parsed: dict, levels: int = 5) -> dict[float, float]:
    out: dict[float, float] = {}
    for i in range(1, levels + 1):
        p, q = parsed.get(f"price_{i}"), parsed.get(f"qty_{i}")
        if p and q:
            out[float(p)] = float(q)
    return out


def main(argv: list[str]) -> int:
    """Opt-in CLI (the feature is OFF unless invoked): replay a day, emit NEW
    analysis/<day>/depth_proxies_<sym>.json (per-bar + rolling rows + event counts)."""
    import argparse
    ap = argparse.ArgumentParser(prog="research.depth_proxies")
    ap.add_argument("--date", required=True)
    ap.add_argument("--instruments", default="NIFTY_FUT,BANKNIFTY_FUT")
    ap.add_argument("--window", type=int, default=10)
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv[1:])
    from recorder.depth_schema import SIDE_BID
    from replayer.engine import ReplayEngine
    from replayer.source import ReplaySource
    from tape.config import load_tape_config
    from tape.engine import TapeEngine
    from signals.pipeline import build_meta
    from tape.trades import TradeExtractor
    dd = Path(args.root) / "data" / args.date
    meta = build_meta(dd)
    sym = {s: m["symbol"] for s, m in meta.items()}
    insts = [s.strip() for s in args.instruments.split(",") if s.strip()]
    tape = TapeEngine(load_tape_config(), sym)
    sid_by_sym = {v: k for k, v in sym.items()}
    engines: dict[int, DepthProxyEngine] = {}
    extractors: dict[int, TradeExtractor] = {}           # own extractor: mirrors R3 trades
    for s in insts:
        sid = sid_by_sym.get(s)
        if sid is not None:
            engines[sid] = DepthProxyEngine()
            extractors[sid] = TradeExtractor()

    class _C:                                            # replay consumer: tape + proxies
        def on_packet(self, parsed, ts):
            tape.on_packet(parsed, ts)
            sid = parsed.get("security_id")
            if parsed.get("is_tick") and sid in engines:
                tr = extractors[sid].on_tick(parsed)
                if tr is not None:
                    engines[sid].on_trade(tr.ts_ns, tr.price, tr.size)

        def on_depth(self, parsed, ts):
            tape.on_depth(parsed, ts)
            sid = parsed.get("security_id")
            if sid in engines:
                side = "bid" if parsed.get("side") == SIDE_BID else "ask"
                engines[sid].on_snapshot(ts, side, snapshot_to_book(parsed))

        def on_event(self, kind, detail, value_num):
            tape.on_event(kind, detail, value_num)

    ReplayEngine(ReplaySource(dd, instruments=insts)).drive(_C(), speed="max")
    for sid, eng in engines.items():
        bars = [b for b in tape.bar_rows if b["security_id"] == sid and b["bar_type"] == "tick"]
        bars.sort(key=lambda b: b["end_ts_ns"])
        bounds = [(b["start_ts_ns"], b["end_ts_ns"]) for b in bars]
        rows = aggregate(eng.events, bounds, window=args.window)
        counts = {"refill": sum(1 for e in eng.events if e.kind == "refill"),
                  "cancel": sum(1 for e in eng.events if e.kind == "cancel"),
                  "wall": sum(1 for e in eng.events if e.kind == "wall")}
        out = Path(args.root) / "analysis" / args.date / f"depth_proxies_{sym[sid]}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"day": args.date, "symbol": sym[sid],
                                   "approximation_notes": APPROXIMATION_NOTES,
                                   "event_counts": counts, "rows": rows}))
        print(f"{sym[sid]}: events={counts} bars={len(rows)} -> {out}")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
