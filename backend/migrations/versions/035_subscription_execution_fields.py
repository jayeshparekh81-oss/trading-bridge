"""Per-subscriber execution config on ``marketplace_subscriptions``.

Marketplace Module 4 — gives each subscriber their own size, execution mode,
paper flag, direction filter, and chosen broker credential.

ADDITIVE ONLY (single new head off 034). Adds five NEW columns to
``marketplace_subscriptions`` ONLY:
    * ``lots_override``       INTEGER  NULL                 (NULL => strategy default)
    * ``execution_mode``      VARCHAR(16) NOT NULL DEFAULT 'auto'
    * ``is_paper``            BOOLEAN  NOT NULL DEFAULT true
    * ``direction_filter``    VARCHAR(8)  NOT NULL DEFAULT 'all'
    * ``broker_credential_id`` UUID    NULL  FK -> broker_credentials (SET NULL)

Changes NO existing column, performs NO meaning-altering backfill. The three
NOT-NULL columns carry safe server-defaults, so existing rows fill with the
default automatically (no NOT-NULL violation on existing data). CHECK
constraints pin the ``execution_mode`` / ``direction_filter`` vocabularies, and
the defaults satisfy them.

Touches only the subscriber table — the OWNER 1->1 path has no rows here.
Fully reversible. Validated locally only; NOT applied to prod.

Revision ID: 035_subscription_execution_fields
Revises: 034_subscription_position_scoping
Create Date: 2026-06-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "035_subscription_execution_fields"
down_revision: str | None = "034_subscription_position_scoping"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "marketplace_subscriptions"
_FK_NAME = "fk_marketplace_subscriptions_broker_credential_id"
_IX_NAME = "ix_marketplace_subscriptions_broker_credential_id"
# Short logical names — the Base.metadata naming convention
# ("ck_%(table_name)s_%(constraint_name)s") prefixes them consistently on both
# create and drop (mirrors migration 032's ``plan_status_valid``).
_MODE_CHECK = "execution_mode_valid"
_DIR_CHECK = "direction_filter_valid"

_EXECUTION_MODES = ("auto", "one_click", "offline")
_DIRECTION_FILTERS = ("all", "long", "short")


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column("lots_override", sa.Integer(), nullable=True),
    )
    op.add_column(
        _TABLE,
        sa.Column(
            "execution_mode",
            sa.String(length=16),
            nullable=False,
            server_default="auto",
        ),
    )
    op.add_column(
        _TABLE,
        sa.Column(
            "is_paper",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        _TABLE,
        sa.Column(
            "direction_filter",
            sa.String(length=8),
            nullable=False,
            server_default="all",
        ),
    )
    op.add_column(
        _TABLE,
        sa.Column("broker_credential_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.create_index(_IX_NAME, _TABLE, ["broker_credential_id"])
    op.create_foreign_key(
        _FK_NAME,
        _TABLE,
        "broker_credentials",
        ["broker_credential_id"],
        ["id"],
        ondelete="SET NULL",
    )

    mode_values = ", ".join(f"'{v}'" for v in _EXECUTION_MODES)
    op.create_check_constraint(
        _MODE_CHECK, _TABLE, f"execution_mode IN ({mode_values})"
    )
    dir_values = ", ".join(f"'{v}'" for v in _DIRECTION_FILTERS)
    op.create_check_constraint(
        _DIR_CHECK, _TABLE, f"direction_filter IN ({dir_values})"
    )


def downgrade() -> None:
    op.drop_constraint(_DIR_CHECK, _TABLE, type_="check")
    op.drop_constraint(_MODE_CHECK, _TABLE, type_="check")
    op.drop_constraint(_FK_NAME, _TABLE, type_="foreignkey")
    op.drop_index(_IX_NAME, table_name=_TABLE)
    op.drop_column(_TABLE, "broker_credential_id")
    op.drop_column(_TABLE, "direction_filter")
    op.drop_column(_TABLE, "is_paper")
    op.drop_column(_TABLE, "execution_mode")
    op.drop_column(_TABLE, "lots_override")
