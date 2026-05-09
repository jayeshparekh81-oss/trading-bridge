"""``ledger_attestations`` table — periodic chain attestations.

Each row pins a ``LedgerSnapshot``'s chain_signature to a higher-
order audit checkpoint:

    daily_snapshot     — every snapshot is also a daily attestation.
    weekly_summary     — emitted every 7th day after publish.
    milestone_30day    — at days_since_publish == 30.
    milestone_60day    — at days_since_publish == 60.
    milestone_90day    — at days_since_publish == 90 (the master-prompt
                         "90-day proof" gate).

Phase 4 will populate ``polygon_tx_hash`` with the txid that put
the ``attestation_hash`` on Polygon mainnet. Phase 2 leaves it
NULL — the off-chain SHA-256 chain is the only proof for now.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class LedgerAttestation(UUIDPrimaryKeyMixin, Base):
    """One attestation row — a higher-order checkpoint over a
    snapshot's chain_signature."""

    __tablename__ = "ledger_attestations"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ledger_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )

    #: One of ``daily_snapshot`` / ``weekly_summary`` /
    #: ``milestone_30day`` / ``milestone_60day`` / ``milestone_90day``.
    #: CHECK constraint at the migration layer pins the values.
    attestation_type: Mapped[str] = mapped_column(String(32), nullable=False)

    #: SHA-256 hex digest of the snapshot's ``chain_signature``.
    #: Phase 4 will commit this string into a Polygon transaction
    #: as ``calldata``.
    attestation_hash: Mapped[str] = mapped_column(Text, nullable=False)

    #: The Polygon transaction hash that landed ``attestation_hash``
    #: on-chain. NULL until Phase 4 wires real Polygon integration.
    polygon_tx_hash: Mapped[str | None] = mapped_column(Text, nullable=True)

    attested_at: Mapped[datetime] = mapped_column(nullable=False)

    def __repr__(self) -> str:
        return (
            f"LedgerAttestation(id={self.id!r}, "
            f"snapshot_id={self.snapshot_id!r}, "
            f"type={self.attestation_type!r})"
        )


__all__ = ["LedgerAttestation"]
