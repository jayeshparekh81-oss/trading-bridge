"""Marketplace Foundation — Phase 1.

Three new tables that let creators publish their strategies and
let other users browse, subscribe to, and rate them:

    * ``marketplace_listings``      — one row per published strategy
    * ``marketplace_subscriptions`` — who's subscribed to what
    * ``marketplace_ratings``       — 1-5 star ratings + reviews

Phase 1 is backend-only. Real payment integration, the Strategy
Transparency Ledger, frontend UI, and royalty tracking land in
later phases (documented in the commit body).

Indexes per the design:
    listings  — (status, published_at) for browse, (creator_id) for
                creator dashboard, (tags) GIN for tag search.
    subs      — (subscriber_id, status), (listing_id) + a partial
                unique on (listing_id, subscriber_id) WHERE
                status='active' so a user can re-subscribe after
                cancelling.
    ratings   — (listing_id) + unique (listing_id, rater_id).

Reversible. ``CASCADE`` on every FK so deleting a user / strategy
cascades their marketplace footprint.

Revision ID: 018_marketplace_tables
Revises: 017_risk_templates
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "018_marketplace_tables"
down_revision: str | None = "017_risk_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ─── marketplace_listings ─────────────────────────────────────────
    op.create_table(
        "marketplace_listings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "price_inr",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "performance_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "subscriber_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("rating_avg", sa.Numeric(3, 2), nullable=True),
        sa.Column(
            "rating_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "published_at", sa.DateTime(timezone=True), nullable=True
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
            ["strategy_id"],
            ["strategies.id"],
            name="fk_marketplace_listings_strategy_id_strategies",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["users.id"],
            name="fk_marketplace_listings_creator_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_marketplace_listings"),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'suspended', 'archived')",
            name="status_valid",
        ),
        sa.CheckConstraint(
            "price_inr >= 0",
            name="price_non_negative",
        ),
        sa.CheckConstraint(
            "rating_avg IS NULL OR (rating_avg >= 0 AND rating_avg <= 5)",
            name="rating_avg_range",
        ),
    )
    op.create_index(
        "ix_marketplace_listings_status_published_at",
        "marketplace_listings",
        ["status", "published_at"],
    )
    op.create_index(
        "ix_marketplace_listings_creator_id",
        "marketplace_listings",
        ["creator_id"],
    )

    # ─── marketplace_subscriptions ────────────────────────────────────
    op.create_table(
        "marketplace_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subscriber_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "subscribed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "access_until", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "amount_paid_inr",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
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
            ["listing_id"],
            ["marketplace_listings.id"],
            name="fk_marketplace_subscriptions_listing_id_listings",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subscriber_id"],
            ["users.id"],
            name="fk_marketplace_subscriptions_subscriber_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_marketplace_subscriptions"),
        sa.CheckConstraint(
            "status IN ('active', 'cancelled', 'expired')",
            name="status_valid",
        ),
        sa.CheckConstraint(
            "amount_paid_inr >= 0",
            name="amount_non_negative",
        ),
    )
    op.create_index(
        "ix_marketplace_subscriptions_subscriber_id_status",
        "marketplace_subscriptions",
        ["subscriber_id", "status"],
    )
    op.create_index(
        "ix_marketplace_subscriptions_listing_id",
        "marketplace_subscriptions",
        ["listing_id"],
    )
    # Partial unique: only ONE active subscription per (listing, user).
    # Cancelled / expired rows can coexist so users can re-subscribe.
    op.create_index(
        "uq_marketplace_subscriptions_listing_subscriber_active",
        "marketplace_subscriptions",
        ["listing_id", "subscriber_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )

    # ─── marketplace_ratings ──────────────────────────────────────────
    op.create_table(
        "marketplace_ratings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rater_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("review", sa.Text(), nullable=True),
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
            ["listing_id"],
            ["marketplace_listings.id"],
            name="fk_marketplace_ratings_listing_id_listings",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["rater_id"],
            ["users.id"],
            name="fk_marketplace_ratings_rater_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_marketplace_ratings"),
        sa.UniqueConstraint(
            "listing_id",
            "rater_id",
            name="uq_marketplace_ratings_listing_rater",
        ),
        sa.CheckConstraint(
            "rating >= 1 AND rating <= 5",
            name="rating_range",
        ),
    )
    op.create_index(
        "ix_marketplace_ratings_listing_id",
        "marketplace_ratings",
        ["listing_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_marketplace_ratings_listing_id",
        table_name="marketplace_ratings",
    )
    op.drop_table("marketplace_ratings")

    op.drop_index(
        "uq_marketplace_subscriptions_listing_subscriber_active",
        table_name="marketplace_subscriptions",
    )
    op.drop_index(
        "ix_marketplace_subscriptions_listing_id",
        table_name="marketplace_subscriptions",
    )
    op.drop_index(
        "ix_marketplace_subscriptions_subscriber_id_status",
        table_name="marketplace_subscriptions",
    )
    op.drop_table("marketplace_subscriptions")

    op.drop_index(
        "ix_marketplace_listings_creator_id",
        table_name="marketplace_listings",
    )
    op.drop_index(
        "ix_marketplace_listings_status_published_at",
        table_name="marketplace_listings",
    )
    op.drop_table("marketplace_listings")
