"""THE MID-DAY JOIN RULE. Founder-decided 2026-09-05. Option A.

    A customer who connects mid-session does NOT join a position that is
    already open. They participate only in signals emitted AFTER they connect.

This is settled policy, not a default and not an emergent side-effect of the
connect flow. It lives here, named, so that someone reading this module in six
months sees the rule itself rather than having to infer it from the order path.

WHY. Dropping a late joiner into a running position fills them at a price the
signal never saw, and their stop distance is then wrong relative to the entry
the strategy actually took. The rule refuses that trade rather than approximate
it.

TWO HALVES, AND THE SECOND IS THE ONE THAT BITES.

  ENTRY  — a customer may take an entry signal only if they were connected
           before that signal was emitted. :func:`may_enter`.

  EXIT   — the mirror case. If the engine's open position exits while this
           customer is connected but never entered, the customer must NOT
           receive an exit order. A "sell to close" sent to an account holding
           nothing does not close anything: it OPENS a short. The customer
           would end up holding a position created by an exit they never
           entered.

           This is guaranteed STRUCTURALLY, not by a test: an exit order in the
           customer lane cannot be constructed without naming the customer's
           OWN filled entry order id (see
           ``app.brokers.customer_dhan.CustomerOrderLane.place_order``, which
           refuses an EXIT intent with no ``closes_order_id``). There is no code
           path that builds a customer exit from the engine's position alone,
           so the failure cannot be reintroduced by forgetting a check.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime, timezone

RULE_ID = "MID_DAY_JOIN_A"
RULE_TITLE = "Option A — a late joiner never enters a position already open"
RULE_DECIDED = "2026-09-05, founder"

#: The single source of the customer-facing wording. status.py imports this.
RULE_TEXT = (
    "If you connect after the market opens, you are not placed into a trade that is "
    "already running. You start from the next fresh entry signal. This protects you "
    "from entering at a price the signal never saw."
)


class Intent(str, enum.Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"


@dataclass(frozen=True)
class ParticipationDecision:
    participates: bool
    rule: str
    reason: str

    def __bool__(self) -> bool:  # never let `if decision:` read the wrong way
        return self.participates


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def may_enter(*, connected_at: datetime | None,
              signal_emitted_at: datetime) -> ParticipationDecision:
    """ENTRY half of the rule. Connected strictly before the signal, or no trade."""
    ca, sa = _aware(connected_at), _aware(signal_emitted_at)
    if ca is None:
        return ParticipationDecision(False, RULE_ID, "not_connected")
    if ca > sa:
        return ParticipationDecision(False, RULE_ID, "connected_after_signal")
    return ParticipationDecision(True, RULE_ID, "connected_before_signal")


def may_exit(*, customer_entry_order_id: str | None) -> ParticipationDecision:
    """EXIT half — the mirror case.

    A customer exits only what THEY entered. ``customer_entry_order_id`` is the
    customer's own filled entry order; ``None`` means they never entered, and an
    exit for them would open a fresh position in the opposite direction.
    """
    if not customer_entry_order_id:
        return ParticipationDecision(
            False, RULE_ID,
            "never_entered — an exit here would OPEN a position, not close one")
    return ParticipationDecision(True, RULE_ID, "closes_own_entry")


__all__ = ["RULE_ID", "RULE_TITLE", "RULE_TEXT", "RULE_DECIDED", "Intent",
           "ParticipationDecision", "may_enter", "may_exit"]
