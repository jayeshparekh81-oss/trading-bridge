"""Resolve the effective paper-mode flag for a single strategy.

Single source of truth for the per-strategy override introduced by
migration ``027_strategies_is_paper`` (incident 2026-05-18). All
execution-path code (entry executor, direct-exit handler, time-of-day
guard) must route through :func:`resolve_paper_mode` instead of reading
``settings.strategy_paper_mode`` directly — otherwise the global flag
would silently override a user-configured per-strategy choice, which is
exactly the bug this migration fixes.

Resolution rule::

    effective_paper = (
        strategy.is_paper
        if strategy.is_paper is not None
        else settings.strategy_paper_mode
    )

The DB column is ``NOT NULL`` with server-default ``TRUE``, so the
``None`` branch only fires for Strategy instances constructed in memory
without the column populated (defensive belt for legacy callers and
tests). Production rows always carry an explicit boolean.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import get_settings

if TYPE_CHECKING:
    from app.db.models.strategy import Strategy


def resolve_paper_mode(strategy: "Strategy | None") -> bool:
    """Return the effective paper-mode flag for ``strategy``.

    A ``None`` strategy (no row resolved) falls back to the global flag
    — the safest behaviour: a missing strategy never accidentally fires
    a live broker order. The per-strategy flag wins when set; falsy
    Python-None on the attribute also falls back to global.
    """
    if strategy is not None:
        flag = getattr(strategy, "is_paper", None)
        if flag is not None:
            return bool(flag)
    return bool(get_settings().strategy_paper_mode)


__all__ = ["resolve_paper_mode"]
