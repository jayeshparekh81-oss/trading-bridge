"""Strategy Transparency Ledger — Marketplace Phase 2 (off-chain).

Public surface re-exported for the API layer. Phase 4 will add a
real Polygon-mainnet integration alongside the off-chain chain;
the API contract here doesn't change in Phase 4 — only the
``polygon_stub`` module gets swapped for a real implementation.
"""

from __future__ import annotations

from app.strategy_engine.ledger.hashing import (
    canonical_json,
    chain_signature_for,
    data_hash_for,
    sha256_hex,
)
from app.strategy_engine.ledger.snapshots import (
    SnapshotPayload,
    create_daily_snapshot,
    gather_performance_payload,
)
from app.strategy_engine.ledger.verification import (
    LedgerVerificationResult,
    verify_listing_chain,
)

__all__ = [
    "LedgerVerificationResult",
    "SnapshotPayload",
    "canonical_json",
    "chain_signature_for",
    "create_daily_snapshot",
    "data_hash_for",
    "gather_performance_payload",
    "sha256_hex",
    "verify_listing_chain",
]
