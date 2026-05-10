"""Feature-flag manager — public read/write API.

Resolution order (highest priority wins):

    1. Environment variable ``TRADETRI_FF_{FLAG_NAME}`` parsed via
       :data:`TRUTHY_VALUES` / :data:`FALSY_VALUES` (case-insensitive).
       Re-read on every call so a process-env change takes effect
       without a restart.
    2. In-process runtime override set via :func:`set_flag`.
    3. Hardcoded default from :mod:`registry`.

Mutations to flags in :data:`CRITICAL_FLAGS` emit an audit event so
disabling the broker safety net or live-trading gate always leaves a
paper trail. The audit dependency is one-way — :mod:`audit` does not
import :mod:`feature_flags`.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

from app.strategy_engine.audit.emitter import emit_event
from app.strategy_engine.feature_flags import registry, store
from app.strategy_engine.feature_flags.constants import (
    CRITICAL_FLAGS,
    ENV_PREFIX,
    FALSY_VALUES,
    TRUTHY_VALUES,
)
from app.strategy_engine.feature_flags.models import (
    FeatureFlag,
    FlagSource,
    FlagsSnapshot,
)


def _read_env_override(flag_name: str) -> bool | None:
    """Return the env-parsed value for ``flag_name`` or ``None`` if
    the variable is unset / has an unrecognised value.

    Anything outside the documented truthy/falsy sets falls through
    to the next layer — we'd rather a typo silently fall back to the
    safe default than be parsed into an unintended boolean.
    """
    raw = os.environ.get(f"{ENV_PREFIX}{flag_name}")
    if raw is None:
        return None
    normalised = raw.strip().lower()
    if normalised in TRUTHY_VALUES:
        return True
    if normalised in FALSY_VALUES:
        return False
    return None


def _resolve(flag_name: str) -> tuple[bool, FlagSource]:
    """Return ``(enabled, source)`` for ``flag_name``.

    Raises :class:`registry.UnknownFlagError` if the flag isn't in
    the locked registry.
    """
    definition = registry.definition(flag_name)
    env_value = _read_env_override(flag_name)
    if env_value is not None:
        return env_value, "env_override"
    runtime_value = store.get(flag_name)
    if runtime_value is not None:
        return runtime_value, "runtime_override"
    return definition.default, "default"


def _build_flag(flag_name: str) -> FeatureFlag:
    definition = registry.definition(flag_name)
    enabled, source = _resolve(flag_name)
    return FeatureFlag(
        flag_name=flag_name,
        enabled=enabled,
        description=definition.description,
        default=definition.default,
        source=source,
        last_updated=datetime.now(UTC),
    )


def is_enabled(flag_name: str) -> bool:
    """Return the resolved boolean for ``flag_name``.

    Resolution order: env override > runtime override > default.
    Raises :class:`registry.UnknownFlagError` for unknown flags.
    """
    enabled, _ = _resolve(flag_name)
    return enabled


def get_flag(flag_name: str) -> FeatureFlag:
    """Return the full :class:`FeatureFlag` snapshot for ``flag_name``.

    Raises :class:`registry.UnknownFlagError` for unknown flags.
    """
    return _build_flag(flag_name)


def set_flag(flag_name: str, enabled: bool) -> FeatureFlag:
    """Set a runtime override for ``flag_name`` and return the new
    snapshot.

    If ``flag_name`` is in :data:`CRITICAL_FLAGS` an audit event is
    emitted at ``critical`` severity. Disabling
    ``BROKER_GUARD_ENABLED`` is additionally tagged as a
    ``risk_block`` event because it removes the live-order safety
    layer.

    Note: an active env override still wins on subsequent reads —
    setting a runtime override against an env-pinned flag is allowed
    (so tests can pre-stage state), but :func:`is_enabled` will
    continue to return the env value. The returned ``FeatureFlag``
    reflects the *resolved* value, so the caller can immediately see
    that the env layer has masked their write.

    Raises :class:`registry.UnknownFlagError` for unknown flags.
    """
    # Validate the flag name *before* taking the lock so unknown
    # flags don't briefly mutate state.
    registry.definition(flag_name)
    store.set_value(flag_name, enabled)

    flag = _build_flag(flag_name)
    if flag_name in CRITICAL_FLAGS:
        _emit_critical_audit(flag_name, enabled)
    return flag


def reset_flag(flag_name: str) -> FeatureFlag:
    """Drop the runtime override for ``flag_name`` and return the
    fresh snapshot (which will resolve from env or default).

    Raises :class:`registry.UnknownFlagError` for unknown flags.
    """
    registry.definition(flag_name)
    store.remove(flag_name)
    return _build_flag(flag_name)


def reset_all_flags() -> None:
    """Drop every runtime override. Intended for tests only — does
    not touch env variables, which the test must clear separately."""
    store.clear()


def get_all_flags() -> FlagsSnapshot:
    """Return a frozen snapshot of every locked flag in registry
    order. ``snapshot_at`` is a single timestamp for the whole snapshot
    so the caller can correlate flags taken at the same instant."""
    now = datetime.now(UTC)
    flags: dict[str, FeatureFlag] = {}
    for name in registry.known_flags():
        defn = registry.definition(name)
        enabled, source = _resolve(name)
        flags[name] = FeatureFlag(
            flag_name=name,
            enabled=enabled,
            description=defn.description,
            default=defn.default,
            source=source,
            last_updated=now,
        )
    return FlagsSnapshot(flags=flags, snapshot_at=now)


def _emit_critical_audit(flag_name: str, enabled: bool) -> None:
    """Audit log entry for a runtime mutation of a critical flag.

    Disabling the broker guard is recorded as a ``risk_block`` event
    because it removes the live-order safety layer. Every other
    critical mutation (live-trading toggle, LLM advisor toggle, or
    enabling the broker guard) is recorded as a ``kill_switch_triggered``
    event so the security view sees the change.
    """
    state = "enabled" if enabled else "disabled"
    summary = f"Feature flag {flag_name} {state} via runtime override"

    if flag_name == "BROKER_GUARD_ENABLED" and not enabled:
        emit_event(
            event_type="risk_block",
            actor="system",
            summary="Broker guard disabled via feature flag — live-order safety net removed",
            severity="critical",
            metadata={"flag_name": flag_name, "enabled": enabled},
        )
        return

    emit_event(
        event_type="kill_switch_triggered",
        actor="system",
        summary=summary,
        severity="critical",
        metadata={"flag_name": flag_name, "enabled": enabled},
    )


__all__ = [
    "get_all_flags",
    "get_flag",
    "is_enabled",
    "reset_all_flags",
    "reset_flag",
    "set_flag",
]
