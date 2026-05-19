"""Per-strategy ``is_paper`` flag — overrides global ``strategy_paper_mode``.

Incident 2026-05-18: the global ``STRATEGY_PAPER_MODE`` was flipped True
on 2026-05-16 to make the May 18 multi-strategy launch paper-only, and
silently converted the founder's already-running BSE LTD live strategy
into paper mode. The flag was too coarse — there was no way to keep one
strategy LIVE while everything else stayed paper.

This migration adds a boolean column ``strategies.is_paper`` with
column-level ``server_default TRUE``. Resolution rule (enforced in code,
not at the schema layer):

    effective_paper_mode = (
        strategy.is_paper
        if strategy.is_paper is not None
        else settings.strategy_paper_mode
    )

i.e. the per-strategy flag wins when set; the global remains a master
fallback for any code path that bypasses the resolver. The column is
``NOT NULL`` at the DB layer so the default propagates to every row,
but the resolver still treats Python-side ``None`` as "fall back" for
defensive safety on objects constructed outside the ORM.

Backfill:
    * ``server_default=TRUE`` populates every existing row with paper=TRUE.
    * The founder's live strategy
      (``89423ecc-c76e-432c-b107-0791508542f0``) is flipped to FALSE so
      tomorrow's market open executes real Dhan orders again.

Revision ID: 027_strategies_is_paper
Revises: 026_add_strategy_templates
Create Date: 2026-05-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "027_strategies_is_paper"
down_revision: str | None = "026_add_strategy_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# The founder's BSE LTD live strategy — must remain LIVE after this
# migration so real orders resume at market open.
_FOUNDER_LIVE_STRATEGY_ID: str = "89423ecc-c76e-432c-b107-0791508542f0"


def upgrade() -> None:
    op.add_column(
        "strategies",
        sa.Column(
            "is_paper",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    # Explicit safety belt: every existing row gets paper=TRUE. The
    # column-level server_default already does this for the ALTER, but
    # restating it as a data-migration step makes the intent obvious in
    # a code review and protects against any backend whose ADD COLUMN
    # semantics differ from PostgreSQL.
    op.execute(
        sa.text(
            "UPDATE strategies SET is_paper = TRUE "
            "WHERE id != :live_id"
        ).bindparams(live_id=_FOUNDER_LIVE_STRATEGY_ID)
    )

    # Founder's live strategy → FALSE. This is the whole point of the
    # migration. If the row doesn't exist (e.g. dev DB), this is a no-op
    # — the safer outcome than failing the migration on a fresh stack.
    op.execute(
        sa.text(
            "UPDATE strategies SET is_paper = FALSE "
            "WHERE id = :live_id"
        ).bindparams(live_id=_FOUNDER_LIVE_STRATEGY_ID)
    )


def downgrade() -> None:
    op.drop_column("strategies", "is_paper")
