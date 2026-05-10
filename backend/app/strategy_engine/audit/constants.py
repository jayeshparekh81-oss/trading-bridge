"""Locked constants for the audit log.

Single tunable knobs for buffer capacity and default query window.
Keep this module dependency-free.
"""

from __future__ import annotations

from typing import Final

MAX_EVENTS_IN_MEMORY: Final[int] = 10_000
"""Capacity of the in-memory ring buffer. Once exceeded, the oldest
event is evicted to make room for the newest. The DB-backed store in a
later phase will replace this cap with paginated persistence."""

DEFAULT_QUERY_LIMIT: Final[int] = 100
"""Maximum number of events returned by ``query_events`` when the
caller does not pass an explicit ``limit``. Filters narrow the
candidate set first; the cap then trims the most recent N matches."""


__all__ = [
    "DEFAULT_QUERY_LIMIT",
    "MAX_EVENTS_IN_MEMORY",
]
