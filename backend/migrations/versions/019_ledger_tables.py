"""Marketplace Phase 2 — Strategy Transparency Ledger (off-chain prototype).

Two append-only tables that record an immutable cryptographic
audit trail of every published listing's daily performance:

    * ``ledger_snapshots``     — one row per (listing, day). Carries
      the day's performance numbers, a SHA-256 ``data_hash`` of all
      payload fields, the prior snapshot's ``chain_signature`` as
      ``prior_hash``, and a fresh ``chain_signature`` that links
      this row into the chain.
    * ``ledger_attestations``  — periodic attestation rows (daily,
      weekly, 30 / 60 / 90-day milestones). The ``polygon_tx_hash``
      column is reserved for Phase 4 — it stays NULL until a real
      Polygon transaction lands the attestation on-chain.

The tables are append-only by convention. Application code only
inserts; the verification API walks the chain to detect any
out-of-band UPDATE / DELETE that would invalidate the hashes.

Reversible. ``CASCADE`` on every FK so deleting a listing cleans
up its ledger atomically (Phase 4 will move "delete-able" listings
to soft-delete; for Phase 2 we keep the FK aggressive so test
isolation is simple).

Revision ID: 019_ledger_tables
Revises: 018_marketplace_tables
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "019_ledger_tables"
down_revision: str | None = "018_marketplace_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ─── ledger_snapshots ─────────────────────────────────────────────
    op.create_table(
        "ledger_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("sequence_number", sa.BigInteger(), nullable=False),
        # ─── Performance payload (immutable once written) ───
        sa.Column(
            "cumulative_pnl_inr",
            sa.Numeric(20, 4),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "max_drawdown_pct",
            sa.Numeric(7, 4),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "total_trades",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "win_rate",
            sa.Numeric(5, 4),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "sharpe_ratio", sa.Numeric(7, 4), nullable=True
        ),
        # ─── Forward-testing tracking ───
        sa.Column(
            "days_since_publish",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "paper_trades_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "live_trades_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        # ─── Cryptographic chain ───
        sa.Column("data_hash", sa.Text(), nullable=False),
        sa.Column("prior_hash", sa.Text(), nullable=True),
        sa.Column("chain_signature", sa.Text(), nullable=False),
        # ─── Audit ───
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["marketplace_listings.id"],
            name="fk_ledger_snapshots_listing_id_listings",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ledger_snapshots"),
        sa.UniqueConstraint(
            "listing_id",
            "snapshot_date",
            name="uq_ledger_snapshots_listing_date",
        ),
        sa.UniqueConstraint(
            "listing_id",
            "sequence_number",
            name="uq_ledger_snapshots_listing_sequence",
        ),
        sa.CheckConstraint(
            "sequence_number >= 1",
            name="sequence_number_positive",
        ),
        sa.CheckConstraint(
            "win_rate >= 0 AND win_rate <= 1",
            name="win_rate_unit_interval",
        ),
        sa.CheckConstraint(
            "max_drawdown_pct >= 0",
            name="max_drawdown_non_negative",
        ),
        sa.CheckConstraint(
            "total_trades >= 0",
            name="total_trades_non_negative",
        ),
    )
    op.create_index(
        "ix_ledger_snapshots_data_hash",
        "ledger_snapshots",
        ["data_hash"],
    )
    op.create_index(
        "ix_ledger_snapshots_listing_id_sequence",
        "ledger_snapshots",
        ["listing_id", "sequence_number"],
    )

    # ─── ledger_attestations ──────────────────────────────────────────
    op.create_table(
        "ledger_attestations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "attestation_type", sa.String(32), nullable=False
        ),
        sa.Column("attestation_hash", sa.Text(), nullable=False),
        sa.Column("polygon_tx_hash", sa.Text(), nullable=True),
        sa.Column(
            "attested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["ledger_snapshots.id"],
            name="fk_ledger_attestations_snapshot_id_snapshots",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ledger_attestations"),
        sa.CheckConstraint(
            "attestation_type IN ('daily_snapshot', 'weekly_summary', "
            "'milestone_30day', 'milestone_60day', 'milestone_90day')",
            name="attestation_type_valid",
        ),
    )
    op.create_index(
        "ix_ledger_attestations_snapshot_type",
        "ledger_attestations",
        ["snapshot_id", "attestation_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ledger_attestations_snapshot_type",
        table_name="ledger_attestations",
    )
    op.drop_table("ledger_attestations")

    op.drop_index(
        "ix_ledger_snapshots_listing_id_sequence",
        table_name="ledger_snapshots",
    )
    op.drop_index(
        "ix_ledger_snapshots_data_hash", table_name="ledger_snapshots"
    )
    op.drop_table("ledger_snapshots")
