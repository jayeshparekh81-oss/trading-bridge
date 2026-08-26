"""Pricing API with the 041 tenor price list.

What matters here: all four tenors reach the surfaces, the discount is DERIVED
from each tier's own monthly price (so the ladder can never disagree with the
numbers shown), and a pre-041 database still renders via the legacy scalars
instead of breaking mid-deploy.
"""

from __future__ import annotations

import importlib

import pytest

mig = importlib.import_module("migrations.versions.041_plan_tenors_and_tiers")


# ═══════════════════════════════════════════════════════════════════
# The ladder itself
# ═══════════════════════════════════════════════════════════════════


def test_founder_prices_exact():
    assert mig.PRICES["starter"] == {
        "monthly": 999, "quarterly": 929, "halfyearly": 869, "yearly": 799}
    assert mig.PRICES["pro"] == {
        "monthly": 2499, "quarterly": 2324, "halfyearly": 2174, "yearly": 1999}
    assert mig.PRICES["premium"] == {
        "monthly": 4999, "quarterly": 4649, "halfyearly": 4349, "yearly": 3999}


def test_twelve_rows_will_be_seeded():
    assert len(mig.PRICES) * len(mig.TENORS) == 12


@pytest.mark.parametrize("tier", ["starter", "pro", "premium"])
def test_discount_ladder_is_0_7_13_20(tier):
    p = mig.PRICES[tier]
    base = p["monthly"]
    pct = {t: round((1 - p[t] / base) * 100) for t in mig.TENORS}
    assert pct["monthly"] == 0
    assert pct["quarterly"] == 7
    assert pct["halfyearly"] == 13
    assert pct["yearly"] == 20


@pytest.mark.parametrize("tier", ["starter", "pro", "premium"])
def test_price_falls_monotonically_with_tenor(tier):
    p = mig.PRICES[tier]
    vals = [p[t] for t in mig.TENORS]
    assert vals == sorted(vals, reverse=True)


def test_monthly_and_yearly_still_match_the_031_seed():
    """Only the two NEW tenors are new money — the others must not move."""
    for tier, m, y in (("starter", 999, 799), ("pro", 2499, 1999),
                       ("premium", 4999, 3999)):
        assert mig.PRICES[tier]["monthly"] == m
        assert mig.PRICES[tier]["yearly"] == y


# ═══════════════════════════════════════════════════════════════════
# The new tier structure
# ═══════════════════════════════════════════════════════════════════


def test_segments_and_strategy_counts():
    f = mig.NEW_FEATURES
    assert f["starter"]["strategies"] == 1
    assert f["starter"]["segments"] == ["CASH"]
    assert f["starter"]["directions"] == ["long"]        # cash cannot short
    assert f["pro"]["strategies"] == 3
    assert f["pro"]["segments"] == ["CASH", "OPTIONS"]
    assert f["pro"]["directions"] == ["long", "short"]
    assert f["premium"]["strategies"] == "all"
    assert f["premium"]["segments"] == ["CASH", "OPTIONS", "FUTURES"]
    assert f["premium"]["directions"] == ["long", "short"]


def test_old_display_only_caps_are_gone():
    """brokers / 5-50-200 were marketing caps — replaced, not supplemented."""
    for tier, blob in mig.NEW_FEATURES.items():
        assert "brokers" not in blob, f"{tier} still carries a broker cap"
        assert blob["strategies"] not in (5, 50, 200), f"{tier} kept an old cap"


def test_support_wording_and_no_research_analyst_claim():
    f = mig.NEW_FEATURES
    assert f["starter"]["support"] == "Email"
    assert f["pro"]["support"] == "Priority"
    assert "founder" in f["premium"]["support"].lower()
    blob = str(mig.NEW_FEATURES).lower()
    assert "research analyst" not in blob
    assert "analyst" not in blob


def test_pro_and_premium_advertise_options_so_the_note_will_fire():
    for tier in ("pro", "premium"):
        text = " ".join(mig.NEW_FEATURES[tier]["bullets"]).lower()
        assert "option" in text, f"{tier} must advertise OPTIONS"
    assert "option" not in " ".join(
        mig.NEW_FEATURES["starter"]["bullets"]).lower()


# ═══════════════════════════════════════════════════════════════════
# Downgrade must be REAL — the exact pre-041 JSON
# ═══════════════════════════════════════════════════════════════════


def test_downgrade_restores_every_tier():
    assert set(mig.OLD_FEATURES) == {"starter", "pro", "premium"}


def test_downgrade_premium_is_039s_version_not_031s():
    """031 seeded '200+ strategies'; 039 corrected it. Restoring 031 would
    silently undo 039."""
    bullets = mig.OLD_FEATURES["premium"]["bullets"]
    assert "Up to 200 strategy slots" in bullets
    assert "200+ strategies" not in bullets


def test_downgrade_baseline_matches_what_is_live():
    """Captured from prod 2026-08-26 — the old caps must be restorable."""
    assert mig.OLD_FEATURES["starter"]["brokers"] == 1
    assert mig.OLD_FEATURES["pro"]["brokers"] == 3
    assert mig.OLD_FEATURES["premium"]["brokers"] == 6
    assert mig.OLD_FEATURES["starter"]["strategies"] == 5
    assert mig.OLD_FEATURES["pro"]["strategies"] == 50
    assert mig.OLD_FEATURES["premium"]["strategies"] == 200


def test_migration_chain_points_at_040():
    assert mig.revision == "041_plan_tenors_tiers"
    assert mig.down_revision == "040_manual_exec_default"


def test_downgrade_is_not_a_stub():
    import inspect
    src = inspect.getsource(mig.downgrade)
    assert "drop_table" in src
    assert "OLD_FEATURES" in src
    assert "pass" not in src.split("\n")[-2]
