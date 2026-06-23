"""Marketplace fan-out — module-level safety contract (M0 + M1).

Pins the invariants that hold regardless of DB state:

    (a) ``settings.marketplace_fanout_enabled`` exists and defaults to False
        (mirrors ``paywall_enforced``) — so the platform stays owner-only 1->1.
    (b) Call-site discipline: the SACRED execution files
        (``strategy_executor`` / ``signal_execution`` / ``direct_exit``) never
        reference the fan-out module, and the webhook is the ONE allowed
        importer/call site (added in Module 1, flag-gated + log-only).
    (c) ``dispatch_subscriber_executions`` is still a pure no-op stub.

The read-only ``resolve_active_subscriptions`` query + the flag-gated webhook
behaviour are covered against a real DB in
``tests/integration/test_marketplace_fanout_webhook.py``.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from types import SimpleNamespace

import app
from app.core.config import Settings, get_settings
from app.services import marketplace_fanout

# Resolve the installed ``app`` package dir so the source-scan assertions work
# regardless of the test runner's cwd.
APP_DIR = Path(app.__file__).resolve().parent

# The owner 1->1 execution core. These must NEVER reference the fan-out module
# — fan-out runs only as an additive, flag-gated hook in the webhook, never in
# the executor / worker / exit path.
SACRED_EXECUTION_FILES = [
    APP_DIR / "services" / "strategy_executor.py",
    APP_DIR / "tasks" / "signal_execution.py",
    APP_DIR / "services" / "direct_exit.py",
]

# The single sanctioned call site (Module 1 wired a flag-gated, log-only hook).
WEBHOOK_REL = "api/strategy_webhook.py"


# ── (a) flag exists + defaults False ──────────────────────────────────


def test_flag_field_exists_and_defaults_false():
    assert "marketplace_fanout_enabled" in Settings.model_fields
    field = Settings.model_fields["marketplace_fanout_enabled"]
    assert field.default is False


def test_flag_runtime_value_is_false_by_default():
    # In the test environment the env var is unset, so the switch reads False
    # — owner-only 1->1 execution.
    assert get_settings().marketplace_fanout_enabled is False
    assert marketplace_fanout.fanout_enabled() is False


# ── (b) call-site discipline ──────────────────────────────────────────


def test_sacred_execution_files_never_reference_fanout():
    for path in SACRED_EXECUTION_FILES:
        assert path.exists(), f"expected sacred file missing: {path}"
        source = path.read_text(encoding="utf-8")
        assert "marketplace_fanout" not in source, (
            f"{path.name} references marketplace_fanout — the executor / worker "
            f"/ exit path must stay free of fan-out; the only call site is the "
            f"webhook."
        )


def test_webhook_is_the_only_importer_under_app():
    # The webhook is the single sanctioned importer. A docstring path-mention
    # (e.g. in config.py) is not an import and is intentionally not matched.
    importers: list[str] = []
    for py in APP_DIR.rglob("*.py"):
        if py.name == "marketplace_fanout.py":
            continue
        text = py.read_text(encoding="utf-8")
        if (
            "from app.services.marketplace_fanout" in text
            or "import marketplace_fanout" in text
        ):
            importers.append(str(py.relative_to(APP_DIR)))
    assert importers == [WEBHOOK_REL], (
        f"exactly one importer expected ({WEBHOOK_REL}); got {importers}"
    )


# ── (c) per-subscriber PAPER dispatch (Module 2) ──────────────────────


def _fake_signal(**overrides):
    base = {
        "id": uuid.uuid4(),
        "symbol": "NIFTY",
        "action": "ENTRY",
        "raw_payload": {"side": "long", "price": 100.0},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _fake_strategy(entry_lots=2, is_paper=True):
    return SimpleNamespace(id=uuid.uuid4(), entry_lots=entry_lots, is_paper=is_paper)


def _subs(n):
    return [
        marketplace_fanout.SubscriberRef(
            subscription_id=uuid.uuid4(),
            subscriber_id=uuid.uuid4(),
            listing_id=uuid.uuid4(),
            status="active",
            subscribed_at=None,
            access_until=None,
        )
        for _ in range(n)
    ]


def _dispatch(signal, strategy, subscribers):
    return asyncio.run(
        marketplace_fanout.dispatch_subscriber_executions(
            signal=signal, strategy=strategy, subscribers=subscribers, db=None
        )
    )


def test_dispatch_runs_one_paper_fill_per_subscriber():
    subs = _subs(3)
    results = _dispatch(_fake_signal(), _fake_strategy(entry_lots=3), subs)

    assert len(results) == 3
    assert all(r.paper is True for r in results)
    assert all(r.status == "filled" for r in results)
    assert all(r.broker_order_id and r.broker_order_id.startswith("PAPER-") for r in results)
    assert all(r.quantity == 3 for r in results)  # strategy default (entry_lots), lot_size 1
    # exactly one result per subscriber
    assert {r.subscription_id for r in results} == {s.subscription_id for s in subs}


def test_dispatch_is_paper_even_when_live_flags_are_set(monkeypatch):
    import app.services.strategy_executor as se

    live_calls: list[int] = []
    # If the subscriber path ever routed through the live execution entry, this
    # spy would record it. It must stay empty.
    monkeypatch.setattr(se, "place_strategy_orders", lambda *a, **k: live_calls.append(1))

    # Global paper mode OFF + strategy.is_paper False — subscribers must STILL
    # be paper (this module ignores both flags for subscribers).
    monkeypatch.setenv("STRATEGY_PAPER_MODE", "false")
    get_settings.cache_clear()
    try:
        results = _dispatch(_fake_signal(), _fake_strategy(is_paper=False), _subs(2))
        assert all(r.paper is True for r in results)
        assert all(r.broker_order_id.startswith("PAPER-") for r in results)
        assert live_calls == [], "subscribers must never hit the live execution entry"
    finally:
        get_settings.cache_clear()


def test_dispatch_isolates_one_failing_subscriber(monkeypatch):
    state = {"n": 0}

    def _flaky(signal, quantity):
        state["n"] += 1
        if state["n"] == 2:
            raise RuntimeError("simulated boom")
        return {
            "broker_order_id": f"PAPER-{state['n']}",
            "status": "complete",
            "avg_price": None,
            "quantity": quantity,
            "raw": {},
        }

    monkeypatch.setattr("app.services.strategy_executor._simulate_fill", _flaky)

    results = _dispatch(_fake_signal(), _fake_strategy(), _subs(3))

    # Middle subscriber failed; the others still filled — and no exception escaped.
    assert [r.status for r in results] == ["filled", "failed", "filled"]
    assert results[1].error and "boom" in results[1].error
    assert results[0].broker_order_id and results[2].broker_order_id
