"""Migration 042 — tier features tell the truth: FUTURES only.

Structural / source validation (the repo convention for migration tests — the
real ``alembic upgrade`` runs against Postgres at deploy, and was additionally
run up+down against a throwaway container before this shipped).

The load-bearing test here is the FINGERPRINT one. ``feature_limits`` is a
``json`` column, so key order and spacing are stored verbatim; the md5 of each
blob is therefore a real byte fingerprint of the live row. Asserting that
``OLD_FEATURES`` reproduces the fingerprints captured from prod is what proves
the downgrade restores what is ACTUALLY there — not 031's seed, not 039's, not
an approximation that happens to look right in a diff. 041's own downgrade
comment warns about exactly this trap; this test makes the warning executable.
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json

import pytest

_MODULE = "migrations.versions.042_futures_only_tiers"

TIERS = ("starter", "pro", "premium")


@pytest.fixture(scope="module")
def module():
    return importlib.import_module(_MODULE)


def _code_only(fn) -> str:
    """Source of ``fn`` with ``#`` comments stripped, so the forbidden-token
    checks assert on CODE and not on prose explaining what the code avoids."""
    lines = []
    for line in inspect.getsource(fn).splitlines():
        code = line.split("#", 1)[0]
        if code.strip():
            lines.append(code)
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# 1. Chaining + shape
# ═══════════════════════════════════════════════════════════════════════


def test_chains_after_041_head(module) -> None:
    assert module.revision == "042_futures_only_tiers"
    assert len(module.revision) <= 32
    assert module.down_revision == "041_plan_tenors_tiers"
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_is_data_only_no_schema_change(module) -> None:
    """No DDL. This migration rewrites three JSON blobs and nothing else."""
    code = _code_only(module.upgrade) + "\n" + _code_only(module.downgrade)
    for forbidden in (
        "create_table",
        "drop_table",
        "add_column",
        "drop_column",
        "alter_column",
        "create_index",
        "drop_index",
        "create_check_constraint",
        "create_unique_constraint",
    ):
        assert forbidden not in code, f"042 must not perform DDL, found {forbidden}"


def test_prices_are_not_touched(module) -> None:
    """The founder's explicit constraint: copy changes, prices do not."""
    source = inspect.getsource(module)
    for price_token in (
        "price_monthly_inr",
        "price_yearly_inr",
        "price_per_month_inr",
        "subscription_plan_prices",
    ):
        assert price_token not in source, (
            f"042 names {price_token} — prices were to stay untouched"
        )


def test_updates_are_per_tier_never_blanket(module) -> None:
    """Keyed on ``tier``, like 041 — a hand-edited row cannot be clobbered by
    an assumption about the others."""
    helper = _code_only(module._set_features)
    assert "WHERE tier =" in helper
    for fn in (module.upgrade, module.downgrade):
        assert "_set_features" in _code_only(fn)


# ═══════════════════════════════════════════════════════════════════════
# 2. 🔴 The downgrade restores what is ACTUALLY LIVE — byte for byte
# ═══════════════════════════════════════════════════════════════════════


def test_old_features_reproduce_the_prod_fingerprints(module) -> None:
    """Captured from prod 2026-09-03 with md5(feature_limits::text).

    If this fails, prod has drifted from what was captured and the downgrade
    would restore the WRONG bytes — fix the capture, do not relax the test.
    """
    assert set(module.PRE_042_FINGERPRINTS) == set(TIERS)
    for tier, expected in module.PRE_042_FINGERPRINTS.items():
        stored = json.dumps(module.OLD_FEATURES[tier])
        assert hashlib.md5(stored.encode()).hexdigest() == expected, (
            f"{tier}: downgrade payload does not match the live row's bytes"
        )


def test_downgrade_is_real_not_a_stub(module) -> None:
    for tier in TIERS:
        assert module.OLD_FEATURES[tier] != module.NEW_FEATURES[tier]
    assert set(module.OLD_FEATURES) == set(module.NEW_FEATURES) == set(TIERS)


def test_downgrade_restores_041_not_an_older_generation(module) -> None:
    """041 restored 039's premium, NOT 031's. The equivalent trap here is
    restoring 041's *pre*-state. These are 041's OWN post-values."""
    assert module.OLD_FEATURES["premium"]["segments"] == ["CASH", "OPTIONS", "FUTURES"]
    assert module.OLD_FEATURES["pro"]["segments"] == ["CASH", "OPTIONS"]
    assert module.OLD_FEATURES["starter"]["segments"] == ["CASH"]
    # 041 removed `brokers`; if it reappeared we would be restoring pre-041.
    for tier in TIERS:
        assert "brokers" not in module.OLD_FEATURES[tier]


# ═══════════════════════════════════════════════════════════════════════
# 3. 🔴 The claim itself: futures only, on every tier
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("tier", TIERS)
def test_every_tier_sells_only_what_executes(module, tier: str) -> None:
    blob = module.NEW_FEATURES[tier]
    assert blob["segments"] == ["FUTURES"]
    assert blob["comingSoon"] == ["CASH", "OPTIONS"]


