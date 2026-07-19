"""Flip ``marketplace_subscriptions.execution_mode`` DEFAULT ``'auto'`` -> ``'offline'`` (MANUAL).

Founder decision: a NEW marketplace subscriber starts in MANUAL mode
(``execution_mode = 'offline'``) and self-enables AUTO later — copy-trades are
NOT auto-executed until the subscriber opts in. Migration 035 created the column
with ``server_default='auto'`` (contradicts the policy); this flips ONLY the
column DEFAULT so future INSERTs that omit ``execution_mode`` land on
``'offline'``.

DEFAULT-ONLY — EXISTING ROWS ARE NOT TOUCHED. ``ALTER COLUMN ... SET DEFAULT``
changes the value used for FUTURE rows only; every already-inserted subscriber
keeps its stored mode. This is deliberate:
    * an existing subscriber's ``execution_mode`` is a live intent — a subscriber
      who chose AUTO must NOT be silently switched to MANUAL (missed auto-exits);
    * the paper fan-out harness's AUTO subscriber ('sub B') is a pre-seeded row
      with an EXPLICIT ``'auto'`` value, so a default-only change leaves it
      ``'auto'`` (the AUTO-path fan-out tests keep working);
    * a data backfill would be irreversible — we could not later tell which rows
      were explicitly 'auto' vs. default-filled.

No CHECK change is needed: ``execution_mode_valid`` already permits ``'offline'``
(migrations 035 + 038 -> auto / one_click / offline / paper), so the new default
satisfies the constraint. Behaviour-preserving while the fan-out flag is OFF.
Fully reversible (downgrade restores the ``'auto'`` default; existing rows are
likewise untouched on the way back).

NOTE: this changes the DB column default ONLY. The ORM model
(``MarketplaceSubscription.execution_mode``) still declares its own Python-side
default and is intentionally NOT modified here (migration-file-only task) — that
model/DB default divergence is called out in the checkpoint report.

Revision id kept <= 32 chars (alembic ``alembic_version.version_num
VARCHAR(32)``). WRITTEN — NOT applied to prod; deployment applies it on prod's
own head.

Revision ID: 040_manual_exec_default
Revises: 039_fix_premium_bullet
Create Date: 2026-07-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "040_manual_exec_default"
down_revision: str | None = "039_fix_premium_bullet"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "marketplace_subscriptions"
_COLUMN = "execution_mode"
_OLD_DEFAULT = "auto"
_NEW_DEFAULT = "offline"  # MANUAL


def upgrade() -> None:
    # DEFAULT-ONLY: issues ``ALTER TABLE marketplace_subscriptions
    # ALTER COLUMN execution_mode SET DEFAULT 'offline'``. Affects only FUTURE
    # rows that omit execution_mode; existing rows are NOT rewritten (no
    # op.execute, no data backfill). 'offline' is already an allowed CHECK
    # value, so the constraint is untouched.
    op.alter_column(
        _TABLE,
        _COLUMN,
        existing_type=sa.String(length=16),
        existing_nullable=False,
        existing_server_default=_OLD_DEFAULT,
        server_default=_NEW_DEFAULT,
    )


def downgrade() -> None:
    # Restore the original 'auto' default. Existing rows are likewise untouched.
    op.alter_column(
        _TABLE,
        _COLUMN,
        existing_type=sa.String(length=16),
        existing_nullable=False,
        existing_server_default=_NEW_DEFAULT,
        server_default=_OLD_DEFAULT,
    )
