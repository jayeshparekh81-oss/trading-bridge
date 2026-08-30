"""The per-subscription DIRECTION FILTER, enforced.

Three rules, in order of how badly they fail if broken:

1. 🔴 EXITS ARE NEVER FILTERED. A subscriber holding a position must always be
   able to close it, whatever their filter says. Filtering an exit would strand
   someone in a position they cannot get out of — far worse than taking a side
   they did not want.

2. 🔴 THE OWNER PATH DOES NOT READ IT. ``direction_filter`` is a column on
   ``marketplace_subscriptions``. The armed live engine runs the OWNER path and
   must be provably unable to see it, so enforcing the filter cannot change what
   the live strategy does.

3. The filter itself narrows entries: long-only drops shorts, short-only drops
   longs, "all" drops nothing.

The vocabulary mismatch is the subtle part and is pinned below: ``OrderSide`` is
buy/sell, ``direction_filter`` is long/short, and ``_resolve_side`` maps
long->BUY / short->SELL. Getting that backwards would silently invert every
subscriber's filter — they would receive exactly the side they excluded.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.schemas.broker import OrderSide
from app.services.marketplace_fanout import (
    _DIRECTION_BY_SIDE,
    _direction_allows,
)

APP_DIR = Path(__file__).resolve().parents[2] / "app"


# ═══════════════════════════════════════════════════════════════════════
# 1. The filter narrows ENTRIES
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("direction_filter", "side", "allowed"),
    [
        ("all", "buy", True),
        ("all", "sell", True),
        ("long", "buy", True),
        ("long", "sell", False),   # long-only refuses a short entry
        ("short", "sell", True),
        ("short", "buy", False),   # short-only refuses a long entry
    ],
)
def test_direction_filter_narrows_entries(direction_filter, side, allowed):
    assert _direction_allows(direction_filter, side) is allowed


def test_case_and_whitespace_are_normalised():
    """"Long" must narrow as intended rather than falling through to 'all' —
    a filter that silently stops filtering is the dangerous direction."""
    assert _direction_allows("LONG", "sell") is False
    assert _direction_allows("  short  ", "buy") is False
    assert _direction_allows("Long", "buy") is True


# ═══════════════════════════════════════════════════════════════════════
# 2. 🔴 The buy/sell <-> long/short mapping, pinned to the REAL enum
# ═══════════════════════════════════════════════════════════════════════


def test_mapping_is_pinned_to_the_real_order_side_enum():
    """The module spells the enum VALUES as literals to keep its import surface
    narrow. This test is what stops those literals drifting from the enum."""
    assert dict(_DIRECTION_BY_SIDE) == {
        str(OrderSide.BUY.value): "long",
        str(OrderSide.SELL.value): "short",
    }


def test_mapping_is_not_inverted():
    """The failure this catches: a subscriber gets EXACTLY the side they
    excluded. Asserted explicitly because both directions individually 'work'
    if you swap them — only the pairing reveals it."""
    assert _direction_allows("long", OrderSide.BUY.value) is True
    assert _direction_allows("long", OrderSide.SELL.value) is False
    assert _direction_allows("short", OrderSide.SELL.value) is True
    assert _direction_allows("short", OrderSide.BUY.value) is False


# ═══════════════════════════════════════════════════════════════════════
# 3. Unrecognised values fail OPEN, loudly
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("bad", [None, "", "both", "LONGISH", "garbage", "0"])
def test_unrecognised_values_permit_rather_than_silently_kill_the_strategy(bad):
    """The column is CHECK-enforced to {all,long,short}, so these can only
    arrive via a hand-edit around the constraint. Refusing every entry on a
    malformed string looks exactly like the strategy going dead — the harder
    failure to diagnose. Permit, and log loudly instead."""
    assert _direction_allows(bad, "buy") is True
    assert _direction_allows(bad, "sell") is True


# ═══════════════════════════════════════════════════════════════════════
# 4. 🔴 EXITS ARE NEVER FILTERED
# ═══════════════════════════════════════════════════════════════════════


def test_the_gate_is_guarded_on_entry_side_being_present():
    """Source-level, because the guard is a control-flow fact rather than a
    value: the gate runs only when ``entry_side is not None``, and entry_side is
    None precisely when the dispatch is not an entry."""
    src = (APP_DIR / "services" / "marketplace_fanout.py").read_text(encoding="utf-8")
    assert "if entry_side is not None and not _direction_allows(" in src, (
        "the direction gate must be guarded on entry_side — an unguarded call "
        "would filter exits and strand subscribers in open positions"
    )


def test_exit_fanout_never_consults_the_direction_filter():
    """BEHAVIOURAL companion: the exit fan-out must not reference the filter at
    all. Scoped to the exit function so a future edit there trips this."""
    import inspect

    from app.services import marketplace_fanout as m

    exit_fn = getattr(m, "fan_out_exit", None)
    assert exit_fn is not None, "fan_out_exit not found — update this test"
    body = inspect.getsource(exit_fn)
    assert "_direction_allows" not in body
    assert "direction_filter" not in body


# ═══════════════════════════════════════════════════════════════════════
# 5. 🔴 THE OWNER PATH CANNOT SEE IT
# ═══════════════════════════════════════════════════════════════════════

#: The owner/live-money execution path. None of these may read the subscriber
#: column, or enforcing the filter could change what the ARMED engine does.
OWNER_PATH_FILES = [
    "services/strategy_executor.py",
    "services/direct_exit.py",
    "services/futures_resolver.py",
    "services/pine_mapper.py",
    "core/kill_switch.py",
    "workers/reconciliation_loop.py",
    "workers/position_loop.py",
]


def test_owner_path_never_reads_direction_filter():
    checked = 0
    for rel in OWNER_PATH_FILES:
        path = APP_DIR / rel
        if not path.exists():
            continue
        checked += 1
        src = path.read_text(encoding="utf-8")
        assert "direction_filter" not in src, (
            f"{rel} references direction_filter. That column is SUBSCRIBER "
            f"state; the owner path is what the ARMED live engine runs. If the "
            f"owner path can read it, enforcing a subscriber's filter can "
            f"change live-money behaviour."
        )
    assert checked >= 4, "owner-path file list went stale — re-check the paths"


def test_direction_filter_lives_only_on_the_subscription_model():
    """It must not have leaked onto Strategy: the strategy is the owner's."""
    strategy_model = (APP_DIR / "db" / "models" / "strategy.py").read_text(encoding="utf-8")
    assert "direction_filter" not in strategy_model

    sub_model = (
        APP_DIR / "db" / "models" / "marketplace_subscription.py"
    ).read_text(encoding="utf-8")
    assert "direction_filter" in sub_model


def test_only_the_fanout_enforces_it():
    """Exactly one place CALLS the gate. A second would be a second policy.

    Scans for the CALL form with comment lines stripped: other modules may
    legitimately NAME the function when documenting where enforcement lives
    (the settings PATCH docstring does), and a mention is not a policy.
    """
    import re

    enforcers = []
    for py in APP_DIR.rglob("*.py"):
        code = re.sub(r"#.*$", "", py.read_text(encoding="utf-8"), flags=re.M)
        code = re.sub(r'"""[\s\S]*?"""', "", code)
        if "_direction_allows(" in code:
            enforcers.append(str(py.relative_to(APP_DIR)))
    assert enforcers == ["services/marketplace_fanout.py"], enforcers
