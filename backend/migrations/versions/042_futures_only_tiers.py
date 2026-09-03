"""Tier features tell the truth: FUTURES only, cash + options coming soon.

WHY. 041 made SEGMENT the price ladder — starter CASH, pro CASH+OPTIONS,
premium all three. The platform executes NONE of that except futures:

  * options fan-out is hard-skipped, by design and with a log line
    (``fanout.options_not_supported_skip``, marketplace_fanout.py) — an options
    strategy mirrors no order for any subscriber, ever;
  * cash appears only as a SIZING branch (shares instead of lots), never an
    execution path.

So the ladder as shipped sold, at 999/mo, a tier whose entire segment offering
could not execute a single order — and the same at 2499/mo. Only premium
worked. That is not a wording problem; it is the product being advertised
backwards, and the fix is the data.

Every tier becomes FUTURES only, with cash and options named as coming soon
rather than silently dropped. The founder's decision, taken with the
consequence stated: PRICES ARE UNCHANGED, so segment stops being the
differentiator and the ladder now rests on strategy count, analytics/telegram/
csv, and support. That Pro(3) and Premium(all) are today the same thing —
only three strategies exist — is a pricing question, deliberately NOT solved
here.

TWO CLAIMS ALSO GO, both of the same class:

  * ``shadowSl`` — "Shadow Stop-Loss", advertised true on premium, has NO
    backend implementation whatsoever. The only backend matches for "shadow"
    are candle-wick indicator maths. The KEY IS DROPPED, not set false,
    following 041's own precedent for ``brokers``: a flag false on every tier
    renders an empty comparison row, which is noise pretending to be a
    feature. Its ``featureRows`` entry goes with it.
  * the AI wording. ``ai`` STAYS true on premium — the validator genuinely
    exists (services/ai_validator.py::validate_signal) — but the label drops
    the "Smart Signals" framing, which reads as a gate that filters trades. On
    the live strategy it has rejected 0 of 40 signals. It is an advisory
    score, and now says so.

NEW KEY ``comingSoon``. Cash and options are named per tier rather than left
to silence, and render in their OWN comparison row labelled "not included", so
the promise cannot be misread as part of the plan.

SAFE TO RUN. ``feature_limits`` is DISPLAY-ONLY — nothing gates behaviour on
it (verified: its only readers are the pricing/billing GET endpoints). No
customer is affected either way: at the time of writing every user row is
``plan_status='none'`` with a NULL ``active_plan_id``, and razorpay_payments
holds 0 rows. This is copy, before the first sale.

DOWNGRADE IS REAL, NOT A STUB: it restores each row's feature_limits to the
EXACT JSON live today — which is 041's version, NOT 031's seed and NOT 039's.
Restoring an older one would silently undo 041's whole tier restructure.
Captured from prod on 2026-09-03; the md5 of each restored blob is asserted in
the migration test, so a drifted byte fails loudly instead of quietly.

``feature_limits`` is a ``json`` column (031) — key order and spacing are
preserved verbatim, which is what makes that md5 a real fingerprint.

Revision ID: 042_futures_only_tiers
Revises: 041_plan_tenors_tiers
Create Date: 2026-09-03
"""

from __future__ import annotations

import json

from alembic import op

revision: str = "042_futures_only_tiers"
down_revision: str | None = "041_plan_tenors_tiers"
branch_labels: str | None = None
depends_on: str | None = None


#: What the platform can actually execute today. One entry, deliberately.
_LIVE_SEGMENTS = ["FUTURES"]
#: Named, not silently dropped — a promise beats a gap.
_COMING_SOON = ["CASH", "OPTIONS"]
#: The one bullet repeated on every card. It is repeated ON PURPOSE: it
#: explains why all three tiers say the same thing, and turns the removal of
#: two segments into a stated roadmap instead of an unexplained absence.
_SEGMENT_BULLET = "Futures only — cash & options coming soon"


