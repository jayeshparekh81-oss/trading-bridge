"""Standalone Risk Builder — ``risk_templates`` table.

Mirrors :file:`015_entry_templates.py` / :file:`016_exit_templates.py`
for the risk-management half of the strategy DSL. Stores one
``RiskRules`` block as JSONB plus template-level metadata.

Risk doesn't reference indicators, so this table has no
``indicators_used`` column.

Reversible. ``CASCADE`` on the ``user_id`` FK so deleting a user
cleans up their templates atomically.

Revision ID: 017_risk_templates
Revises: 016_exit_templates
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "017_risk_templates"
down_revision: str | None = "016_exit_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "risk_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "risk_rules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_risk_templates_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_risk_templates"),
    )
    op.create_index(
        "ix_risk_templates_user_id", "risk_templates", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_risk_templates_user_id", table_name="risk_templates"
    )
    op.drop_table("risk_templates")
