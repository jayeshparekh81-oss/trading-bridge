"""Add algomitra_messages table.

Revision ID: 003_add_algomitra_messages_table
Revises: 002_fix_broker_name_case
Create Date: 2026-04-25

Logs each message in an AlgoMitra chat session so we can analyse common
questions and seed the Phase 1B Claude retriever. Append-only.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "003_add_algomitra_messages_table"
down_revision: Union[str, None] = "002_fix_broker_name_case"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ALGOMITRA_ROLE_ENUM = sa.Enum(
    "user",
    "assistant",
    name="algomitra_role_enum",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "algomitra_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("role", ALGOMITRA_ROLE_ENUM, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("flow_id", sa.String(64), nullable=True),
        sa.Column("flow_step", sa.String(64), nullable=True),
        sa.Column(
            "has_image",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_algomitra_messages")),
    )
    op.create_index(
        op.f("ix_algomitra_messages_user_id"),
        "algomitra_messages",
        ["user_id"],
    )
    op.create_index(
        op.f("ix_algomitra_messages_session_id"),
        "algomitra_messages",
        ["session_id"],
    )
    op.create_index(
        op.f("ix_algomitra_messages_created_at"),
        "algomitra_messages",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_algomitra_messages_created_at"),
        table_name="algomitra_messages",
    )
    op.drop_index(
        op.f("ix_algomitra_messages_session_id"),
        table_name="algomitra_messages",
    )
    op.drop_index(
        op.f("ix_algomitra_messages_user_id"),
        table_name="algomitra_messages",
    )
    op.drop_table("algomitra_messages")
