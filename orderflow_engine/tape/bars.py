"""Event-time bars (Module R3).

Two bar types, both driven by classified Trades (not wall-clock):
  * N-tick bars  — close every ``tick_bar_size`` trades
  * volume bars  — close when accumulated traded volume >= threshold (0 disables)

Each bar: OHLC, volume, buy_vol/sell_vol, delta (=buy_vol-sell_vol), trade_count,
start/end ts, duration_s, and a FOOTPRINT — per-price-bin volume split by aggressor
side (price_bin -> [buy_vol, sell_vol]). A partial trailing bar is flushed at
session end.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from tape.classify import BUY
from tape.trades import Trade

TICK = "tick"
VOLUME = "volume"


@dataclass
class Bar:
    bar_type: str
    bar_index: int
    start_ts_ns: int
    end_ts_ns: int
    open: float
    high: float
    low: float
    close: float
    volume: int
    buy_vol: int
    sell_vol: int
    trade_count: int
    footprint: dict = field(default_factory=dict)   # price_bin -> [buy_vol, sell_vol]

    @property
    def delta(self) -> int:
        return self.buy_vol - self.sell_vol

    @property
    def duration_s(self) -> float:
        return (self.end_ts_ns - self.start_ts_ns) / 1e9


class _Accumulator:
    def __init__(self, bin_size: float = 0.0) -> None:
        self.bin_size = float(bin_size or 0.0)
        self.reset()

    def reset(self) -> None:
        self.n = 0
        self.open = self.high = self.low = self.close = None
        self.start_ts = self.end_ts = None
        self.volume = self.buy_vol = self.sell_vol = 0
        self.footprint: dict[float, list[int]] = {}

    def add(self, t: Trade) -> None:
        if self.n == 0:
            self.open = self.high = self.low = t.price
            self.start_ts = t.ts_ns
        self.high = max(self.high, t.price)
        self.low = min(self.low, t.price)
        self.close = t.price
        self.end_ts = t.ts_ns
        self.volume += t.size
        is_buy = t.side == BUY
        if is_buy:
            self.buy_vol += t.size
        else:
            self.sell_vol += t.size
        if self.bin_size > 0:
            b = round(math.floor(t.price / self.bin_size) * self.bin_size, 6)
            cell = self.footprint.setdefault(b, [0, 0])
            cell[0 if is_buy else 1] += t.size
        self.n += 1

    def emit(self, bar_type: str, index: int) -> Bar:
        return Bar(bar_type, index, self.start_ts, self.end_ts, self.open, self.high,
                   self.low, self.close, self.volume, self.buy_vol, self.sell_vol, self.n,
                   footprint={k: list(v) for k, v in self.footprint.items()})


class BarBuilder:
    """One bar series (a single bar_type) for one instrument."""

    def __init__(self, bar_type: str, *, tick_size: int = 0, volume_threshold: int = 0,
                 footprint_bin_size: float = 0.0):
        self.bar_type = bar_type
        self.tick_size = tick_size
        self.volume_threshold = volume_threshold
        self._acc = _Accumulator(footprint_bin_size)
        self._index = 0

    def _should_close(self) -> bool:
        if self.bar_type == TICK:
            return self.tick_size > 0 and self._acc.n >= self.tick_size
        return self.volume_threshold > 0 and self._acc.volume >= self.volume_threshold

    def on_trade(self, t: Trade) -> Optional[Bar]:
        self._acc.add(t)
        if self._should_close():
            bar = self._acc.emit(self.bar_type, self._index)
            self._index += 1
            self._acc.reset()
            return bar
        return None

    def flush(self) -> Optional[Bar]:
        """Emit the trailing partial bar (if any) at session end."""
        if self._acc.n == 0:
            return None
        bar = self._acc.emit(self.bar_type, self._index)
        self._index += 1
        self._acc.reset()
        return bar
