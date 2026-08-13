"""Alert dedup + spam guards (Module R7).

Suppression layers (all knob-driven), checked in order:
  1. EXACT      — (instrument, side, bar_ts) already alerted this session
  2. cooldown   — (instrument, side) alerted within alerts.cooldown_sec
  3. min_gap    — any send within alerts.min_gap_sec of the previous send
  4. max/day    — alerts.max_alerts_per_day cap reached

Time is the SIGNAL's timestamp (seconds), not wall-clock, so a dry-run over a
recorded day is deterministic. State persists to analysis/{date}/alerts_state.json
(when alerts.persist_state) so re-running the same evening does not re-send.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


def _sk(instrument: str, side: str) -> str:
    return f"{instrument}|{side}"


class Deduper:
    def __init__(self, cfg, state_path: Optional[Path] = None):
        self.cfg = cfg
        self.state_path = Path(state_path) if state_path else None
        self._seen: set = set()               # {(instrument, side, bar_ts)}
        self._last_side: dict = {}             # "inst|side" -> last send ts (s)
        self._last_send_ts: Optional[float] = None
        self._sent_count: int = 0
        if self.state_path and cfg.persist_state and self.state_path.exists():
            self._load()

    def should_send(self, instrument: str, side: str, bar_ts: int, now_ts: float):
        if (instrument, side, int(bar_ts)) in self._seen:
            return False, "exact_dup"
        last = self._last_side.get(_sk(instrument, side))
        if last is not None and now_ts - last < self.cfg.cooldown_sec:
            return False, "cooldown"
        if self._last_send_ts is not None and now_ts - self._last_send_ts < self.cfg.min_gap_sec:
            return False, "min_gap"
        if self._sent_count >= self.cfg.max_alerts_per_day:
            return False, "max_per_day"
        return True, None

    def record(self, instrument: str, side: str, bar_ts: int, now_ts: float) -> None:
        self._seen.add((instrument, side, int(bar_ts)))
        self._last_side[_sk(instrument, side)] = now_ts
        self._last_send_ts = now_ts
        self._sent_count += 1
        if self.state_path and self.cfg.persist_state:
            self._save()

    @property
    def sent_count(self) -> int:
        return self._sent_count

    # -- persistence ---------------------------------------------------------
    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"seen": [list(k) for k in sorted(self._seen)],
                "last_side": self._last_side, "last_send_ts": self._last_send_ts,
                "sent_count": self._sent_count}
        tmp = self.state_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, default=str))
        tmp.replace(self.state_path)

    def _load(self) -> None:
        try:
            d = json.loads(self.state_path.read_text())
        except Exception:  # noqa: BLE001 - corrupt state -> start fresh
            return
        self._seen = {(s[0], s[1], int(s[2])) for s in d.get("seen", [])}
        self._last_side = dict(d.get("last_side", {}))
        self._last_send_ts = d.get("last_send_ts")
        self._sent_count = int(d.get("sent_count", 0))
