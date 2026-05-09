"""Standalone Exit Builder — ``exit_templates`` table.

Mirrors :file:`015_entry_templates.py` for the exit half of the
strategy DSL. The standalone Exit Builder lets users author one
``ExitRules`` block in isolation and save it for later reuse. The
row stores everything needed to round-trip a template back into the
builder UI:

    * ``exit_rules`` — full Pydantic ``ExitRules`` block serialised
      as JSONB. Holds ``targetPercent`` / ``stopLossPercent`` /
      ``trailingStopPercent`` / ``partialExits`` / ``squareOffTime``
      / ``indicatorExits`` / ``reverseSignalExit`` (camelCase aliases
      preserved on the wire).
    * ``indicators_used`` — JSONB array of ``IndicatorConfig`` dicts
      referenced by the template's ``indicatorExits``. Stored as
      JSONB rather than ``text[]`` so the same ORM ships against the
      test SQLite + production Postgres without dialect-specific
      glue.

Reversible. ``CASCADE`` on the ``user_id`` FK so deleting a user
cleans up their templates atomically.

Revision ID: 016_exit_templates
Revises: 015_entry_templates
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "016_exit_templates"
down_revision: str | None = "015_entry_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exit_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "exit_rules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "indicators_used",
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_exit_templates_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_exit_templates"),
    )
    op.create_index(
        "ix_exit_templates_user_id", "exit_templates", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_exit_templates_user_id", table_name="exit_templates"
    )
    op.drop_table("exit_templates")
