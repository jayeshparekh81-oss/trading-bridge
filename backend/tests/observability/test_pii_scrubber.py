"""PII scrubber unit tests — pure functions, no DB / no SDK."""

from __future__ import annotations

import os
from unittest.mock import patch

from app.observability.pii_scrubber import (
    hash_resource_id,
    hash_user_id,
    scrub_properties_dict,
)

# ─── Hashing ──────────────────────────────────────────────────────────


def test_hash_user_id_is_deterministic() -> None:
    """Same input → same output (so PostHog deduplicates events
    from the same user across sessions)."""
    a = hash_user_id("user-abc")
    b = hash_user_id("user-abc")
    assert a == b
    # Hex digest of SHA-256 is 64 chars.
    assert len(a) == 64


def test_hash_user_id_differs_between_users() -> None:
    a = hash_user_id("user-1")
    b = hash_user_id("user-2")
    assert a != b


def test_hash_resource_id_salted_by_resource_kind() -> None:
    """A user id and a listing id that share the same UUID string
    should produce different hashes — the salt scopes them."""
    common = "00000000-0000-0000-0000-000000000001"
    user = hash_user_id(common)
    listing = hash_resource_id("listing", common)
    assert user != listing
    # And listing vs strategy of the same id also differ.
    strategy = hash_resource_id("strategy", common)
    assert listing != strategy


def test_hash_user_id_changes_when_salt_env_var_set() -> None:
    """Rotating ``ANALYTICS_SALT`` invalidates every prior hash —
    that's by design (a way to nuke the analytics user id graph)."""
    base = hash_user_id("user-X")
    with patch.dict(os.environ, {"ANALYTICS_SALT": "fresh-salt"}):
        rotated = hash_user_id("user-X")
    assert base != rotated


# ─── Property scrubbing ───────────────────────────────────────────────


def test_scrub_strips_email_field() -> None:
    out = scrub_properties_dict({"email": "x@y.com", "mode": "expert"})
    assert "email" not in out
    assert out["mode"] == "expert"


def test_scrub_strips_phone_variants() -> None:
    out = scrub_properties_dict(
        {
            "phone": "9876543210",
            "phone_number": "9876543210",
            "telephone": "9876543210",
            "mobile": "9876543210",
            "ok": True,
        }
    )
    for key in ("phone", "phone_number", "telephone", "mobile"):
        assert key not in out
    assert out["ok"] is True


def test_scrub_strips_token_and_secret_keys() -> None:
    out = scrub_properties_dict(
        {
            "access_token": "x",
            "refresh_token": "y",
            "api_key": "z",
            "broker_token": "b",
            "broker_secret": "s",
            "user_count": 42,
        }
    )
    assert "access_token" not in out
    assert "refresh_token" not in out
    assert "api_key" not in out
    assert "broker_token" not in out
    assert "broker_secret" not in out
    assert out["user_count"] == 42


def test_scrub_strips_amount_keys() -> None:
    """Free-form business amounts (P&L magnitudes, individual
    trade sizes) get dropped. Aggregate-percentage variants pass."""
    out = scrub_properties_dict(
        {
            "pnl_inr": 12345,
            "amount_paid_inr": 999,
            "win_rate": 0.65,  # aggregate — passes
            "trade_count": 5,
        }
    )
    assert "pnl_inr" not in out
    assert "amount_paid_inr" not in out
    assert out["win_rate"] == 0.65
    assert out["trade_count"] == 5


def test_scrub_is_case_insensitive_on_keys() -> None:
    out = scrub_properties_dict(
        {"Email": "x@y", "EMAIL": "z@w", "ok": True}
    )
    assert out == {"ok": True}


def test_scrub_returns_defensive_copy() -> None:
    """Mutating the output must not affect the input dict."""
    original = {"mode": "beginner", "email": "x@y"}
    out = scrub_properties_dict(original)
    out["mode"] = "expert"
    assert original["mode"] == "beginner"
    # Original unchanged — email still there until the caller drops it.
    assert "email" in original


def test_scrub_empty_dict_returns_empty_dict() -> None:
    assert scrub_properties_dict({}) == {}
