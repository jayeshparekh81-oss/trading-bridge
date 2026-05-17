"""Idempotency hash for backtest runs.

Computes a SHA-256 hex digest over the canonical JSON serialisation
of a request payload + the engine version. Identical inputs yield
identical hashes regardless of dict-key order, whitespace, or
``int`` vs ``float`` representation of integer-valued floats.

Cache lookup at ``persistence.get_cached_run_by_hash`` is
``(user_id, request_hash) WHERE status='SUCCEEDED'`` (decision D3).
The partial-unique index in migration 028 guards against
double-success-insert races.

**Canonicalisation rules:**
    * Recursively sort dict keys
    * Round-trip floats through ``json.loads(json.dumps(...))`` so
      ``1.0`` and ``1`` hash identically when both are floats in
      memory (they aren't, but the engine accepts either at the
      Pydantic boundary)
    * Strip whitespace via ``separators=(",", ":")``

Engine version: returns ``"v1"`` per decision D2. Replace with
``app/strategy_engine/backtest/_version.py:__engine_version__``
when that ships (Day 7 of original 7-day plan).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


#: Engine version embedded in every request hash. Bumping this
#: produces a different hash for identical request payloads, which
#: is the desired cache-bust on engine behavioural change.
ENGINE_VERSION: str = "v1"


def engine_version() -> str:
    """Return the current backtest engine version string."""
    return ENGINE_VERSION


def _canonicalize(value: Any) -> Any:
    """Recursively normalise a JSON-serialisable structure for hashing.

    Rules:
        - dicts → sorted by key, recursively canonicalised
        - lists/tuples → list (preserve order), each item canonicalised
        - other → leave as-is (json.dumps handles primitives)
    """
    if isinstance(value, dict):
        return {k: _canonicalize(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    return value


def compute_hash(
    *,
    strategy_config: dict[str, Any] | None,
    symbols: list[str] | str,
    date_range: tuple[str, str] | dict[str, Any] | None,
    engine_version: str = ENGINE_VERSION,
    extra: dict[str, Any] | None = None,
) -> str:
    """Return the SHA-256 hex digest of the canonical request payload.

    Args:
        strategy_config: Either the strategy's full ``strategy_json``
            payload OR ``None`` when the request resolves the strategy
            by id. The DB scope (user_id) is NOT in the hash —
            user-scoping happens at cache-lookup SQL (decision D4).
        symbols: One symbol string ("NIFTY") or list of symbols.
            Lists are sorted before hashing so symbol order doesn't
            affect the digest.
        date_range: Either a ``(start_iso, end_iso)`` tuple or a
            dict ``{"start": ..., "end": ...}``. Both forms normalise
            to a sorted-dict shape.
        engine_version: Defaults to module's ``ENGINE_VERSION``.
        extra: Additional fields the caller wants in the hash
            (initial_capital, quantity, cost_settings, ambiguity_mode).
            Each must be JSON-serialisable.

    Returns:
        64-character lowercase hex string.
    """
    # Normalise symbols → sorted list of unique strings
    if isinstance(symbols, str):
        symbols_norm: list[str] = [symbols]
    else:
        symbols_norm = sorted({str(s) for s in symbols})

    # Normalise date_range → dict with sorted keys
    if date_range is None:
        date_range_norm: dict[str, str] | None = None
    elif isinstance(date_range, dict):
        date_range_norm = {
            "start": str(date_range["start"]) if "start" in date_range else "",
            "end": str(date_range["end"]) if "end" in date_range else "",
        }
    else:
        start, end = date_range
        date_range_norm = {"start": str(start), "end": str(end)}

    payload: dict[str, Any] = {
        "strategy_config": strategy_config,
        "symbols": symbols_norm,
        "date_range": date_range_norm,
        "engine_version": engine_version,
    }
    if extra:
        payload["extra"] = extra

    canonical = _canonicalize(payload)
    # Use sort_keys=True and tight separators for byte-stable output.
    serialised = json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


def compute_hash_from_request(
    *,
    strategy_id: Any | None,
    strategy_config: dict[str, Any] | None,
    symbol: str,
    timeframe: str,
    start: Any,
    end: Any,
    initial_capital: float,
    quantity: float,
    cost_settings: dict[str, Any] | Any,
    ambiguity_mode: Any,
    engine_version_str: str = ENGINE_VERSION,
) -> str:
    """High-level helper that adapts a BacktestEnqueueRequest's fields
    to ``compute_hash``. Handles datetime → ISO conversion + Pydantic
    model_dump.

    Note: ``strategy_id`` is captured (its hash contribution
    distinguishes "this strategy's snapshot" from another strategy's
    identical config), but the user_id is NOT — cache scope is the
    SQL filter, not the hash.
    """
    sc_norm: dict[str, Any] | None = None
    if strategy_config is not None:
        sc_norm = strategy_config
    elif strategy_id is not None:
        # Reference-by-id: the strategy_id IS the strategy's identity
        # for hashing purposes (different ids → different hashes even
        # when configs happen to match).
        sc_norm = {"_strategy_id": str(strategy_id)}

    # cost_settings may be a Pydantic model — coerce to dict.
    if hasattr(cost_settings, "model_dump"):
        cost_norm: dict[str, Any] = cost_settings.model_dump(mode="json")
    elif isinstance(cost_settings, dict):
        cost_norm = cost_settings
    else:
        cost_norm = {}

    ambiguity_norm = (
        ambiguity_mode.value
        if hasattr(ambiguity_mode, "value")
        else str(ambiguity_mode)
    )

    return compute_hash(
        strategy_config=sc_norm,
        symbols=symbol,
        date_range={"start": str(start), "end": str(end)},
        engine_version=engine_version_str,
        extra={
            "timeframe": timeframe,
            "initial_capital": float(initial_capital),
            "quantity": float(quantity),
            "cost_settings": cost_norm,
            "ambiguity_mode": ambiguity_norm,
        },
    )


__all__ = [
    "ENGINE_VERSION",
    "compute_hash",
    "compute_hash_from_request",
    "engine_version",
]
