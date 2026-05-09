"""Customer Support — ``support_tickets`` table.

User-submitted tickets routed to admin queue. CASCADE on
``user_id`` so deleting a user retires their tickets atomically;
``assigned_admin_id`` SET NULL so unassigning an admin who's
left the team doesn't break the row.

Reversible.

Revision ID: 020_support_tickets
Revises: 019_ledger_tables
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "020_support_tickets"
down_revision: str | None = "019_ledger_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "support_tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="open",
        ),
        sa.Column(
            "priority",
            sa.String(16),
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "attachments",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "resolved_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "assigned_admin_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_support_tickets_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_admin_id"],
            ["users.id"],
            name="fk_support_tickets_assigned_admin_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_support_tickets"),
        sa.CheckConstraint(
            "category IN ('bug', 'billing', 'broker_connection', "
            "'strategy_help', 'account', 'other')",
            name="category_valid",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'awaiting_user', "
            "'resolved', 'closed')",
            name="status_valid",
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'critical')",
            name="priority_valid",
        ),
    )
    op.create_index(
        "ix_support_tickets_user_id_status",
        "support_tickets",
        ["user_id", "status"],
    )
    op.create_index(
        "ix_support_tickets_status_priority_created_at",
        "support_tickets",
        ["status", "priority", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_support_tickets_status_priority_created_at",
        table_name="support_tickets",
    )
    op.drop_index(
        "ix_support_tickets_user_id_status",
        table_name="support_tickets",
    )
    op.drop_table("support_tickets")
