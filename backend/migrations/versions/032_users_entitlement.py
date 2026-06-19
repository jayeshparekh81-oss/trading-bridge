"""``users`` account-entitlement columns — Phase 2 Billing B2.

Additive link from a user to their overall subscription plan
(``subscription_plans``, B1). Adds three columns to ``users`` and nothing
else — NO ALTER/DROP of any existing column or constraint, and in
particular NO touch of the RBAC / live-trading columns (``role``,
``is_admin``, ``is_active``, ``password_hash``, ``live_trading_enabled``).

Billing is INTENTIONALLY decoupled from RBAC: these columns never drive
``role`` or ``live_trading_enabled`` — plan-based feature gating is a
deliberate later phase.

New columns:
    * ``active_plan_id``  UUID NULL, FK -> subscription_plans(id)
                          ON DELETE RESTRICT, indexed.
    * ``plan_status``     String(16) NOT NULL, server_default ``'none'``,
                          CHECK in ('none','active','expired','cancelled').
    * ``plan_expires_at`` TIMESTAMPTZ NULL (NULL = no expiry / free).

``ADD COLUMN`` with a constant ``server_default`` is metadata-only on
PostgreSQL 11+, so existing rows backfill to
``(active_plan_id=NULL, plan_status='none', plan_expires_at=NULL)`` = free
tier with NO table rewrite.

Fully reversible (downgrade drops the CHECK, FK, index, and the 3 columns).
Chains off ``031_subscription_plans`` (current head on main).

Revision ID: 032_users_entitlement
Revises: 031_subscription_plans
Create Date: 2026-06-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "032_users_entitlement"
down_revision: str | None = "031_subscription_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Locked plan_status vocabulary. Update this migration + the
#: ``plan_status_valid`` CheckConstraint on the User model together if it
#: ever changes. Suffix only — the naming convention prepends
#: ``ck_users_`` (resolves to ``ck_users_plan_status_valid``), mirroring
#: the ``role_valid`` pattern in migration 014.
_PLAN_STATUS_VALUES = ("none", "active", "expired", "cancelled")
_CHECK_NAME = "plan_status_valid"
_FK_NAME = "fk_users_active_plan_id_subscription_plans"
_IX_NAME = "ix_users_active_plan_id"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("active_plan_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "plan_status",
            sa.String(length=16),
            nullable=False,
            server_default="none",
        ),
    )
    op.add_column(
        "users",
        sa.Column("plan_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(_IX_NAME, "users", ["active_plan_id"])
    op.create_foreign_key(
        _FK_NAME,
        "users",
        "subscription_plans",
        ["active_plan_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    quoted = ", ".join(f"'{v}'" for v in _PLAN_STATUS_VALUES)
    op.create_check_constraint(
        _CHECK_NAME,
        "users",
        f"plan_status IN ({quoted})",
    )


def downgrade() -> None:
    op.drop_constraint(_CHECK_NAME, "users", type_="check")
    op.drop_constraint(_FK_NAME, "users", type_="fk")
    op.drop_index(_IX_NAME, table_name="users")
    op.drop_column("users", "plan_expires_at")
    op.drop_column("users", "plan_status")
    op.drop_column("users", "active_plan_id")
