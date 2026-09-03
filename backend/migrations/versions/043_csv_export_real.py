"""CSV export is a real feature again — ``csv`` -> true on Pro and Premium.

WHY. 042 set ``csv`` FALSE on every tier because ``GET /me/trades/export``,
while real, streamed the legacy ``trades`` table the strategy engine never
writes (0 rows on prod), and nothing in the frontend called it anyway. A
customer could not export. The rule 042 applied — a feature is sold only if a
CUSTOMER can use it — is the same rule that flips it back now:

  * ``GET /api/strategies/executions/export`` streams a CSV of EXACTLY what
    the /trades page shows (``strategy_executions``, owner-scoped,
    ``subscription_id IS NULL``), through the SAME query as the list so the
    file can never disagree with the page.
  * /trades has an "Export CSV" button (``data-testid="export-csv"``) that
    downloads it with the Bearer token attached (a bare link would 401).
  * Both are paywall-gated identically to the list they mirror.

The endpoint, the button, and the plan flag ship in the same cutover, in that
order, so the ✓ never appears before the control it describes.

WHICH TIERS. Pro and Premium — the same two that carried it before 042.
Starter stays false, as it was. Note that the gate (``require_active_plan``)
is TIER-BLIND, like every gate on the platform today: a Starter customer can
in fact export. The table describes what each tier is SOLD, not what is
enforced; per-tier enforcement is a separate, known gap.

``telegram`` stays FALSE. Alerts still reach one operator chat, not the
customer's.

DOWNGRADE IS REAL: restores 042's live values byte-for-byte. The fingerprints
of those rows were captured from prod on 2026-09-03 after 042 ran, and the
migration test asserts ``OLD_FEATURES`` reproduces them.

Revision ID: 043_csv_export_real
Revises: 042_futures_only_tiers
Create Date: 2026-09-03
"""

from __future__ import annotations

import json

from alembic import op

revision: str = "043_csv_export_real"
down_revision: str | None = "042_futures_only_tiers"
branch_labels: str | None = None
depends_on: str | None = None


_LIVE_SEGMENTS = ["FUTURES"]
_COMING_SOON = ["CASH", "OPTIONS"]
_SEGMENT_BULLET = "Futures only — cash & options coming soon"


# ── NEW: csv true where it is sold; one Pro bullet names it ───────────
NEW_FEATURES: dict[str, dict] = {
    "starter": {
        "popular": False,
        "strategies": 1,
        "segments": _LIVE_SEGMENTS,
        "comingSoon": _COMING_SOON,
        "directions": ["long"],
        "killSwitch": True,
        "analytics": False,
        "telegram": False,
        "csv": False,
        "ai": False,
        "support": "Email",
        "bullets": [
            "1 strategy",
            _SEGMENT_BULLET,
            "Long only",
            "Kill Switch",
            "Email support",
        ],
    },
    "pro": {
        "popular": True,
        "strategies": 3,
        "segments": _LIVE_SEGMENTS,
        "comingSoon": _COMING_SOON,
        "directions": ["long", "short"],
        "killSwitch": True,
        "analytics": True,
        "telegram": False,
        # TRUE — /trades → Export CSV → /api/strategies/executions/export.
        "csv": True,
        "ai": False,
        "support": "Priority",
        "bullets": [
            "3 strategies",
            _SEGMENT_BULLET,
            "Long + Short",
            "Analytics dashboard + CSV export",
            "Priority support",
        ],
    },
    "premium": {
        "popular": False,
        "strategies": "all",
        "segments": _LIVE_SEGMENTS,
        "comingSoon": _COMING_SOON,
        "directions": ["long", "short"],
        "killSwitch": True,
        "analytics": True,
        "telegram": False,
        # TRUE — same control, same endpoint.
        "csv": True,
        "ai": True,
        "support": "Direct founder support",
        "bullets": [
            "All strategies",
            _SEGMENT_BULLET,
            "Long + Short",
            "AI conviction score (advisory)",
            "Direct founder support",
        ],
    },
}


# ── EXACT post-042 feature_limits (live on prod, captured 2026-09-03) ──
#   starter 3da708b0e7e8697801723960ace162bf
#   pro     a3fdb822f26bf488adcdff324f20cd27
#   premium a01f60dae43db50c8aa53385aaddaf31
OLD_FEATURES: dict[str, dict] = {
    "starter": {
        "popular": False,
        "strategies": 1,
        "segments": ["FUTURES"],
        "comingSoon": ["CASH", "OPTIONS"],
        "directions": ["long"],
        "killSwitch": True,
        "analytics": False,
        "telegram": False,
        "csv": False,
        "ai": False,
        "support": "Email",
        "bullets": [
            "1 strategy",
            "Futures only — cash & options coming soon",
            "Long only",
            "Kill Switch",
            "Email support",
        ],
    },
    "pro": {
        "popular": True,
        "strategies": 3,
        "segments": ["FUTURES"],
        "comingSoon": ["CASH", "OPTIONS"],
        "directions": ["long", "short"],
        "killSwitch": True,
        "analytics": True,
        "telegram": False,
        "csv": False,
        "ai": False,
        "support": "Priority",
        "bullets": [
            "3 strategies",
            "Futures only — cash & options coming soon",
            "Long + Short",
            "Analytics dashboard",
            "Priority support",
        ],
    },
    "premium": {
        "popular": False,
        "strategies": "all",
        "segments": ["FUTURES"],
        "comingSoon": ["CASH", "OPTIONS"],
        "directions": ["long", "short"],
        "killSwitch": True,
        "analytics": True,
        "telegram": False,
        "csv": False,
        "ai": True,
        "support": "Direct founder support",
        "bullets": [
            "All strategies",
            "Futures only — cash & options coming soon",
            "Long + Short",
            "AI conviction score (advisory)",
            "Direct founder support",
        ],
    },
}

#: md5 of each row's stored bytes BEFORE this migration (= after 042). The
#: downgrade must reproduce these; the migration test asserts it.
PRE_043_FINGERPRINTS: dict[str, str] = {
    "starter": "3da708b0e7e8697801723960ace162bf",
    "pro": "a3fdb822f26bf488adcdff324f20cd27",
    "premium": "a01f60dae43db50c8aa53385aaddaf31",
}


def _set_features(tier: str, blob: dict) -> None:
    """Per-tier UPDATE keyed on ``tier`` — never a blanket rewrite (041/042)."""
    payload = json.dumps(blob).replace("'", "''")
    op.execute(
        f"UPDATE subscription_plans SET feature_limits = '{payload}'::json, "
        f"updated_at = NOW() WHERE tier = '{tier}'"
    )


def upgrade() -> None:
    for tier, blob in NEW_FEATURES.items():
        _set_features(tier, blob)


def downgrade() -> None:
    # Restore the EXACT post-042 JSON.
    for tier, blob in OLD_FEATURES.items():
        _set_features(tier, blob)
