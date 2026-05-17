"""``strategy_templates`` + ``strategy_template_origin`` tables.

Phase 1 of the Strategy Template System. Adds two new tables:

1. ``strategy_templates`` — the 113-entry catalog. 15 active equity
   templates with full ``config_json``; 35 cataloged-but-inactive
   equity entries (metadata only, ``is_active = FALSE``,
   ``config_json = '{}'``); 63 cataloged-but-inactive options entries
   (metadata only, ``requires_options_builder = TRUE``).

2. ``strategy_template_origin`` — linking table that records which
   template a strategy was cloned from. Keeps the existing
   ``strategies`` table untouched (per the Phase 1 new-files-preferred
   doctrine — no ALTER on existing tables).

Additive only. No ALTER, no DROP, no changes to existing tables.
Fully reversible via :func:`downgrade`.

Revision ID: 026_add_strategy_templates
Revises: 025_add_trade_markers
Create Date: 2026-05-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "026_add_strategy_templates"
down_revision: str | None = "025_add_trade_markers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_SEGMENT_VALUES = "'EQUITY', 'FUTURES', 'OPTIONS', 'COMMODITY', 'CURRENCY'"
_INSTRUMENT_TYPE_VALUES = (
    "'CASH', 'FUTURES', 'CALL', 'PUT', 'MULTI_LEG'"
)
_COMPLEXITY_VALUES = (
    "'beginner', 'intermediate', 'advanced', 'expert'"
)
_RISK_LEVEL_VALUES = "'low', 'medium', 'high'"


def upgrade() -> None:
    op.create_table(
        "strategy_templates",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("segment", sa.String(32), nullable=False),
        sa.Column("instrument_type", sa.String(32), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("complexity", sa.String(32), nullable=False),
        sa.Column("description_en", sa.Text(), nullable=False),
        sa.Column(
            "description_hi",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "config_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("risk_level", sa.String(32), nullable=False),
        sa.Column(
            "recommended_capital_inr",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "timeframe", sa.String(16), nullable=False, server_default=sa.text("'5m'")
        ),
        sa.Column(
            "indicators_used",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "index_filter",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "requires_options_builder",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column("legs_count", sa.Integer(), nullable=True),
        sa.Column(
            "display_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
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
        # ── Constraints — enum-vocabulary gates ────────────────────
        sa.CheckConstraint(
            f"segment IN ({_SEGMENT_VALUES})",
            name="ck_strategy_templates_segment",
        ),
        sa.CheckConstraint(
            f"instrument_type IN ({_INSTRUMENT_TYPE_VALUES})",
            name="ck_strategy_templates_instrument_type",
        ),
        sa.CheckConstraint(
            f"complexity IN ({_COMPLEXITY_VALUES})",
            name="ck_strategy_templates_complexity",
        ),
        sa.CheckConstraint(
            f"risk_level IN ({_RISK_LEVEL_VALUES})",
            name="ck_strategy_templates_risk_level",
        ),
        sa.CheckConstraint(
            "recommended_capital_inr >= 0",
            name="ck_strategy_templates_capital_non_negative",
        ),
        sa.CheckConstraint(
            "(requires_options_builder = FALSE) OR (segment = 'OPTIONS')",
            name="ck_strategy_templates_options_builder_segment",
        ),
        sa.CheckConstraint(
            "(legs_count IS NULL) OR (legs_count BETWEEN 1 AND 6)",
            name="ck_strategy_templates_legs_count_range",
        ),
    )

    # Unique slug (enforced via the column UNIQUE constraint we'll
    # express here as an explicit unique index — same semantics, makes
    # the index name predictable for migration audit).
    op.create_index(
        "uq_strategy_templates_slug",
        "strategy_templates",
        ["slug"],
        unique=True,
    )

    # Filter indexes — match the four most common picker filters.
    op.create_index(
        "ix_strategy_templates_category",
        "strategy_templates",
        ["category"],
    )
    op.create_index(
        "ix_strategy_templates_complexity",
        "strategy_templates",
        ["complexity"],
    )
    op.create_index(
        "ix_strategy_templates_segment",
        "strategy_templates",
        ["segment"],
    )
    op.create_index(
        "ix_strategy_templates_instrument_type",
        "strategy_templates",
        ["instrument_type"],
    )
    op.create_index(
        "ix_strategy_templates_is_active",
        "strategy_templates",
        ["is_active"],
    )

    # ── strategy_template_origin — linking table, additive only ────
    # Records which template a strategy was cloned from. Composite
    # (strategy_id PK) FK to strategies(id) so the link cascades on
    # strategy delete; FK to strategy_templates(id) so accidental
    # template delete RESTRICTS (don't orphan the trace).
    op.create_table(
        "strategy_template_origin",
        sa.Column(
            "strategy_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("strategies.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "template_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("strategy_templates.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "template_slug",
            sa.String(128),
            nullable=False,
        ),
        sa.Column(
            "cloned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_strategy_template_origin_template_slug",
        "strategy_template_origin",
        ["template_slug"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_strategy_template_origin_template_slug",
        table_name="strategy_template_origin",
    )
    op.drop_table("strategy_template_origin")

    op.drop_index(
        "ix_strategy_templates_is_active", table_name="strategy_templates"
    )
    op.drop_index(
        "ix_strategy_templates_instrument_type", table_name="strategy_templates"
    )
    op.drop_index(
        "ix_strategy_templates_segment", table_name="strategy_templates"
    )
    op.drop_index(
        "ix_strategy_templates_complexity", table_name="strategy_templates"
    )
    op.drop_index(
        "ix_strategy_templates_category", table_name="strategy_templates"
    )
    op.drop_index(
        "uq_strategy_templates_slug", table_name="strategy_templates"
    )
    op.drop_table("strategy_templates")