@pytest.mark.parametrize("tier", TIERS)
def test_no_bullet_advertises_cash_or_options_as_included(module, tier: str) -> None:
    """The ONLY place cash/options may appear in the cards is the coming-soon
    bullet. Anything else re-makes the claim the migration exists to remove."""
    for bullet in module.NEW_FEATURES[tier]["bullets"]:
        mentions = "cash" in bullet.lower() or "option" in bullet.lower()
        if mentions:
            assert bullet == module._SEGMENT_BULLET, (
                f"{tier}: bullet {bullet!r} names cash/options outside the "
                "coming-soon line"
            )


def test_the_coming_soon_promise_is_actually_made(module) -> None:
    """Removing the segments without saying why would read as a silent
    downgrade. The bullet must survive on every card."""
    assert "coming soon" in module._SEGMENT_BULLET.lower()
    for tier in TIERS:
        assert module._SEGMENT_BULLET in module.NEW_FEATURES[tier]["bullets"]


# ═══════════════════════════════════════════════════════════════════════
# 4. 🔴 shadowSl is GONE, and the AI claim is de-escalated
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("tier", TIERS)
def test_shadow_stop_loss_key_is_removed_not_falsified(module, tier: str) -> None:
    """It has no backend at all. Set false it would render an empty comparison
    row on every tier — noise pretending to be a feature — so 041's precedent
    for ``brokers`` applies: drop the key."""
    assert "shadowSl" not in module.NEW_FEATURES[tier]
    # ...and it WAS there before, so this test is actually asserting a change.
    assert "shadowSl" in module.OLD_FEATURES[tier]


def test_ai_flag_survives_but_the_wording_stops_implying_a_filter(module) -> None:
    """The validator genuinely exists, so the flag stays. What goes is copy
    that reads as a gate: it has rejected 0 of 40 signals on the live
    strategy."""
    assert module.NEW_FEATURES["premium"]["ai"] is True
    assert module.NEW_FEATURES["starter"]["ai"] is False
    assert module.NEW_FEATURES["pro"]["ai"] is False

    all_bullets = [b for t in TIERS for b in module.NEW_FEATURES[t]["bullets"]]
    joined = " | ".join(all_bullets).lower()
    for banned in ("smart signal", "reject", "filters", "skipped", "why it"):
        assert banned not in joined, f"AI copy still implies a filter: {banned!r}"
    assert any("advisory" in b.lower() for b in all_bullets)


# ═══════════════════════════════════════════════════════════════════════
# 5. Key parity — the diff is exactly what was intended, nothing else
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("tier", TIERS)
def test_key_diff_is_exactly_minus_shadowsl_plus_comingsoon(module, tier: str) -> None:
    old = set(module.OLD_FEATURES[tier])
    new = set(module.NEW_FEATURES[tier])
    assert old - new == {"shadowSl"}, f"{tier}: unexpected key removal"
    assert new - old == {"comingSoon"}, f"{tier}: unexpected key addition"


@pytest.mark.parametrize("tier", TIERS)
def test_unrelated_flags_are_carried_over_untouched(module, tier: str) -> None:
    """A copy migration must not quietly re-tier the product.

    ``telegram`` and ``csv`` are deliberately EXCLUDED here — they are an
    intended change, asserted on its own below."""
    old, new = module.OLD_FEATURES[tier], module.NEW_FEATURES[tier]
    for key in ("popular", "strategies", "directions", "killSwitch",
                "analytics", "support"):
        assert new[key] == old[key], f"{tier}.{key} changed and should not have"


# ═══════════════════════════════════════════════════════════════════════
# 6. 🔴 Only features a CUSTOMER can actually use are sold
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("tier", TIERS)
def test_csv_and_telegram_are_false_everywhere(module, tier: str) -> None:
    """Neither reaches a customer today.

    csv: ``GET /me/trades/export`` streams real CSV but nothing in the
    frontend calls it — no button, no fetch. telegram: the transport is real
    but ``send_notification_task`` has zero production callers and live alerts
    go to ONE operator chat id, not per-customer.
    """
    assert module.NEW_FEATURES[tier]["csv"] is False
    assert module.NEW_FEATURES[tier]["telegram"] is False


def test_this_is_actually_a_change_not_a_no_op(module) -> None:
    """Both were sold as TRUE on pro and premium before 042."""
    for tier in ("pro", "premium"):
        assert module.OLD_FEATURES[tier]["csv"] is True
        assert module.OLD_FEATURES[tier]["telegram"] is True


@pytest.mark.parametrize("tier", TIERS)
def test_the_keys_survive_so_they_can_be_flipped_back(module, tier: str) -> None:
    """Unlike shadowSl (dropped — no implementation at all), these two have
    real machinery and return to true the day a customer can use them. The
    key must stay, or that flip becomes another migration."""
    assert "csv" in module.NEW_FEATURES[tier]
    assert "telegram" in module.NEW_FEATURES[tier]


def test_no_bullet_still_advertises_telegram_or_csv(module) -> None:
    """Pro's bullet sold exactly these two ("Analytics + Telegram alerts +
    CSV export"). Flipping the flags while leaving the bullet would keep the
    claim on the card and merely uncheck it in the table below."""
    for tier in TIERS:
        for bullet in module.NEW_FEATURES[tier]["bullets"]:
            low = bullet.lower()
            assert "telegram" not in low, f"{tier}: {bullet!r} still sells Telegram"
            assert "csv" not in low, f"{tier}: {bullet!r} still sells CSV"
            assert "export" not in low, f"{tier}: {bullet!r} still sells export"
