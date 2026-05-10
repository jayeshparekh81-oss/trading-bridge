"""Deterministic SHA-256 helpers for the Transparency Ledger chain.

Two design goals make this leaf-pure and easy to verify:

    1. **Canonical JSON** — fields are serialised with sorted keys,
       no whitespace, and explicit type coercion so the same row
       hashes identically on every platform / Python version.
       :class:`Decimal` round-trips via :func:`str` (exact text);
       :class:`datetime` and :class:`date` round-trip via ISO-8601;
       :class:`uuid.UUID` round-trips via :func:`str`.

    2. **Chain signature** — ``data_hash`` is SHA-256 of the
       canonical JSON. The ``chain_signature`` is SHA-256 of
       ``data_hash + "|" + (prior_hash or "GENESIS")`` — so the
       genesis snapshot has a deterministic seed string and every
       subsequent snapshot signs over both its own data and the
       prior link.

The functions here are pure: no DB, no clock, no randomness. Easy
to test, easy to reason about, easy to swap with a Polygon
on-chain emission in Phase 4.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any

#: Sentinel string that seeds the genesis snapshot's chain signature.
#: Locked in this module so any out-of-band change (typo, casing,
#: whitespace) trips every existing chain on its first verify.
_GENESIS_SEED = "GENESIS"


def canonical_json(payload: Mapping[str, Any]) -> str:
    """Serialise ``payload`` to deterministic JSON.

    Rules:
        * Keys sorted alphabetically (recursive).
        * No whitespace separators.
        * ``Decimal`` -> ``str(value)`` (exact text representation;
          preserves the row's storage precision).
        * ``date`` / ``datetime`` -> ISO-8601 string.
        * ``UUID`` -> ``str(uuid)``.
        * ``None`` -> JSON null.
        * Lists / dicts recursed; everything else passed through to
          :func:`json.dumps`'s default encoder (ints, floats, bools,
          strings).

    The output is the *exact* string fed to SHA-256 — verifiers can
    reconstruct it from a snapshot row's columns and recompute the
    expected ``data_hash``.
    """
    return json.dumps(
        _canonicalise(dict(payload)),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _canonicalise(value: Any) -> Any:
    """Recurse into lists / dicts, coercing types into JSON-friendly
    primitives. Bypassed for primitives that ``json`` already knows
    how to serialise (int, float, bool, str, None)."""
    if isinstance(value, Mapping):
        return {k: _canonicalise(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonicalise(v) for v in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def sha256_hex(payload: str) -> str:
    """Hex-encoded SHA-256 of ``payload`` interpreted as UTF-8."""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def data_hash_for(payload: Mapping[str, Any]) -> str:
    """``sha256_hex(canonical_json(payload))`` — the value stored in
    a snapshot's ``data_hash`` column."""
    return sha256_hex(canonical_json(payload))


def chain_signature_for(
    *, data_hash: str, prior_hash: str | None
) -> str:
    """Compose the chain signature from a fresh ``data_hash`` and
    the prior snapshot's chain signature.

    Genesis snapshots pass ``prior_hash=None``; the function
    substitutes the locked ``_GENESIS_SEED`` so the seed string
    remains deterministic.
    """
    seed = prior_hash if prior_hash is not None else _GENESIS_SEED
    return sha256_hex(f"{data_hash}|{seed}")


__all__ = [
    "canonical_json",
    "chain_signature_for",
    "data_hash_for",
    "sha256_hex",
]
