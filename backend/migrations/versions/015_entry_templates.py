"""Standalone Entry Builder — ``entry_templates`` table.

The standalone Entry Builder lets users author one ``EntryRules``
block in isolation and save it for later reuse. The row stores
everything needed to round-trip a template back into the builder UI:

    * ``side`` + ``operator`` — top-level entry knobs.
    * ``conditions`` — full Pydantic ``Condition`` list serialised as
      a JSONB array. Each entry is one of ``IndicatorCondition``,
      ``CandleCondition``, ``TimeCondition``, or ``PriceCondition``.
    * ``indicators_used`` — JSONB array of the ``IndicatorConfig``
      dicts the template references. Stored as JSONB rather than
      ``text[]`` so the same ORM ships against the test SQLite +
      production Postgres without dialect-specific glue.

Reversible. ``CASCADE`` on the ``user_id`` FK so deleting a user
cleans up their templates atomically.

Revision ID: 015_entry_templates
Revises: 014_role_check_constraint
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "015_entry_templates"
down_revision: str | None = "014_role_check_constraint"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "entry_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column(
            "operator",
            sa.String(8),
            nullable=False,
            server_default="AND",
        ),
        sa.Column(
            "conditions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
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
            name="fk_entry_templates_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_entry_templates"),
    )
    op.create_index(
        "ix_entry_templates_user_id", "entry_templates", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_entry_templates_user_id", table_name="entry_templates"
    )
    op.drop_table("entry_templates")
