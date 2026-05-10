"""Admin workflow for promoting / overriding / deprecating indicators.

The indicator registry stays the source of truth for *default*
status. This package layers on DB-backed overrides + a creator
request queue so admins can change status without a code deploy.

Three responsibilities, one module each:

* :mod:`.resolver`  — read-side: resolve effective status for a given id
* :mod:`.approval`  — write-side: queue lifecycle (request / decide / withdraw)
* :mod:`.overrides` — write-side: direct admin override + history queries
"""

from app.strategy_engine.indicator_admin.approval import (
    decide_request,
    enqueue_request,
    list_my_requests,
    list_pending_queue,
    withdraw_request,
)
from app.strategy_engine.indicator_admin.overrides import (
    create_direct_override,
    get_indicator_history,
    list_active_overrides,
)
from app.strategy_engine.indicator_admin.resolver import (
    EffectiveStatus,
    resolve_effective_status,
)

__all__ = [
    "EffectiveStatus",
    "create_direct_override",
    "decide_request",
    "enqueue_request",
    "get_indicator_history",
    "list_active_overrides",
    "list_my_requests",
    "list_pending_queue",
    "resolve_effective_status",
    "withdraw_request",
]
