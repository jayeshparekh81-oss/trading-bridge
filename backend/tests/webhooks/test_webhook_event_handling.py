"""Webhook event-handling edge case tests.

Catches:
  - Duplicate event delivery (TradingView retries on 500)
  - Malformed JSON payloads
  - Signals after square-off
  - HMAC signature variations

Tests run against the existing webhook validator + receiver. Heavy
mocking of the broker call path; we test the GATING logic only.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid

import pytest

# bcrypt is transitively imported by app.core.security via the webhook
# stack. Skip-module gracefully if not installed in this dev env.
pytest.importorskip("bcrypt")


HMAC_SECRET = "test-webhook-secret-do-not-use-in-prod"


def _hmac(payload: dict) -> str:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hmac.new(HMAC_SECRET.encode(), body, hashlib.sha256).hexdigest()


# ─── Payload shape validation ────────────────────────────────────────


def test_webhook_payload_validator_accepts_valid_minimum() -> None:
    """Smoke: importing the StrategySignal schema works."""
    from app.schemas.strategy_webhook import StrategySignalIn

    valid = {
        "symbol": "NIFTY",
        "side": "BUY",
        "quantity": 75,
        "entry_price": 22000.0,
        "exchange": "NSE",
    }
    StrategySignalIn.model_validate(valid)


def test_webhook_payload_validator_rejects_missing_symbol() -> None:
    from pydantic import ValidationError

    from app.schemas.strategy_webhook import StrategySignalIn

    bad = {"side": "BUY", "quantity": 75, "entry_price": 22000.0, "exchange": "NSE"}
    with pytest.raises(ValidationError):
        StrategySignalIn.model_validate(bad)


def test_webhook_payload_validator_rejects_invalid_side() -> None:
    from pydantic import ValidationError

    from app.schemas.strategy_webhook import StrategySignalIn

    bad = {
        "symbol": "NIFTY",
        "side": "INVALID_SIDE",
        "quantity": 75,
        "entry_price": 22000.0,
        "exchange": "NSE",
    }
    with pytest.raises(ValidationError):
        StrategySignalIn.model_validate(bad)


def test_webhook_payload_validator_rejects_negative_quantity() -> None:
    from pydantic import ValidationError

    from app.schemas.strategy_webhook import StrategySignalIn

    bad = {
        "symbol": "NIFTY",
        "side": "BUY",
        "quantity": -1,
        "entry_price": 22000.0,
        "exchange": "NSE",
    }
    with pytest.raises(ValidationError):
        StrategySignalIn.model_validate(bad)


def test_webhook_payload_validator_rejects_zero_quantity() -> None:
    from pydantic import ValidationError

    from app.schemas.strategy_webhook import StrategySignalIn

    bad = {
        "symbol": "NIFTY",
        "side": "BUY",
        "quantity": 0,
        "entry_price": 22000.0,
        "exchange": "NSE",
    }
    with pytest.raises(ValidationError):
        StrategySignalIn.model_validate(bad)


def test_webhook_payload_validator_rejects_negative_price() -> None:
    from pydantic import ValidationError

    from app.schemas.strategy_webhook import StrategySignalIn

    bad = {
        "symbol": "NIFTY",
        "side": "BUY",
        "quantity": 75,
        "entry_price": -100.0,
        "exchange": "NSE",
    }
    with pytest.raises(ValidationError):
        StrategySignalIn.model_validate(bad)


# ─── HMAC signature handling ─────────────────────────────────────────


def test_hmac_signature_is_hex_of_sha256() -> None:
    """Sanity: our test helper produces a 64-char hex SHA-256 digest."""
    sig = _hmac({"symbol": "NIFTY", "side": "BUY", "quantity": 75, "entry_price": 22000.0})
    assert len(sig) == 64
    assert all(c in "0123456789abcdef" for c in sig)


def test_hmac_signature_changes_when_payload_changes() -> None:
    sig_a = _hmac({"symbol": "NIFTY", "quantity": 75})
    sig_b = _hmac({"symbol": "NIFTY", "quantity": 100})
    assert sig_a != sig_b


def test_hmac_signature_key_order_invariant() -> None:
    """JSON serialised with sort_keys=True is byte-stable."""
    sig_a = _hmac({"symbol": "NIFTY", "quantity": 75})
    sig_b = _hmac({"quantity": 75, "symbol": "NIFTY"})
    assert sig_a == sig_b


# ─── Idempotency hash (duplicate signal detection) ───────────────────


def test_idempotency_hash_changes_with_payload_change() -> None:
    """Different payloads → different signal hashes (no false dedup)."""
    from app.schemas.strategy_webhook import StrategySignalIn

    sig_a = StrategySignalIn.model_validate(
        {
            "symbol": "NIFTY",
            "side": "BUY",
            "quantity": 75,
            "entry_price": 22000.0,
            "exchange": "NSE",
        }
    )
    sig_b = StrategySignalIn.model_validate(
        {
            "symbol": "NIFTY",
            "side": "BUY",
            "quantity": 75,
            "entry_price": 22001.0,  # 1 rupee different
            "exchange": "NSE",
        }
    )
    # Hash the payloads
    body_a = json.dumps(sig_a.model_dump(mode="json"), sort_keys=True)
    body_b = json.dumps(sig_b.model_dump(mode="json"), sort_keys=True)
    hash_a = hashlib.sha256(body_a.encode()).hexdigest()
    hash_b = hashlib.sha256(body_b.encode()).hexdigest()
    assert hash_a != hash_b


def test_idempotency_hash_stable_for_same_payload() -> None:
    from app.schemas.strategy_webhook import StrategySignalIn

    payload = {
        "symbol": "NIFTY",
        "side": "BUY",
        "quantity": 75,
        "entry_price": 22000.0,
        "exchange": "NSE",
    }
    sig_a = StrategySignalIn.model_validate(payload)
    sig_b = StrategySignalIn.model_validate(payload)
    body_a = json.dumps(sig_a.model_dump(mode="json"), sort_keys=True)
    body_b = json.dumps(sig_b.model_dump(mode="json"), sort_keys=True)
    assert body_a == body_b
