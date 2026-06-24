"""Cross-track seam — widen ``execution_mode`` CHECK to add ``'paper'``.

INTEGRATION follow-on (after the 037 merge). The fan-out track created
``marketplace_subscriptions.execution_mode`` with CHECK IN
('auto','one_click','offline') (migration 035_subscription_exec_fields). The
billing track's M3 per-subscriber settings UI/endpoint offers ``'paper'`` as an
execution mode (default). This ADDITIVE widen lets the M3 settings PATCH persist
``'paper'`` into the fan-out column, so the two tracks' subscriber-settings
vocabularies coexist.

Behaviour-preserving: ``execution_mode`` is CARRIED but NOT branched on by the
fan-out (which forces paper today and is flag-OFF), so enlarging the allowed set
changes no execution behaviour. ``is_paper`` remains the real paper/live gate.
(A later cleanup may collapse the redundant ``'paper'`` mode into ``is_paper``
before any main merge — flagged in NOTES.)

Kept <= 32 chars. LOCAL validation only; NOT prod.

Revision ID: 038_exec_mode_paper
Revises: 037_merge_fanout_billing
Create Date: 2026-06-24
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "038_exec_mode_paper"
down_revision: str | None = "037_merge_fanout_billing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "marketplace_subscriptions"
_CHECK = "execution_mode_valid"
_OLD = ("auto", "one_click", "offline")
_NEW = ("auto", "one_click", "offline", "paper")


def _expr(values: tuple[str, ...]) -> str:
    return f"execution_mode IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.drop_constraint(_CHECK, _TABLE, type_="check")
    op.create_check_constraint(_CHECK, _TABLE, _expr(_NEW))


def downgrade() -> None:
    op.drop_constraint(_CHECK, _TABLE, type_="check")
    op.create_check_constraint(_CHECK, _TABLE, _expr(_OLD))
