"""``indicator_status_overrides`` table — admin lifecycle overrides.

History-style schema: every override change is a new row, never an
update. Effective status is the latest non-expired row for an
indicator id (resolver in
``app.strategy_engine.indicator_admin.resolver``).

CHECK constraint pins the allowed status values + the prior_status_source
enum. Two indexes:

    * ``(indicator_id, effective_from DESC)`` — resolver lookup
    * ``(approved_at DESC)`` — admin "recent decisions" view

Reversible.

Revision ID: 023_indicator_status_overrides
Revises: 022_perf_indexes
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "023_indicator_status_overrides"
down_revision: str | None = "022_perf_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "indicator_status_overrides",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("indicator_id", sa.String(64), nullable=False),
        sa.Column("override_status", sa.String(16), nullable=False),
        sa.Column("override_reason", sa.Text(), nullable=False),
        sa.Column(
            "approved_by_user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "effective_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("prior_status", sa.String(16), nullable=True),
        sa.Column("prior_status_source", sa.String(32), nullable=True),
        sa.Column(
            "audit_log_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("audit_logs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "decision_metadata",
            sa.JSON(),
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
    )

    # Bare suffix — naming_convention auto-prepends ``ck_<table>_``.
    op.create_check_constraint(
        "override_status_allowed",
        "indicator_status_overrides",
        "override_status IN ('active', 'coming_soon', 'experimental', 'deprecated')",
    )
    op.create_check_constraint(
        "prior_status_source_allowed",
        "indicator_status_overrides",
        (
            "prior_status_source IS NULL OR "
            "prior_status_source IN ('registry_default', 'prior_override')"
        ),
    )

    op.create_index(
        "ix_indicator_status_overrides_indicator_effective_from",
        "indicator_status_overrides",
        ["indicator_id", sa.text("effective_from DESC")],
    )
    op.create_index(
        "ix_indicator_status_overrides_approved_at",
        "indicator_status_overrides",
        [sa.text("approved_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_indicator_status_overrides_approved_at",
        table_name="indicator_status_overrides",
    )
    op.drop_index(
        "ix_indicator_status_overrides_indicator_effective_from",
        table_name="indicator_status_overrides",
    )
    op.drop_constraint(
        "ck_indicator_status_overrides_prior_status_source_allowed",
        "indicator_status_overrides",
        type_="check",
    )
    op.drop_constraint(
        "ck_indicator_status_overrides_override_status_allowed",
        "indicator_status_overrides",
        type_="check",
    )
    op.drop_table("indicator_status_overrides")
