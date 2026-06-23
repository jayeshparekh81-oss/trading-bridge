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


# ── (c) dispatch stub is still a no-op ────────────────────────────────


def test_dispatch_subscriber_executions_is_noop():
    # Dummy sentinels — the stub ignores its args and must not raise or return.
    fake_signal = SimpleNamespace(id=uuid.uuid4())
    fake_strategy = SimpleNamespace(id=uuid.uuid4())
    assert (
        marketplace_fanout.dispatch_subscriber_executions(fake_signal, fake_strategy)
        is None
    )
