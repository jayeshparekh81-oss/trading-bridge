"""Initial schema — Step 3.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-04-16

Creates every table registered by :mod:`app.db.models`. Drops them in
reverse FK order on downgrade.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BROKER_NAME_ENUM = sa.Enum(
    "fyers", "dhan", "shoonya", "zerodha", "upstox", "angelone",
    name="broker_name_enum",
    native_enum=False,
)
ORDER_SIDE_ENUM = sa.Enum(
    "buy", "sell", name="order_side_enum", native_enum=False
)
ORDER_TYPE_ENUM = sa.Enum(
    "market", "limit", "sl", "sl_m", name="order_type_enum", native_enum=False
)
PRODUCT_TYPE_ENUM = sa.Enum(
    "intraday", "delivery", "margin", "bo", "co",
    name="product_type_enum",
    native_enum=False,
)
TRADE_STATUS_ENUM = sa.Enum(
    "pending", "open", "complete", "cancelled", "rejected", "partial", "squared_off",
    name="trade_status_enum",
    native_enum=False,
)
PROCESSING_STATUS_ENUM = sa.Enum(
    "received", "validated", "executed", "failed", "skipped",
    name="processing_status_enum",
    native_enum=False,
)
ACTOR_TYPE_ENUM = sa.Enum(
    "user", "system", "admin", name="actor_type_enum", native_enum=False
)


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("telegram_chat_id", sa.String(64), nullable=True),
        sa.Column(
            "notification_prefs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
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
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ── broker_credentials ─────────────────────────────────────────────
    op.create_table(
        "broker_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("broker_name", BROKER_NAME_ENUM, nullable=False),
        sa.Column("client_id_enc", sa.String(512), nullable=False),
        sa.Column("api_key_enc", sa.String(512), nullable=False),
        sa.Column("api_secret_enc", sa.String(512), nullable=False),
        sa.Column("access_token_enc", sa.String(1024), nullable=True),
        sa.Column("refresh_token_enc", sa.String(1024), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("totp_secret_enc", sa.String(512), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_broker_credentials_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_broker_credentials"),
    )
    op.create_index(
        "ix_broker_credentials_user_id", "broker_credentials", ["user_id"]
    )

    # ── webhook_tokens ─────────────────────────────────────────────────
    op.create_table(
        "webhook_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("hmac_secret_enc", sa.String(512), nullable=False),
        sa.Column("label", sa.String(128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_webhook_tokens_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_webhook_tokens"),
        sa.UniqueConstraint("token_hash", name="uq_webhook_tokens_token_hash"),
    )
    op.create_index("ix_webhook_tokens_user_id", "webhook_tokens", ["user_id"])
    op.create_index("ix_webhook_tokens_token_hash", "webhook_tokens", ["token_hash"])

    # ── strategies ─────────────────────────────────────────────────────
    op.create_table(
        "strategies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("webhook_token_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("broker_credential_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("max_position_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "allowed_symbols",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
            ["user_id"], ["users.id"],
            name="fk_strategies_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["webhook_token_id"], ["webhook_tokens.id"],
            name="fk_strategies_webhook_token_id_webhook_tokens",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["broker_credential_id"], ["broker_credentials.id"],
            name="fk_strategies_broker_credential_id_broker_credentials",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_strategies"),
    )
    op.create_index("ix_strategies_user_id", "strategies", ["user_id"])

    # ── webhook_events ─────────────────────────────────────────────────
    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("source_ip", sa.String(64), nullable=True),
        sa.Column("signature_valid", sa.Boolean(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("processing_status", PROCESSING_STATUS_ENUM, nullable=False),
        sa.Column("error_message", sa.String(1024), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_webhook_events_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_webhook_events"),
    )
    op.create_index("ix_webhook_events_user_id", "webhook_events", ["user_id"])
    op.create_index("ix_webhook_events_received_at", "webhook_events", ["received_at"])

    # ── trades ─────────────────────────────────────────────────────────
    op.create_table(
        "trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "broker_credential_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("broker_order_id", sa.String(128), nullable=True),
        sa.Column("tradingview_signal_id", sa.String(128), nullable=True),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("exchange", sa.String(8), nullable=False),
        sa.Column("side", ORDER_SIDE_ENUM, nullable=False),
        sa.Column("order_type", ORDER_TYPE_ENUM, nullable=False),
        sa.Column("product_type", PRODUCT_TYPE_ENUM, nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(18, 4), nullable=True),
        sa.Column("avg_fill_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("status", TRADE_STATUS_ENUM, nullable=False),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pnl_realized", sa.Numeric(18, 4), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_trades_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["broker_credential_id"], ["broker_credentials.id"],
            name="fk_trades_broker_credential_id_broker_credentials",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["strategy_id"], ["strategies.id"],
            name="fk_trades_strategy_id_strategies",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_trades"),
    )
    op.create_index("ix_trades_user_id", "trades", ["user_id"])
    op.create_index("ix_trades_broker_order_id", "trades", ["broker_order_id"])

    # ── kill_switch_config ─────────────────────────────────────────────
    op.create_table(
        "kill_switch_config",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "max_daily_loss_inr",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="10000",
        ),
        sa.Column("max_daily_trades", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "auto_square_off", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_kill_switch_config_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_kill_switch_config"),
    )

    # ── kill_switch_events ─────────────────────────────────────────────
    op.create_table(
        "kill_switch_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("daily_pnl_at_trigger", sa.Numeric(18, 2), nullable=False),
        sa.Column(
            "positions_squared_off",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reset_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_kill_switch_events_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reset_by"], ["users.id"],
            name="fk_kill_switch_events_reset_by_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_kill_switch_events"),
    )
    op.create_index("ix_kill_switch_events_user_id", "kill_switch_events", ["user_id"])

    # ── idempotency_keys ───────────────────────────────────────────────
    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signal_hash", sa.String(128), nullable=False),
        sa.Column("webhook_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_idempotency_keys_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["webhook_event_id"], ["webhook_events.id"],
            name="fk_idempotency_keys_webhook_event_id_webhook_events",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_idempotency_keys"),
        sa.UniqueConstraint("signal_hash", name="uq_idempotency_keys_signal_hash"),
    )
    op.create_index("ix_idempotency_keys_user_id", "idempotency_keys", ["user_id"])
    op.create_index(
        "ix_idempotency_keys_signal_hash", "idempotency_keys", ["signal_hash"]
    )
    op.create_index(
        "ix_idempotency_keys_expires_at", "idempotency_keys", ["expires_at"]
    )

    # ── audit_logs ─────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor", ACTOR_TYPE_ENUM, nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_audit_logs_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # ── copy_trading_groups ────────────────────────────────────────────
    op.create_table(
        "copy_trading_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("master_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["master_user_id"], ["users.id"],
            name="fk_copy_trading_groups_master_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_copy_trading_groups"),
    )
    op.create_index(
        "ix_copy_trading_groups_master_user_id",
        "copy_trading_groups",
        ["master_user_id"],
    )

    # ── copy_trading_followers ─────────────────────────────────────────
    op.create_table(
        "copy_trading_followers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "follower_credential_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "quantity_multiplier",
            sa.Numeric(10, 4),
            nullable=False,
            server_default="1.0",
        ),
        sa.Column("max_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["group_id"], ["copy_trading_groups.id"],
            name="fk_copy_trading_followers_group_id_copy_trading_groups",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["follower_credential_id"], ["broker_credentials.id"],
            name="fk_copy_trading_followers_follower_credential_id_broker_credentials",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_copy_trading_followers"),
    )
    op.create_index(
        "ix_copy_trading_followers_group_id",
        "copy_trading_followers",
        ["group_id"],
    )


def downgrade() -> None:
    op.drop_table("copy_trading_followers")
    op.drop_table("copy_trading_groups")
    op.drop_table("audit_logs")
    op.drop_table("idempotency_keys")
    op.drop_table("kill_switch_events")
    op.drop_table("kill_switch_config")
    op.drop_table("trades")
    op.drop_table("webhook_events")
    op.drop_table("strategies")
    op.drop_table("webhook_tokens")
    op.drop_table("broker_credentials")
    op.drop_table("users")