# ── NEW: honest tier structure ────────────────────────────────────────
# Prices untouched. `shadowSl` is ABSENT by design (see docstring), so a
# missing key here is the change, not an oversight.
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
        "telegram": True,
        "csv": True,
        "ai": False,
        "support": "Priority",
        "bullets": [
            "3 strategies",
            _SEGMENT_BULLET,
            "Long + Short",
            "Analytics + Telegram alerts + CSV export",
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
        "telegram": True,
        "csv": True,
        # Kept — the validator exists. The NAME is what changed: an advisory
        # score, not a filter that rejects trades.
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


# ── EXACT current feature_limits, captured from PROD 2026-09-03 ───────
# This is 041's version — the live one. Key order matches the stored bytes so
# the downgrade round-trips to the same md5 (see test_042_futures_only_tiers).
#   starter 00fdb70e0a3280b20d58d2962aa2c3ab
#   pro     afaf161f36eb067af0c8a5db38a815c3
#   premium 17044e6263a601d2e463618f6118d3e2
OLD_FEATURES: dict[str, dict] = {
    "starter": {
        "popular": False,
        "strategies": 1,
        "segments": ["CASH"],
        "directions": ["long"],
        "killSwitch": True,
        "analytics": False,
        "telegram": False,
        "csv": False,
        "ai": False,
        "shadowSl": False,
        "support": "Email",
        "bullets": [
            "1 strategy",
            "CASH only",
            "Long only",
            "Kill Switch",
            "Email support",
        ],
    },
    "pro": {
        "popular": True,
        "strategies": 3,
        "segments": ["CASH", "OPTIONS"],
        "directions": ["long", "short"],
        "killSwitch": True,
        "analytics": True,
        "telegram": True,
        "csv": True,
        "ai": False,
        "shadowSl": False,
        "support": "Priority",
        "bullets": [
            "3 strategies",
            "CASH + OPTIONS",
            "Long + Short",
            "Kill Switch + Analytics",
            "Priority support",
        ],
    },
    "premium": {
        "popular": False,
        "strategies": "all",
        "segments": ["CASH", "OPTIONS", "FUTURES"],
        "directions": ["long", "short"],
        "killSwitch": True,
        "analytics": True,
        "telegram": True,
        "csv": True,
        "ai": True,
        "shadowSl": True,
        "support": "Direct founder support",
        "bullets": [
            "All strategies",
            "CASH + OPTIONS + FUTURES",
            "Long + Short",
            "AI Smart Signals",
            "Direct founder support",
        ],
    },
}

#: md5 of each row's stored bytes BEFORE this migration — the fingerprint the
#: downgrade must reproduce. Asserted by the migration test in both
#: directions; a mismatch means prod drifted from what was captured and the
#: downgrade would restore the wrong thing.
PRE_042_FINGERPRINTS: dict[str, str] = {
    "starter": "00fdb70e0a3280b20d58d2962aa2c3ab",
    "pro": "afaf161f36eb067af0c8a5db38a815c3",
    "premium": "17044e6263a601d2e463618f6118d3e2",
}


def _set_features(tier: str, blob: dict) -> None:
    """Per-tier UPDATE keyed on ``tier`` — never a blanket rewrite, so a
    hand-edited row cannot be clobbered by an assumption about the others.
    Same helper shape as 041, deliberately."""
    payload = json.dumps(blob).replace("'", "''")
    op.execute(
        f"UPDATE subscription_plans SET feature_limits = '{payload}'::json, "
        f"updated_at = NOW() WHERE tier = '{tier}'"
    )


def upgrade() -> None:
    for tier, blob in NEW_FEATURES.items():
        _set_features(tier, blob)


def downgrade() -> None:
    # Restore the EXACT pre-042 JSON (041's version — not 031's, not 039's).
    for tier, blob in OLD_FEATURES.items():
        _set_features(tier, blob)
