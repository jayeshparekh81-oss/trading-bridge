"""Marketplace Module 0 — dormant fan-out scaffold safety contract.

Pins the *inert* guarantees of M0:

    (a) ``settings.marketplace_fanout_enabled`` exists and defaults to False
        (mirrors ``paywall_enforced``) — so the platform stays owner-only 1->1.
    (b) The new module ``app.services.marketplace_fanout`` has ZERO call sites
        in the live path: the owner webhook -> executor files neither import
        nor reference it, and nothing under ``app/`` imports it.
    (c) The stubs import cleanly and are pure no-ops (return [] / None), with
        no DB / broker / Celery side effects.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import app
from app.core.config import Settings, get_settings
from app.services import marketplace_fanout

# Resolve the installed ``app`` package dir so the source-scan assertions work
# regardless of the test runner's cwd.
APP_DIR = Path(app.__file__).resolve().parent

# The owner 1->1 execution path that MUST stay free of any fan-out reference.
LIVE_PATH_FILES = [
    APP_DIR / "api" / "strategy_webhook.py",
    APP_DIR / "services" / "strategy_executor.py",
    APP_DIR / "tasks" / "signal_execution.py",
    APP_DIR / "services" / "direct_exit.py",
]


# ── (a) flag exists + defaults False ──────────────────────────────────


def test_flag_field_exists_and_defaults_false():
    assert "marketplace_fanout_enabled" in Settings.model_fields
    field = Settings.model_fields["marketplace_fanout_enabled"]
    assert field.default is False


def test_flag_runtime_value_is_false_by_default():
    # In the test environment the env var is unset, so the dormant switch
    # must read False — owner-only 1->1 execution.
    assert get_settings().marketplace_fanout_enabled is False
    assert marketplace_fanout.fanout_enabled() is False


# ── (b) zero call sites in the live owner path ────────────────────────


def test_live_path_files_never_reference_fanout_module():
    for path in LIVE_PATH_FILES:
        assert path.exists(), f"expected live-path file missing: {path}"
        source = path.read_text(encoding="utf-8")
        assert "marketplace_fanout" not in source, (
            f"{path.name} references marketplace_fanout — the M0 scaffold "
            f"must have ZERO call sites in the live owner path."
        )


def test_nothing_under_app_imports_the_fanout_module():
    # Scan every app module (except the stub itself) for an import of the
    # fan-out module. A docstring path-mention (e.g. in config.py) is not an
    # import and is intentionally not matched.
    offenders: list[str] = []
    for py in APP_DIR.rglob("*.py"):
        if py.name == "marketplace_fanout.py":
            continue
        text = py.read_text(encoding="utf-8")
        if (
            "from app.services.marketplace_fanout" in text
            or "import marketplace_fanout" in text
        ):
            offenders.append(str(py.relative_to(APP_DIR)))
    assert offenders == [], f"unexpected importers of the dormant module: {offenders}"


# ── (c) stubs import + no-op ──────────────────────────────────────────


def test_resolve_active_subscriptions_returns_empty():
    assert marketplace_fanout.resolve_active_subscriptions(uuid.uuid4()) == []


def test_dispatch_subscriber_executions_is_noop():
    # Dummy sentinels — the stub ignores its args and must not raise or return.
    fake_signal = SimpleNamespace(id=uuid.uuid4())
    fake_strategy = SimpleNamespace(id=uuid.uuid4())
    assert (
        marketplace_fanout.dispatch_subscriber_executions(fake_signal, fake_strategy)
        is None
    )
