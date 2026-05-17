"""Idempotency hash for backtest runs.

Computes a SHA-256 hex digest over the canonical JSON serialisation of
``(BacktestEnqueueRequest payload + engine_version)``. The hash is
**deterministic** — identical inputs yield identical hashes regardless
of dict-key order, whitespace, or trivial float-int coercion.

The cache lookup at ``persistence.fetch_cached_run`` is
``(user_id, hash) WHERE status='SUCCEEDED'``. The partial unique index
in migration 028 guards against double-success-insert races.

**Skeleton stage:** function bodies raise NotImplementedError. Day 2
of the Week 2 sprint fills these in; see
``docs/BACKTEST_ENGINE_EXTENSION_PLAN.md``.
"""

from __future__ import annotations

from app.backtest_extension.schemas import BacktestEnqueueRequest


def engine_version() -> str:
    """Return the current backtest engine version string.

    Read from ``app.strategy_engine.backtest._version.__engine_version__``
    once the version module ships (Day 7 of Week 2). Until then, return
    the placeholder ``"1.0"`` so the hash function is still importable.
    """
    # Day 7 work — replace with:
    #     from app.strategy_engine.backtest._version import __engine_version__
    #     return __engine_version__
    return "1.0"


def compute_request_hash(request: BacktestEnqueueRequest) -> str:
    """Return the SHA-256 hex digest over the canonical request payload.

    Canonicalisation rules:
        * ``request.model_dump(mode="json")`` to coerce datetimes to ISO strings,
          UUIDs to str, enums to their value.
        * ``json.dumps(payload, sort_keys=True, separators=(",", ":"))`` — strict
          canonical form, no whitespace, sorted keys at every depth.
        * Append ``engine_version()`` and re-hash the combined string.

    The hash is **only valid within the current engine version**. A
    version bump produces a different hash for identical request payloads,
    which is the desired cache-bust on engine behaviour change.

    Raises:
        NotImplementedError: skeleton — implement on Day 2 of Week 2.
    """
    raise NotImplementedError(
        "compute_request_hash is a Week-2 Day-2 deliverable; see "
        "docs/BACKTEST_ENGINE_EXTENSION_PLAN.md"
    )


__all__ = ["compute_request_hash", "engine_version"]
