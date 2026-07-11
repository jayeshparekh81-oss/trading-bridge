"""Per-strike chain state + ΔOI windows (Module R5).

Reconstructs, from replayed option ticks, each strike's running OI / volume /
last price and the change in OI over configurable trailing windows (1/5/15 min).
Pure + deterministic (time is the tick ts, never wall-clock).
"""

from __future__ import annotations

from collections import deque


class StrikeState:
    def __init__(self, windows_s: list[int]):
        self.windows_ns = sorted(int(w) * 1_000_000_000 for w in windows_s)
        self._max_window = self.windows_ns[-1] if self.windows_ns else 0
        self.oi = 0
        self.volume = 0
        self.ltp: float | None = None
        self.first_ts: int | None = None
        self.last_ts: int | None = None
        self._oi_hist: deque[tuple[int, int]] = deque()   # (ts, oi)

    def update(self, ts: int, oi, volume, ltp) -> None:
        if self.first_ts is None:
            self.first_ts = ts
        self.last_ts = ts
        if oi is not None:
            self.oi = int(oi)
            self._oi_hist.append((ts, int(oi)))
            # prune anything older than max window (keep one older anchor)
            while len(self._oi_hist) > 2 and self._oi_hist[1][0] < ts - self._max_window:
                self._oi_hist.popleft()
        if volume is not None:
            self.volume = int(volume)
        if ltp is not None:
            self.ltp = float(ltp)

    def delta_oi(self, ts: int, window_ns: int) -> int:
        """OI now minus OI as of (ts - window). Uses the earliest observation when
        the window reaches before session start (partial window, reported honestly)."""
        if not self._oi_hist:
            return 0
        target = ts - window_ns
        base = self._oi_hist[0][1]
        for t, o in self._oi_hist:
            if t <= target:
                base = o
            else:
                break
        return self.oi - base


class ChainState:
    def __init__(self, index: str, windows_s: list[int]):
        self.index = index
        self.windows_s = windows_s
        self.strikes: dict[tuple, StrikeState] = {}   # (expiry, right, strike) -> StrikeState

    def update(self, expiry: str, right: str, strike: int, ts: int, oi, volume, ltp) -> None:
        key = (expiry, right, strike)
        st = self.strikes.get(key)
        if st is None:
            st = StrikeState(self.windows_s)
            self.strikes[key] = st
        st.update(ts, oi, volume, ltp)

    def snapshot(self, ts: int) -> list[dict]:
        rows = []
        for (expiry, right, strike), st in self.strikes.items():
            row = {"expiry": expiry, "right": right, "strike": strike,
                   "oi": st.oi, "volume": st.volume, "ltp": st.ltp}
            for w_s, w_ns in zip(self.windows_s, sorted(int(w) * 1_000_000_000
                                                        for w in self.windows_s)):
                row[f"doi_{w_s}s"] = st.delta_oi(ts, w_ns)
            rows.append(row)
        return rows
