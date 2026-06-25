"""Honesty fix — Premium seed bullet "200+ strategies" -> limit wording.

ADDITIVE data correction (NOT a schema change). The Premium row seeded in
031_subscription_plans carries a marketing bullet "200+ strategies" inside its
``feature_limits.bullets`` array. "200+" implies 200+ strategies exist to use,
which overstates reality — the per-plan value is a LIMIT/cap (and ~3 strategies
are live). This swaps just that one bullet string to honest, limit-accurate
wording ("Up to 200 strategy slots"), matching the /pricing matrix copy.

Surgical + idempotent: only the single offending array element is replaced (order
and every other bullet preserved), and the UPDATE is guarded so it runs only on
rows that still carry the old string — re-running is a no-op. Reversible. Prices,
plan names, tiers, broker counts, and feature checkmarks are untouched.

``feature_limits`` is a ``json`` column (migration 031), so the JSONB operators
run on a ``::jsonb`` cast; the result assigns back via the jsonb->json cast.

Kept <= 32 chars. LOCAL validation only; NOT prod.

Revision ID: 039_fix_premium_bullet
Revises: 038_exec_mode_paper
Create Date: 2026-06-25
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "039_fix_premium_bullet"
down_revision: str | None = "038_exec_mode_paper"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_BULLET = "200+ strategies"
_NEW_BULLET = "Up to 200 strategy slots"


def _swap_sql(old: str, new: str) -> str:
    """Idempotent, order-preserving swap of one bullet string in feature_limits."""
    old_sql = old.replace("'", "''")
    new_sql = new.replace("'", "''")
    return f"""
        UPDATE subscription_plans
        SET feature_limits = jsonb_set(
            feature_limits::jsonb,
            '{{bullets}}',
            (
                SELECT jsonb_agg(
                    CASE WHEN elem = to_jsonb('{old_sql}'::text)
                         THEN to_jsonb('{new_sql}'::text)
                         ELSE elem END
                    ORDER BY ord
                )
                FROM jsonb_array_elements((feature_limits::jsonb) -> 'bullets')
                     WITH ORDINALITY AS t(elem, ord)
            )
        )
        WHERE (feature_limits::jsonb) -> 'bullets' @> to_jsonb(ARRAY['{old_sql}']);
    """


def upgrade() -> None:
    op.execute(_swap_sql(_OLD_BULLET, _NEW_BULLET))


def downgrade() -> None:
    op.execute(_swap_sql(_NEW_BULLET, _OLD_BULLET))
