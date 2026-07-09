"""Consumer contract + reference consumers.

The replay engine delivers events through the EXACT callback shape the live feed
uses (see ``recorder.feed``: ``PacketCb = (parsed_packet, ts_recv_ns)`` and
``EventCb = (kind, detail, value_num)``). Any R3+ strategy/analytics module that
implements :class:`Consumer` therefore runs unchanged on live OR replayed data.
"""

from __future__ import annotations

import hashlib
from typing import Optional, Protocol, runtime_checkable

from recorder.schema import TICK_COLUMNS


@runtime_checkable
class Consumer(Protocol):
    def on_packet(self, parsed: dict, ts_recv_ns: int) -> None: ...
    def on_event(self, kind: str, detail: str, value_num: Optional[float]) -> None: ...


class CountingConsumer:
    """Tallies packets + events (used by the CLI summary and tests)."""

    def __init__(self) -> None:
        self.packets = 0
        self.events = 0

    def on_packet(self, parsed: dict, ts_recv_ns: int) -> None:
        self.packets += 1

    def on_event(self, kind: str, detail: str, value_num: Optional[float]) -> None:
        self.events += 1

    @property
    def total(self) -> int:
        return self.packets + self.events


def _canon(value) -> str:
    """Deterministic scalar encoding (stable across runs/platforms)."""
    if value is None:
        return "\x00"
    if isinstance(value, float):
        # repr() round-trips float64 exactly and is deterministic.
        return repr(value)
    return str(value)


class HashingConsumer:
    """Folds the FULL emitted stream into one hash — the G1 determinism gate.

    Each item is serialized canonically (fixed field order, None sentinel) so two
    replays of identical input yield an identical digest. Timing/speed never
    enters the hash, so the digest is speed-independent.
    """

    def __init__(self) -> None:
        self._h = hashlib.sha256()
        self.count = 0

    def on_packet(self, parsed: dict, ts_recv_ns: int) -> None:
        parts = ["P", str(ts_recv_ns)] + [_canon(parsed.get(c)) for c in TICK_COLUMNS]
        self._h.update(("\x1f".join(parts) + "\x1e").encode("utf-8"))
        self.count += 1

    def on_event(self, kind: str, detail: str, value_num: Optional[float]) -> None:
        parts = ["E", _canon(kind), _canon(detail), _canon(value_num)]
        self._h.update(("\x1f".join(parts) + "\x1e").encode("utf-8"))
        self.count += 1

    def hexdigest(self) -> str:
        return self._h.hexdigest()
