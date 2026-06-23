"""``subscription_id`` scoping on strategy_positions + strategy_executions.

Marketplace Module 3 — adds the per-subscriber scoping dimension so subscriber
PAPER positions are isolated from the OWNER's 1->1 positions (which are keyed by
``(strategy, symbol, side)`` ignoring ``user_id`` — without this column a
subscriber row would sum into / be closed by the owner's LIVE position).

ADDITIVE + NULLABLE ONLY:
    * Adds ``subscription_id`` (nullable UUID FK -> marketplace_subscriptions)
      to ``strategy_positions`` and ``strategy_executions``.
    * Changes NO existing column, performs NO data backfill, adds NO NOT-NULL
      constraint. Every existing (owner) row keeps ``subscription_id = NULL`` and
      behaves byte-identically — owner lookups scope to ``subscription_id IS
      NULL`` and so match exactly the same rows as before.
    * ``ON DELETE CASCADE``: a subscriber row must never decay to NULL (which
      would bleed it into the owner's scope), so deleting a subscription removes
      its paper positions/executions rather than nulling the FK.

Does NOT touch the live BSE/CDSL strategy state. Fully reversible: downgrade
drops the two columns (+ their FK/index).

Revision ID: 034_subscription_position_scoping
Revises: 033_strategy_state_audit
Create Date: 2026-06-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "034_subscription_position_scoping"
down_revision: str | None = "033_strategy_state_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_POSITIONS = "strategy_positions"
_EXECUTIONS = "strategy_executions"
_SUBSCRIPTIONS = "marketplace_subscriptions"

_POS_FK = "fk_strategy_positions_subscription_id"
_POS_IX = "ix_strategy_positions_subscription_id"
_EXEC_FK = "fk_strategy_executions_subscription_id"
_EXEC_IX = "ix_strategy_executions_subscription_id"


def upgrade() -> None:
    # ── strategy_positions.subscription_id (nullable) ──────────────────────
    op.add_column(
        _POSITIONS,
        sa.Column("subscription_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.create_index(_POS_IX, _POSITIONS, ["subscription_id"])
    op.create_foreign_key(
        _POS_FK,
        _POSITIONS,
        _SUBSCRIPTIONS,
        ["subscription_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # ── strategy_executions.subscription_id (nullable) ─────────────────────
    op.add_column(
        _EXECUTIONS,
        sa.Column("subscription_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.create_index(_EXEC_IX, _EXECUTIONS, ["subscription_id"])
    op.create_foreign_key(
        _EXEC_FK,
        _EXECUTIONS,
        _SUBSCRIPTIONS,
        ["subscription_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(_EXEC_FK, _EXECUTIONS, type_="foreignkey")
    op.drop_index(_EXEC_IX, table_name=_EXECUTIONS)
    op.drop_column(_EXECUTIONS, "subscription_id")

    op.drop_constraint(_POS_FK, _POSITIONS, type_="foreignkey")
    op.drop_index(_POS_IX, table_name=_POSITIONS)
    op.drop_column(_POSITIONS, "subscription_id")
