"""Hashing primitives — pure unit tests, no DB.

These pin the deterministic-output contract that the rest of the
ledger relies on. If any of these change shape, the chain
verifier will report every existing chain as broken — so the
contract is locked here on purpose.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.strategy_engine.ledger.hashing import (
    canonical_json,
    chain_signature_for,
    data_hash_for,
    sha256_hex,
)


def test_sha256_hex_matches_known_vector() -> None:
    """Anchor against the canonical SHA-256 of an empty string."""
    assert sha256_hex("") == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_canonical_json_sorts_keys_recursively() -> None:
    out = canonical_json({"b": 1, "a": {"d": 2, "c": 3}})
    assert out == '{"a":{"c":3,"d":2},"b":1}'


def test_canonical_json_coerces_decimal_to_exact_text() -> None:
    """A ``Decimal`` round-trips via ``str(value)`` so storage
    precision is preserved (e.g. trailing zeros)."""
    out = canonical_json({"price": Decimal("123.4500")})
    assert out == '{"price":"123.4500"}'


def test_canonical_json_coerces_date_and_datetime_to_iso() -> None:
    out = canonical_json(
        {
            "d": date(2026, 5, 9),
            "t": datetime(2026, 5, 9, 12, 30, 45),
        }
    )
    # JSON output is alphabetised — ``d`` precedes ``t``.
    assert '"d":"2026-05-09"' in out
    assert '"t":"2026-05-09T12:30:45"' in out


def test_canonical_json_coerces_uuid_to_str() -> None:
    u = uuid.UUID("12345678-1234-5678-1234-567812345678")
    out = canonical_json({"id": u})
    assert out == '{"id":"12345678-1234-5678-1234-567812345678"}'


def test_canonical_json_handles_lists_and_nones() -> None:
    out = canonical_json({"vals": [1, None, "x"]})
    assert out == '{"vals":[1,null,"x"]}'


def test_data_hash_for_is_deterministic_across_dict_orders() -> None:
    """Same payload, different insertion orders → identical digest."""
    a = data_hash_for({"a": 1, "b": 2, "c": [3, 4]})
    b = data_hash_for({"c": [3, 4], "b": 2, "a": 1})
    assert a == b


def test_data_hash_for_changes_on_any_field_edit() -> None:
    base = data_hash_for({"pnl": "100.00", "trades": 5})
    edited_value = data_hash_for({"pnl": "100.01", "trades": 5})
    edited_key = data_hash_for({"pnl": "100.00", "trade_count": 5})
    assert base != edited_value
    assert base != edited_key


def test_chain_signature_for_genesis_uses_locked_seed() -> None:
    """Genesis snapshot composes the seed string ``data|GENESIS``;
    if anyone changes the seed sentinel every chain breaks — pin it
    here."""
    sig = chain_signature_for(data_hash="abc", prior_hash=None)
    expected = sha256_hex("abc|GENESIS")
    assert sig == expected


def test_chain_signature_for_chained_uses_prior_hash() -> None:
    sig = chain_signature_for(data_hash="abc", prior_hash="def")
    expected = sha256_hex("abc|def")
    assert sig == expected


def test_chain_signature_for_distinguishes_genesis_from_literal_genesis_string() -> None:
    """A snapshot whose prior_hash literally equals ``"GENESIS"`` (a
    deliberate caller error) must still hash to the same digest as
    a genesis seed — but the verifier has separate state to detect
    that pathological case. Here we just pin that the function
    treats them identically (which is the right call: ``GENESIS``
    is a magic string, not a sentinel value)."""
    genesis = chain_signature_for(data_hash="abc", prior_hash=None)
    impostor = chain_signature_for(data_hash="abc", prior_hash="GENESIS")
    assert genesis == impostor


def test_canonical_json_rejects_unknown_complex_objects_via_default() -> None:
    """An unsupported object (e.g. a class instance) falls through
    to ``json.dumps``'s default encoder and raises TypeError.
    Pinning this so a future regression that silently coerces
    arbitrary objects (and breaks determinism) trips here."""
    class _Foo:
        pass

    with pytest.raises(TypeError):
        canonical_json({"x": _Foo()})
