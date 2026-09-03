"""Migration 043 — CSV export is real again: ``csv`` -> true on Pro + Premium.

Structural / source validation (repo convention). The fingerprint test is the
load-bearing one: ``feature_limits`` is a ``json`` column, so md5 of the stored
bytes is a real fingerprint of the live row, and asserting ``OLD_FEATURES``
reproduces the post-042 fingerprints is what proves the downgrade restores
what is ACTUALLY on prod.

The second load-bearing test ties the flag to the control: the plan may say
✓ only while the export endpoint and the /trades button both exist.
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
from pathlib import Path

import pytest

_MODULE = "migrations.versions.043_csv_export_real"
TIERS = ("starter", "pro", "premium")
_REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def module():
    return importlib.import_module(_MODULE)


def _code_only(fn) -> str:
    return "\n".join(
        line.split("#", 1)[0]
        for line in inspect.getsource(fn).splitlines()
        if line.split("#", 1)[0].strip()
    )


# ═══════════════════════════════════════════════════════════════════════
# 1. Chaining + shape
# ═══════════════════════════════════════════════════════════════════════


def test_chains_after_042(module) -> None:
    assert module.revision == "043_csv_export_real"
    assert len(module.revision) <= 32
    assert module.down_revision == "042_futures_only_tiers"


def test_data_only_no_ddl_no_prices(module) -> None:
    code = _code_only(module.upgrade) + _code_only(module.downgrade)
    for forbidden in ("create_table", "drop_table", "add_column", "drop_column",
                      "alter_column", "create_index", "drop_index"):
        assert forbidden not in code
    src = inspect.getsource(module)
    for tok in ("price_monthly_inr", "price_yearly_inr", "subscription_plan_prices"):
        assert tok not in src


def test_per_tier_updates(module) -> None:
    assert "WHERE tier =" in _code_only(module._set_features)


# ═══════════════════════════════════════════════════════════════════════
# 2. 🔴 Downgrade restores the live (post-042) bytes
# ═══════════════════════════════════════════════════════════════════════


def test_old_features_reproduce_post_042_prod_fingerprints(module) -> None:
    assert set(module.PRE_043_FINGERPRINTS) == set(TIERS)
    for tier, expected in module.PRE_043_FINGERPRINTS.items():
        got = hashlib.md5(json.dumps(module.OLD_FEATURES[tier]).encode()).hexdigest()
        assert got == expected, f"{tier}: downgrade payload != live row bytes"


def test_old_is_042s_new_not_041s(module) -> None:
    """The trap: restoring pre-042 would resurrect CASH/OPTIONS and shadowSl."""
    for tier in TIERS:
        old = module.OLD_FEATURES[tier]
        assert old["segments"] == ["FUTURES"]
        assert "shadowSl" not in old
        assert old["csv"] is False and old["telegram"] is False


# ═══════════════════════════════════════════════════════════════════════
# 3. 🔴 The change is exactly csv, on exactly Pro + Premium
# ═══════════════════════════════════════════════════════════════════════


def test_csv_true_on_pro_and_premium_only(module) -> None:
    assert module.NEW_FEATURES["starter"]["csv"] is False
    assert module.NEW_FEATURES["pro"]["csv"] is True
    assert module.NEW_FEATURES["premium"]["csv"] is True


def test_telegram_stays_false_everywhere(module) -> None:
    """Alerts still reach ONE operator chat. Not a customer feature yet."""
    for tier in TIERS:
        assert module.NEW_FEATURES[tier]["telegram"] is False


@pytest.mark.parametrize("tier", TIERS)
def test_nothing_else_moved(module, tier: str) -> None:
    old, new = module.OLD_FEATURES[tier], module.NEW_FEATURES[tier]
    assert set(old) == set(new), f"{tier}: key set changed"
    for k in old:
        if k in ("csv", "bullets"):
            continue
        assert new[k] == old[k], f"{tier}.{k} changed"


def test_only_pros_bullet_changed_and_it_names_csv(module) -> None:
    assert module.NEW_FEATURES["starter"]["bullets"] == module.OLD_FEATURES["starter"]["bullets"]
    assert module.NEW_FEATURES["premium"]["bullets"] == module.OLD_FEATURES["premium"]["bullets"]
    pro = module.NEW_FEATURES["pro"]["bullets"]
    assert any("CSV export" in b for b in pro)
    # ...and nothing sneaks telegram back in via a bullet.
    for tier in TIERS:
        assert not any("telegram" in b.lower() for b in module.NEW_FEATURES[tier]["bullets"])


# ═══════════════════════════════════════════════════════════════════════
# 4. 🔴 The ✓ exists only because the CONTROL exists
# ═══════════════════════════════════════════════════════════════════════


def test_the_endpoint_and_the_button_both_exist() -> None:
    """A plan flag is a promise about a control. Both halves must be present
    in the same tree, or the flag is 042's hollow claim all over again."""
    api = (_REPO / "backend/app/api/strategy_signals.py").read_text()
    assert '@router.get("/executions/export")' in api
    assert "require_active_plan" in api

    page = (_REPO / "frontend/src/app/(dashboard)/trades/page.tsx").read_text()
    assert 'data-testid="export-csv"' in page
    assert '"/strategies/executions/export"' in page
    # never the legacy endpoint whose table has 0 rows
    assert "/users/me/trades/export" not in page.split("*/")[-1].replace("//", "")
