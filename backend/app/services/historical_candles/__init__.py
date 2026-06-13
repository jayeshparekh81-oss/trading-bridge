"""Historical-candle persistence layer.

Queue CCC Phase 2 skeleton. See ``docs/QUEUE_CCC_REAL_DHAN_DESIGN_v2.md``.

Phase 2 ships:
    * :class:`HistoricalCandle` ORM model (re-export).
    * :class:`HistoricalCandleRepository` (commit b — pending).
    * Schema bridges (commit c — pending).

Phase 3 will add: ``fetch_orchestrator``, ``backfill_service``,
``symbol_bridge``, ``rate_limit_guard``.

Public surface stays minimal so Phase 3 modules can extend it without
breaking existing imports.
"""

from __future__ import annotations

from app.db.models.historical_candle import HistoricalCandle

__all__ = ["HistoricalCandle"]
