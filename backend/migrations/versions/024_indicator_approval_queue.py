"""``indicator_approval_queue`` table — pending status-change requests.

CHECK constraints pin both ``requested_status`` (active /
deprecated) and lifecycle ``status`` (pending / approved /
rejected / withdrawn).

Uniqueness on (indicator_id, status='pending') is **NOT** enforced
at the schema layer — the deliberate choice is to enforce it in
the service layer (service can return a 409 with a useful Hinglish
message; the IntegrityError equivalent is opaque). This also keeps
the migration SQLite-friendly for tests.

Reversible.

Revision ID: 024_indicator_approval_queue
Revises: 023_indicator_status_overrides
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "024_indicator_approval_queue"
down_revision: str | None = "023_indicator_status_overrides"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "indicator_approval_queue",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("indicator_id", sa.String(64), nullable=False),
        sa.Column("requested_status", sa.String(16), nullable=False),
        sa.Column("request_reason", sa.Text(), nullable=False),
        sa.Column(
            "requester_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "request_metadata",
            sa.JSON(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "decision_by_user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "decision_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("decision_notes", sa.Text(), nullable=True),
        sa.Column(
            "resulting_override_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(
                "indicator_status_overrides.id",
                ondelete="SET NULL",
            ),
            nullable=True,
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

    op.create_check_constraint(
        "requested_status_allowed",
        "indicator_approval_queue",
        "requested_status IN ('active', 'deprecated')",
    )
    op.create_check_constraint(
        "queue_status_allowed",
        "indicator_approval_queue",
        (
            "status IN ('pending', 'approved', 'rejected', 'withdrawn')"
        ),
    )

    op.create_index(
        "ix_indicator_approval_queue_indicator_id",
        "indicator_approval_queue",
        ["indicator_id"],
    )
    op.create_index(
        "ix_indicator_approval_queue_status_created_at",
        "indicator_approval_queue",
        ["status", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_indicator_approval_queue_status_created_at",
        table_name="indicator_approval_queue",
    )
    op.drop_index(
        "ix_indicator_approval_queue_indicator_id",
        table_name="indicator_approval_queue",
    )
    op.drop_constraint(
        "ck_indicator_approval_queue_queue_status_allowed",
        "indicator_approval_queue",
        type_="check",
    )
    op.drop_constraint(
        "ck_indicator_approval_queue_requested_status_allowed",
        "indicator_approval_queue",
        type_="check",
    )
    op.drop_table("indicator_approval_queue")
