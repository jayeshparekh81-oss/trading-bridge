"""Production env-var validation tests.

Pure-stdlib — uses a callable ``env_getter`` parameter so the tests
substitute a dict instead of mutating ``os.environ``.
"""

from __future__ import annotations

import logging

import pytest

from app.observability.env_check import (
    OPTIONAL_PRODUCTION_ENV,
    REQUIRED_PRODUCTION_ENV,
    EnvValidationError,
    validate_production_env,
)


def _full_env() -> dict[str, str]:
    """Build a dict that satisfies every required + optional var."""
    env: dict[str, str] = {"ENVIRONMENT": "production"}
    for var in REQUIRED_PRODUCTION_ENV:
        env[var.name] = f"value-for-{var.name}"
    for var in OPTIONAL_PRODUCTION_ENV:
        env[var.name] = f"value-for-{var.name}"
    return env


def test_passes_with_all_required_set() -> None:
    env = _full_env()
    # No exception → success.
    validate_production_env(env_getter=env.get)


def test_fails_when_required_var_missing() -> None:
    env = _full_env()
    del env["DATABASE_URL"]
    with pytest.raises(EnvValidationError) as excinfo:
        validate_production_env(env_getter=env.get)
    assert "DATABASE_URL" in str(excinfo.value)


def test_fails_aggregates_every_missing_var() -> None:
    """If multiple required vars are missing the error message
    lists all of them, not just the first."""
    env = _full_env()
    del env["DATABASE_URL"]
    del env["REDIS_URL"]
    with pytest.raises(EnvValidationError) as excinfo:
        validate_production_env(env_getter=env.get)
    msg = str(excinfo.value)
    assert "DATABASE_URL" in msg
    assert "REDIS_URL" in msg


def test_warns_for_missing_optional_vars(
    caplog: pytest.LogCaptureFixture,
) -> None:
    env = _full_env()
    del env["SENTRY_DSN"]
    del env["DHAN_ACCESS_TOKEN"]
    with caplog.at_level(logging.WARNING):
        validate_production_env(env_getter=env.get)

    warned_names = [
        record.__dict__.get("var_name")
        for record in caplog.records
        if record.message == "env.missing_optional"
    ]
    assert "SENTRY_DSN" in warned_names
    assert "DHAN_ACCESS_TOKEN" in warned_names


def test_no_op_for_non_production_environment() -> None:
    """Required vars missing? No problem when ENVIRONMENT != production."""
    env = {"ENVIRONMENT": "development"}  # everything else absent
    # No exception, no error log — pure no-op.
    validate_production_env(env_getter=env.get)


def test_no_op_when_environment_unset() -> None:
    """The ``ENVIRONMENT`` var itself absent → treated as non-prod."""
    env: dict[str, str] = {}
    validate_production_env(env_getter=env.get)


def test_environment_is_case_insensitive() -> None:
    """``ENVIRONMENT=PRODUCTION`` (mis-cased) still triggers
    validation — defensive against deploy-config typos."""
    env = _full_env()
    env["ENVIRONMENT"] = "PRODUCTION"
    del env["DATABASE_URL"]
    with pytest.raises(EnvValidationError):
        validate_production_env(env_getter=env.get)
