"""Feature-flag store tests.

Covers default resolution, runtime overrides, env overrides (with
case-insensitivity and invalid-value fallthrough), unknown-flag
errors, snapshot ordering, audit emission for critical-flag
mutations, threading, determinism, and AST-level dependency hygiene.
"""

from __future__ import annotations

import ast
import threading
from collections.abc import Generator
from pathlib import Path

import pytest

from app.strategy_engine.audit import clear_audit_log, query_events
from app.strategy_engine.feature_flags import (
    FeatureFlag,
    FlagsSnapshot,
    UnknownFlagError,
    get_all_flags,
    get_flag,
    is_enabled,
    reset_all_flags,
    reset_flag,
    set_flag,
)
from app.strategy_engine.feature_flags.constants import (
    CRITICAL_FLAGS,
    ENV_PREFIX,
)
from app.strategy_engine.feature_flags.registry import known_flags

_LOCKED_FLAGS: tuple[str, ...] = (
    "PINE_IMPORT_ENABLED",
    "LIVE_TRADING_ENABLED",
    "MARKETPLACE_ENABLED",
    "AUTO_DISCOVERY_ENABLED",
    "EXPERT_MODE_ENABLED",
    "LLM_ADVISOR_ENABLED",
    "STRATEGY_TRUTH_ENABLED",
    "MARKET_REGIME_ENABLED",
    "DEVIATION_MONITOR_ENABLED",
    "PAPER_TRADING_ENABLED",
    "BROKER_GUARD_ENABLED",
    "AUDIT_LOG_ENABLED",
    "HYPNOTIC_POLISH_ENABLED",
)


@pytest.fixture(autouse=True)
def _isolated_flag_store(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Reset the runtime override map and audit log before *and* after
    every test so module-level state never leaks between tests. Env
    overrides are scrubbed by removing every ``TRADETRI_FF_*`` var so
    a test in CI with a leaked env doesn't poison defaults."""
    for name, _ in list(__import__("os").environ.items()):
        if name.startswith(ENV_PREFIX):
            monkeypatch.delenv(name, raising=False)
    reset_all_flags()
    clear_audit_log()
    yield
    reset_all_flags()
    clear_audit_log()


# ─── 1. Default resolution when no override exists ────────────────────


def test_is_enabled_returns_default_when_no_override() -> None:
    # PINE_IMPORT default is True; LIVE_TRADING default is False.
    assert is_enabled("PINE_IMPORT_ENABLED") is True
    assert is_enabled("LIVE_TRADING_ENABLED") is False
    assert get_flag("PINE_IMPORT_ENABLED").source == "default"
    assert get_flag("LIVE_TRADING_ENABLED").source == "default"


# ─── 2. Runtime override beats default ────────────────────────────────


def test_set_flag_overrides_default() -> None:
    flag = set_flag("PAPER_TRADING_ENABLED", False)
    assert flag.enabled is False
    assert flag.source == "runtime_override"
    assert is_enabled("PAPER_TRADING_ENABLED") is False
    assert get_flag("PAPER_TRADING_ENABLED").source == "runtime_override"


# ─── 3. reset_flag clears runtime override ────────────────────────────


def test_reset_flag_clears_runtime_override() -> None:
    set_flag("PAPER_TRADING_ENABLED", False)
    assert is_enabled("PAPER_TRADING_ENABLED") is False
    reset_flag("PAPER_TRADING_ENABLED")
    assert is_enabled("PAPER_TRADING_ENABLED") is True
    assert get_flag("PAPER_TRADING_ENABLED").source == "default"


# ─── 4. Env override beats runtime override ───────────────────────────


def test_env_override_beats_runtime_override(monkeypatch: pytest.MonkeyPatch) -> None:
    set_flag("EXPERT_MODE_ENABLED", False)  # runtime → False
    monkeypatch.setenv(f"{ENV_PREFIX}EXPERT_MODE_ENABLED", "true")  # env → True
    assert is_enabled("EXPERT_MODE_ENABLED") is True
    assert get_flag("EXPERT_MODE_ENABLED").source == "env_override"


# ─── 5. Env values are case-insensitive ───────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("TRUE", True),
        ("True", True),
        ("true", True),
        ("YES", True),
        ("yes", True),
        ("1", True),
        ("FALSE", False),
        ("False", False),
        ("false", False),
        ("NO", False),
        ("no", False),
        ("0", False),
    ],
)
def test_env_override_case_insensitive(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: bool
) -> None:
    monkeypatch.setenv(f"{ENV_PREFIX}LIVE_TRADING_ENABLED", raw)
    assert is_enabled("LIVE_TRADING_ENABLED") is expected
    assert get_flag("LIVE_TRADING_ENABLED").source == "env_override"


