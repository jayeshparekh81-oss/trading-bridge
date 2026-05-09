"""Phase 1 RBAC — ``users.role`` text column.

Adds a string ``role`` column on the ``users`` table for the locked
2-tier RBAC system. Today's values:

    "user"  — default. Regular trader. No admin endpoints.
    "admin" — full access. Manage users + system.

Phase 2 (locked launch plan) extends to five roles —
``pro_user`` / ``creator`` / ``super_admin`` — without a further
migration because the column type is plain ``text`` rather than an
Enum. The ``is_admin`` boolean column added by Migration 001 is
backfilled into the ``role`` column on upgrade and stays around as a
shadow flag; Phase 2 collapses it into a derived property.

Backfill rules:

    * Rows with ``is_admin = true``  → ``role = 'admin'``
    * All other rows                 → ``role = 'user'``  (server_default)

Index on ``role`` so the admin endpoints (and Phase 2's role-tier
filters) can scan by role cheaply.

Revision ID: 013_users_role
Revises: 012_strategies_cached_scores
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "013_users_role"
down_revision: str | None = "012_strategies_cached_scores"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add the column with server_default so existing rows pick up
    # ``'user'`` automatically — keeps the migration zero-downtime
    # even on a hot DB.
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(32),
            nullable=False,
            server_default="user",
        ),
    )

    # 2. Backfill admins. UPDATE without a default-collision because
    # the prior column-add already populated everyone with ``'user'``.
    op.execute(
        sa.text("UPDATE users SET role = 'admin' WHERE is_admin = TRUE")
    )

    # 3. Index for fast role filtering. Used by Phase 2 admin tier
    # listings and by the audit-events endpoint that joins on role.
    op.create_index("ix_users_role", "users", ["role"])


def downgrade() -> None:
    op.drop_index("ix_users_role", table_name="users")
    op.drop_column("users", "role")
