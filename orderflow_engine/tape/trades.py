"""Trade extraction from tick snapshots (Module R3).

Dhan FULL/QUOTE packets are SNAPSHOTS, not trade prints: consecutive packets
repeat the same last trade until a new one occurs (verified on real 2026-07-09
data — 4 identical rows, then volume jumps). So a trade is detected only when the
cumulative ``volume`` advances, and the traded size is the volume DELTA.

    trade_size (default 'volume_delta') = volume[t] - volume[t-1]
    trade_size ('ltq' mode)             = last-traded-quantity field

The first snapshot only seeds the volume baseline (its accumulated volume predates
recording and can't be attributed to a classified trade). See TAPE_NOTES.md for
when volume_delta and ltq diverge on real packets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from tape.classify import BUY, classify_trade


@dataclass
class Trade:
    ts_ns: int
    price: float
    size: int
    side: int          # BUY (+1) / SELL (-1)
    notional: float


class TradeExtractor:
    """Per-instrument: fold a stream of tick rows into classified Trades."""

    def __init__(self, size_mode: str = "volume_delta", method: str = "lee_ready"):
        self.size_mode = size_mode
        self.method = method
        self._last_volume: Optional[int] = None
        self._prev_price: Optional[float] = None
        self._prev_side: int = BUY

    def on_tick(self, row: dict) -> Optional[Trade]:
        vol = row.get("volume")
        price = row.get("ltp")
        if vol is None or price is None:
            return None
        vol = int(vol)
        if self._last_volume is None:            # seed on first snapshot; no trade
            self._last_volume = vol
            self._prev_price = float(price)
            return None
        dvol = vol - self._last_volume
        self._last_volume = vol
        if dvol <= 0:                            # no new trade (repeat / correction)
            return None

        size = dvol if self.size_mode == "volume_delta" else int(row.get("ltq") or dvol)
        side = classify_trade(float(price), row.get("bid_price_1"), row.get("ask_price_1"),
                              self._prev_price, self._prev_side, self.method)
        self._prev_price = float(price)
        self._prev_side = side
        return Trade(ts_ns=int(row["ts_recv_ns"]), price=float(price), size=int(size),
                     side=side, notional=float(price) * int(size))