# ─── 6. Invalid env value falls through to default ────────────────────


def test_invalid_env_value_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(f"{ENV_PREFIX}LIVE_TRADING_ENABLED", "maybe?")
    # LIVE_TRADING default is False; we expect the parse to be ignored
    # and the source to drop back to "default".
    assert is_enabled("LIVE_TRADING_ENABLED") is False
    assert get_flag("LIVE_TRADING_ENABLED").source == "default"


def test_invalid_env_value_falls_through_to_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the env value is unparseable but a runtime override exists,
    the runtime override wins (env layer is *skipped*, not failing)."""
    set_flag("LIVE_TRADING_ENABLED", True)
    monkeypatch.setenv(f"{ENV_PREFIX}LIVE_TRADING_ENABLED", "garbage")
    assert is_enabled("LIVE_TRADING_ENABLED") is True
    assert get_flag("LIVE_TRADING_ENABLED").source == "runtime_override"


# ─── 7. Unknown flag → UnknownFlagError ───────────────────────────────


def test_unknown_flag_raises_clear_error() -> None:
    with pytest.raises(UnknownFlagError, match="unknown feature flag"):
        is_enabled("DOES_NOT_EXIST")
    with pytest.raises(UnknownFlagError):
        get_flag("DOES_NOT_EXIST")
    with pytest.raises(UnknownFlagError):
        set_flag("DOES_NOT_EXIST", True)
    with pytest.raises(UnknownFlagError):
        reset_flag("DOES_NOT_EXIST")


def test_unknown_flag_set_does_not_mutate_state() -> None:
    """A failed set_flag must not leave a runtime override behind."""
    with pytest.raises(UnknownFlagError):
        set_flag("DOES_NOT_EXIST", True)
    snap = get_all_flags()
    # No surprise key snuck in.
    assert "DOES_NOT_EXIST" not in snap.flags
    assert set(snap.flags.keys()) == set(_LOCKED_FLAGS)


# ─── 8. get_all_flags returns every locked flag ───────────────────────


def test_get_all_flags_returns_all_locked_flags() -> None:
    snap = get_all_flags()
    assert isinstance(snap, FlagsSnapshot)
    assert len(snap.flags) == 13
    assert set(snap.flags.keys()) == set(_LOCKED_FLAGS)
    # Order matches registry definition.
    assert tuple(snap.flags.keys()) == known_flags()
    # Every entry is a fully-formed FeatureFlag.
    for flag in snap.flags.values():
        assert isinstance(flag, FeatureFlag)
        assert flag.description
        assert flag.source == "default"


# ─── 9. set_flag for LIVE_TRADING_ENABLED emits audit ─────────────────


def test_set_flag_live_trading_emits_audit() -> None:
    set_flag("LIVE_TRADING_ENABLED", True)
    result = query_events()
    assert result.filtered_count == 1
    event = result.events[0]
    assert event.severity == "critical"
    assert event.event_type == "kill_switch_triggered"
    assert event.actor == "system"
    assert event.metadata["flag_name"] == "LIVE_TRADING_ENABLED"
    assert event.metadata["enabled"] is True


# ─── 10. Disabling BROKER_GUARD emits a critical risk_block ───────────


def test_set_flag_broker_guard_disable_is_risk_block() -> None:
    set_flag("BROKER_GUARD_ENABLED", False)
    result = query_events()
    assert result.filtered_count == 1
    event = result.events[0]
    assert event.severity == "critical"
    assert event.event_type == "risk_block"
    assert event.metadata["flag_name"] == "BROKER_GUARD_ENABLED"
    assert event.metadata["enabled"] is False


def test_set_flag_broker_guard_enable_is_kill_switch_event() -> None:
    """Re-enabling the broker guard is also a critical event but
    rides on the generic kill_switch_triggered channel — only the
    *disable* of broker guard rolls up under risk_block."""
    set_flag("BROKER_GUARD_ENABLED", True)
    result = query_events()
    assert result.filtered_count == 1
    event = result.events[0]
    assert event.severity == "critical"
    assert event.event_type == "kill_switch_triggered"


def test_non_critical_flag_does_not_emit_audit() -> None:
    set_flag("HYPNOTIC_POLISH_ENABLED", False)
    assert query_events().filtered_count == 0


# ─── 11. Threading: concurrent set_flag calls don't corrupt state ─────


def test_concurrent_set_flag_does_not_corrupt_state() -> None:
    """Hammer ``set_flag`` from many threads against a non-critical
    flag (no audit traffic) and confirm the final value is one of the
    written values and the state is internally consistent."""
    n_threads = 50
    per_thread = 2  # 100 total writes.

    def worker(idx: int) -> None:
        for j in range(per_thread):
            set_flag("HYPNOTIC_POLISH_ENABLED", (idx + j) % 2 == 0)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    final = get_flag("HYPNOTIC_POLISH_ENABLED")
    assert isinstance(final.enabled, bool)  # not torn / not missing.
    assert final.source == "runtime_override"
    # And the snapshot is still fully formed.
    snap = get_all_flags()
    assert len(snap.flags) == 13


# ─── 12. Determinism: get_flag with same input → same shape ───────────


def test_get_flag_is_deterministic_in_shape() -> None:
    a = get_flag("STRATEGY_TRUTH_ENABLED")
    b = get_flag("STRATEGY_TRUTH_ENABLED")
    # last_updated may differ; everything else is stable.
    for field in ("flag_name", "enabled", "description", "default", "source"):
        assert getattr(a, field) == getattr(b, field), field
    assert a.last_updated <= b.last_updated


# ─── 13. AST inspection: no forbidden imports ─────────────────────────


_FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "app.services",
    "app.brokers",
    "app.db",
    "sqlalchemy",
    "openai",
    "anthropic",
    "httpx",
    "requests",
)


def _feature_flags_python_files() -> list[Path]:
    pkg_root = Path(__file__).resolve().parents[3] / "app" / "strategy_engine" / "feature_flags"
    return sorted(p for p in pkg_root.glob("*.py"))


def _is_forbidden(name: str) -> bool:
    if not name:
        return False
    return any(name == pref or name.startswith(pref + ".") for pref in _FORBIDDEN_PREFIXES)


@pytest.mark.parametrize("source_file", _feature_flags_python_files())
def test_feature_flags_module_does_not_import_forbidden_modules(
    source_file: Path,
) -> None:
    """Walk every import in every feature_flags *.py file and assert
    it does not pull in DB, ORM, broker SDKs, LLM SDKs, or HTTP
    libraries. The store is, by design, a pure stdlib module."""
    tree = ast.parse(source_file.read_text(), filename=str(source_file))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden(alias.name):
                    offenders.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if _is_forbidden(module):
                offenders.append(f"from {module} import …")
    assert not offenders, f"{source_file.name} pulls in forbidden modules: {offenders}"


# ─── 14. reset_all_flags clears runtime overrides ─────────────────────


def test_reset_all_flags_clears_runtime_overrides() -> None:
    set_flag("PAPER_TRADING_ENABLED", False)
    set_flag("PINE_IMPORT_ENABLED", False)
    set_flag("EXPERT_MODE_ENABLED", False)
    # Sanity: overrides took effect.
    assert is_enabled("PAPER_TRADING_ENABLED") is False
    assert is_enabled("PINE_IMPORT_ENABLED") is False
    assert is_enabled("EXPERT_MODE_ENABLED") is False

    reset_all_flags()

    # Defaults restored.
    assert is_enabled("PAPER_TRADING_ENABLED") is True
    assert is_enabled("PINE_IMPORT_ENABLED") is True
    assert is_enabled("EXPERT_MODE_ENABLED") is True
    snap = get_all_flags()
    for flag in snap.flags.values():
        assert flag.source == "default"


# ─── 15. CRITICAL_FLAGS constant matches expectations ─────────────────


def test_critical_flags_constant_is_the_expected_set() -> None:
    """Lock the CRITICAL_FLAGS set so an accidental edit to the
    constants file shows up as a test failure — disabling broker
    guard or live trading without an audit trail is exactly the
    failure mode this set protects against."""
    assert (
        frozenset({"LIVE_TRADING_ENABLED", "LLM_ADVISOR_ENABLED", "BROKER_GUARD_ENABLED"})
        == CRITICAL_FLAGS
    )


# ─── 16. Env override surfaces in get_all_flags ───────────────────────


def test_env_override_visible_in_get_all_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(f"{ENV_PREFIX}LIVE_TRADING_ENABLED", "true")
    snap = get_all_flags()
    flag = snap.flags["LIVE_TRADING_ENABLED"]
    assert flag.enabled is True
    assert flag.source == "env_override"
    # Default is unchanged in the snapshot — the source field is the
    # only signal that the env layer overrode it.
    assert flag.default is False
