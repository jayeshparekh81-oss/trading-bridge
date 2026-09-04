"""customer lane: connection state, notification ladder, connect links

ADDITIVE ONLY. Creates three NEW tables. No ALTER, no DROP of any pre-existing
object. Nothing on the live BSE trading path is referenced.

Revision ID: 047_customer_lane
Revises: 046_pnl_attribution
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "047_customer_lane"
down_revision: str | None = "046_pnl_attribution"
branch_labels = None
depends_on = None

_LINK_STATUS = ("NEVER_CONNECTED", "CONNECTED", "EXPIRED", "FAILED", "DISABLED")
_STEP = ("R1", "R2", "CALL", "RED", "CONFIRM")
_LINK_STATE = ("ISSUED", "CONSUMED", "EXPIRED")


def upgrade() -> None:
    op.create_table(
        "customer_broker_link",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("customer_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("broker", sa.String(32), nullable=False, server_default="dhan"),
        sa.Column("broker_client_id", sa.String(64), nullable=True),
        sa.Column("access_token_enc", sa.String(2048), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_static_ip", sa.String(64), nullable=True),
        sa.Column("proxy_url", sa.String(512), nullable=True),
        sa.Column("proxy_username", sa.String(128), nullable=True),
        sa.Column("proxy_password_enc", sa.String(1024), nullable=True),
        sa.Column("ip_whitelisted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_lock_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status",
                  sa.Enum(*_LINK_STATUS, name="customer_link_status_enum", native_enum=False),
                  nullable=False, server_default="NEVER_CONNECTED"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_customer_broker_link_customer_id", "customer_broker_link", ["customer_id"])

    op.create_table(
        "customer_notification_log",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("customer_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("step", sa.Enum(*_STEP, name="customer_ladder_step_enum", native_enum=False),
                  nullable=False),
        sa.Column("trading_date", sa.Date(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("detail", sa.String(1024), nullable=True),
        sa.UniqueConstraint("customer_id", "step", "trading_date",
                            name="uq_customer_notification_step_day"),
    )
    op.create_index("ix_customer_notification_log_customer_id", "customer_notification_log", ["customer_id"])
    op.create_index("ix_customer_notification_log_trading_date", "customer_notification_log", ["trading_date"])

    op.create_table(
        "customer_connect_link",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("customer_id", sa.Uuid(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trading_date", sa.Date(), nullable=False),
        sa.Column("status", sa.Enum(*_LINK_STATE, name="customer_connect_link_status_enum",
                                    native_enum=False),
                  nullable=False, server_default="ISSUED"),
    )
    op.create_index("ix_customer_connect_link_customer_id", "customer_connect_link", ["customer_id"])
    op.create_index("ix_customer_connect_link_token_hash", "customer_connect_link", ["token_hash"])
    op.create_index("ix_customer_connect_link_trading_date", "customer_connect_link", ["trading_date"])


def downgrade() -> None:
    op.drop_table("customer_connect_link")
    op.drop_table("customer_notification_log")
    op.drop_table("customer_broker_link")
