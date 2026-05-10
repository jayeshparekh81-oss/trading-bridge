"""Chain verification — walks every snapshot in sequence order and
recomputes its ``data_hash`` + ``chain_signature``, returning the
first mismatch (or "all clean") to the caller.

The algorithm is deterministic and DB-only — no external
dependencies, no clock. Any tampered column (cumulative PnL,
total trades, even ``snapshot_date``) shows up as a recomputed
``data_hash`` that differs from the stored one. Any tampered
``prior_hash`` shows up as a recomputed ``chain_signature``
mismatch.

Phase 4 will additionally cross-check ``LedgerAttestation``'s
``polygon_tx_hash`` against the on-chain calldata; for now the
verifier just checks the off-chain SHA-256 chain.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ledger_snapshot import LedgerSnapshot
from app.strategy_engine.ledger.hashing import (
    chain_signature_for,
    data_hash_for,
)
from app.strategy_engine.ledger.snapshots import (
    _DRAWDOWN_SCALE,
    _PNL_SCALE,
    _SHARPE_SCALE,
    _WIN_RATE_SCALE,
    SnapshotPayload,
    _format_decimal,
    _format_optional_decimal,
)


class LedgerVerificationResult(BaseModel):
    """Outcome of walking a listing's chain end-to-end."""

    model_config = ConfigDict(extra="forbid")

    listing_id: uuid.UUID
    is_chain_valid: bool
    snapshots_verified: int
    first_break_at_sequence: int | None
    first_break_reason: str | None
    verified_at: datetime


def _payload_from_row(row: LedgerSnapshot) -> dict[str, Any]:
    """Reconstruct the canonical payload dict that was hashed when
    the row was written. Mirrors ``SnapshotPayload`` field names."""
    return SnapshotPayload(
        listing_id=str(row.listing_id),
        snapshot_date=row.snapshot_date.isoformat(),
        sequence_number=int(row.sequence_number),
        cumulative_pnl_inr=_format_decimal(row.cumulative_pnl_inr, _PNL_SCALE),
        max_drawdown_pct=_format_decimal(row.max_drawdown_pct, _DRAWDOWN_SCALE),
        total_trades=int(row.total_trades),
        win_rate=_format_decimal(row.win_rate, _WIN_RATE_SCALE),
        sharpe_ratio=_format_optional_decimal(row.sharpe_ratio, _SHARPE_SCALE),
        days_since_publish=int(row.days_since_publish),
        paper_trades_count=int(row.paper_trades_count),
        live_trades_count=int(row.live_trades_count),
    ).model_dump()


async def verify_listing_chain(
    db: AsyncSession, listing_id: uuid.UUID
) -> LedgerVerificationResult:
    """Walk the chain for ``listing_id`` in sequence order and flag
    the first inconsistency.

    Returns ``snapshots_verified == N`` plus
    ``is_chain_valid is True`` when the entire chain (length N) is
    intact.

    Returns ``is_chain_valid is False`` plus
    ``first_break_at_sequence`` + ``first_break_reason`` when any
    snapshot fails its data-hash or chain-signature check, or when
    the sequence numbers are non-monotonic / gapped.
    """
    rows = (
        await db.execute(
            select(LedgerSnapshot)
            .where(LedgerSnapshot.listing_id == listing_id)
            .order_by(LedgerSnapshot.sequence_number.asc())
        )
    ).scalars().all()

    now = datetime.now(UTC)
    if not rows:
        return LedgerVerificationResult(
            listing_id=listing_id,
            is_chain_valid=True,
            snapshots_verified=0,
            first_break_at_sequence=None,
            first_break_reason=None,
            verified_at=now,
        )

    expected_prior_hash: str | None = None
    expected_sequence = 1
    for row in rows:
        if int(row.sequence_number) != expected_sequence:
            return LedgerVerificationResult(
                listing_id=listing_id,
                is_chain_valid=False,
                snapshots_verified=expected_sequence - 1,
                first_break_at_sequence=int(row.sequence_number),
                first_break_reason=(
                    f"sequence gap: expected {expected_sequence}, "
                    f"got {row.sequence_number}"
                ),
                verified_at=now,
            )

        recomputed_data_hash = data_hash_for(_payload_from_row(row))
        if recomputed_data_hash != row.data_hash:
            return LedgerVerificationResult(
                listing_id=listing_id,
                is_chain_valid=False,
                snapshots_verified=expected_sequence - 1,
                first_break_at_sequence=expected_sequence,
                first_break_reason=(
                    "data_hash mismatch — payload columns tampered "
                    "with after the snapshot was written"
                ),
                verified_at=now,
            )

        if row.prior_hash != expected_prior_hash:
            return LedgerVerificationResult(
                listing_id=listing_id,
                is_chain_valid=False,
                snapshots_verified=expected_sequence - 1,
                first_break_at_sequence=expected_sequence,
                first_break_reason=(
                    "prior_hash mismatch — chain link broken "
                    "(prior snapshot's chain_signature changed)"
                ),
                verified_at=now,
            )

        recomputed_signature = chain_signature_for(
            data_hash=row.data_hash, prior_hash=row.prior_hash
        )
        if recomputed_signature != row.chain_signature:
            return LedgerVerificationResult(
                listing_id=listing_id,
                is_chain_valid=False,
                snapshots_verified=expected_sequence - 1,
                first_break_at_sequence=expected_sequence,
                first_break_reason=(
                    "chain_signature mismatch — signature column "
                    "tampered with"
                ),
                verified_at=now,
            )

        expected_prior_hash = row.chain_signature
        expected_sequence += 1

    return LedgerVerificationResult(
        listing_id=listing_id,
        is_chain_valid=True,
        snapshots_verified=len(rows),
        first_break_at_sequence=None,
        first_break_reason=None,
        verified_at=now,
    )


__all__ = [
    "LedgerVerificationResult",
    "verify_listing_chain",
]
