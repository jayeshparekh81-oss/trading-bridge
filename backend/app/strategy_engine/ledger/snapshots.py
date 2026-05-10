"""Snapshot creation — builds today's ledger row for a listing.

The function pulls performance numbers from existing TRADETRI
tables (``paper_sessions`` for paper PnL + trade counts, ``trades``
for live trades, ``strategies.last_truth_score`` etc. for cached
scores) and assembles the cryptographic chain link. The DB layer's
``UNIQUE (listing_id, snapshot_date)`` enforces the daily-only
contract; calling :func:`create_daily_snapshot` twice in the same
day raises :class:`SnapshotAlreadyExistsError`.

Phase 2 keeps the math intentionally simple — this is a *proof
chain* for already-public numbers, not a re-derivation of the
strategy. Phase 3 polish swaps the simple win-rate / max-DD calc
for a session-level Sharpe / Sortino once frontend telemetry is
wired.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ledger_attestation import LedgerAttestation
from app.db.models.ledger_snapshot import LedgerSnapshot
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.paper_session import PaperSession
from app.db.models.trade import Trade
from app.strategy_engine.ledger.hashing import (
    chain_signature_for,
    data_hash_for,
)

#: Decimal quantization scales matching the storage columns.
#: Both sides of the chain (writer + verifier) use ``_format_decimal``
#: so a value that's ``Decimal('0')`` on the way in and
#: ``Decimal('0.0000')`` on the way back hashes identically.
_PNL_SCALE = Decimal("0.0001")
_DRAWDOWN_SCALE = Decimal("0.0001")
_WIN_RATE_SCALE = Decimal("0.0001")
_SHARPE_SCALE = Decimal("0.0001")


def _format_decimal(value: Decimal, scale: Decimal) -> str:
    """Quantize ``value`` to ``scale`` and stringify."""
    return str(value.quantize(scale))


def _format_optional_decimal(
    value: Decimal | None, scale: Decimal
) -> str | None:
    """Same as :func:`_format_decimal` but passes ``None`` through."""
    return None if value is None else _format_decimal(value, scale)


class SnapshotAlreadyExistsError(ValueError):
    """Raised when :func:`create_daily_snapshot` is called twice in
    one day for the same listing — the unique index on
    ``(listing_id, snapshot_date)`` would block the insert anyway,
    but raising explicitly lets the API layer return a clean 409."""


class ListingNotFoundError(ValueError):
    """Raised when ``create_daily_snapshot`` is called for a
    listing id that doesn't exist (or has been deleted)."""


class SnapshotPayload(BaseModel):
    """The payload fields fed into ``data_hash``.

    Stored on the snapshot row so a verifier can recompute the hash
    purely from the row's columns. ``listing_id`` and
    ``snapshot_date`` are included so the same payload values for
    two different listings or two different days hash to different
    digests.
    """

    model_config = ConfigDict(extra="forbid")

    listing_id: str
    snapshot_date: str  # ISO-8601 date
    sequence_number: int

    cumulative_pnl_inr: str  # Decimal text
    max_drawdown_pct: str
    total_trades: int
    win_rate: str
    sharpe_ratio: str | None  # nullable

    days_since_publish: int
    paper_trades_count: int
    live_trades_count: int


# ─── Public API ────────────────────────────────────────────────────────


async def gather_performance_payload(
    db: AsyncSession,
    listing: MarketplaceListing,
    snapshot_date: date,
    sequence_number: int,
) -> SnapshotPayload:
    """Aggregate performance numbers for ``listing`` as of
    ``snapshot_date``.

    Pulls:
        * Paper-trading: sum of ``total_trades`` + ``total_pnl``
          across every completed :class:`PaperSession` linked to the
          listing's strategy_id.
        * Live trading: count of live :class:`Trade` rows for the
          same strategy.
        * ``days_since_publish``: ``snapshot_date - listing.published_at::date``,
          clamped to ``>= 0`` (drafts get 0).
        * ``win_rate``: fraction of completed sessions with positive
          ``total_pnl``.
        * ``max_drawdown_pct``: peak-to-trough on cumulative session
          PnL ordered by date, expressed as a percent.
        * ``sharpe_ratio``: stays ``None`` in Phase 2 — needs a
          per-session return series the strategy engine doesn't
          surface yet.

    Pure aggregation — no DB writes happen here.
    """
    # Cumulative + per-session PnL stream from completed sessions.
    sessions = (
        await db.execute(
            select(PaperSession.session_date, PaperSession.total_pnl, PaperSession.total_trades)
            .where(
                PaperSession.strategy_id == listing.strategy_id,
                PaperSession.is_complete.is_(True),
            )
            .order_by(PaperSession.session_date.asc())
        )
    ).all()

    cumulative_pnl = Decimal("0")
    cumulative_pnls: list[Decimal] = []
    paper_trades = 0
    winning_sessions = 0
    for _date, pnl, trades_in_session in sessions:
        cumulative_pnl += Decimal(pnl)
        cumulative_pnls.append(cumulative_pnl)
        paper_trades += int(trades_in_session)
        if Decimal(pnl) > 0:
            winning_sessions += 1

    win_rate = (
        Decimal(winning_sessions) / Decimal(len(sessions))
        if sessions
        else Decimal("0")
    )

    # Peak-to-trough on the cumulative series → max drawdown %.
    max_dd_pct = Decimal("0")
    if cumulative_pnls:
        peak = cumulative_pnls[0]
        for v in cumulative_pnls:
            if v > peak:
                peak = v
            if peak > 0:
                dd = (peak - v) / peak * Decimal("100")
                if dd > max_dd_pct:
                    max_dd_pct = dd

    # Live trades — count live ``Trade`` rows for the strategy. The
    # strategies table links via ``strategy_id`` on ``Trade``.
    live_count = (
        await db.execute(
            select(func.count(Trade.id)).where(
                Trade.strategy_id == listing.strategy_id
            )
        )
    ).scalar_one()

    if listing.published_at is not None:
        delta = snapshot_date - listing.published_at.date()
        days_since_publish = max(0, delta.days)
    else:
        days_since_publish = 0

    return SnapshotPayload(
        listing_id=str(listing.id),
        snapshot_date=snapshot_date.isoformat(),
        sequence_number=sequence_number,
        cumulative_pnl_inr=_format_decimal(cumulative_pnl, _PNL_SCALE),
        max_drawdown_pct=_format_decimal(max_dd_pct, _DRAWDOWN_SCALE),
        total_trades=paper_trades + int(live_count),
        win_rate=_format_decimal(win_rate, _WIN_RATE_SCALE),
        sharpe_ratio=None,
        days_since_publish=days_since_publish,
        paper_trades_count=paper_trades,
        live_trades_count=int(live_count),
    )


async def create_daily_snapshot(
    db: AsyncSession,
    listing_id: Any,
    snapshot_date: date | None = None,
) -> LedgerSnapshot:
    """Build + persist today's snapshot for ``listing_id``.

    Steps:
        1. Resolve the listing (404-equivalent if missing).
        2. Reject if a snapshot already exists for the date.
        3. Look up the prior snapshot's ``chain_signature`` (or
           ``None`` for genesis).
        4. Build the payload via :func:`gather_performance_payload`.
        5. Compute ``data_hash`` + ``chain_signature``.
        6. Insert :class:`LedgerSnapshot` + a daily
           :class:`LedgerAttestation`.

    Returns the freshly-inserted ``LedgerSnapshot`` (refreshed).
    """
    target_date = snapshot_date or datetime.now(UTC).date()

    listing = (
        await db.execute(
            select(MarketplaceListing).where(
                MarketplaceListing.id == listing_id
            )
        )
    ).scalar_one_or_none()
    if listing is None:
        raise ListingNotFoundError(f"Listing {listing_id!r} not found.")

    # Reject duplicate-day snapshots up front.
    existing = (
        await db.execute(
            select(LedgerSnapshot).where(
                LedgerSnapshot.listing_id == listing.id,
                LedgerSnapshot.snapshot_date == target_date,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise SnapshotAlreadyExistsError(
            f"Snapshot already exists for listing {listing.id!s} on {target_date}."
        )

    prior = (
        await db.execute(
            select(LedgerSnapshot)
            .where(LedgerSnapshot.listing_id == listing.id)
            .order_by(LedgerSnapshot.sequence_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    next_sequence = (prior.sequence_number + 1) if prior is not None else 1
    prior_hash = prior.chain_signature if prior is not None else None

    payload = await gather_performance_payload(
        db, listing, target_date, next_sequence
    )

    data_hash = data_hash_for(payload.model_dump())
    chain_sig = chain_signature_for(data_hash=data_hash, prior_hash=prior_hash)

    snapshot = LedgerSnapshot(
        listing_id=listing.id,
        snapshot_date=target_date,
        sequence_number=next_sequence,
        cumulative_pnl_inr=Decimal(payload.cumulative_pnl_inr),
        max_drawdown_pct=Decimal(payload.max_drawdown_pct),
        total_trades=payload.total_trades,
        win_rate=Decimal(payload.win_rate),
        sharpe_ratio=None,
        days_since_publish=payload.days_since_publish,
        paper_trades_count=payload.paper_trades_count,
        live_trades_count=payload.live_trades_count,
        data_hash=data_hash,
        prior_hash=prior_hash,
        chain_signature=chain_sig,
        created_at=datetime.now(UTC),
    )
    db.add(snapshot)
    await db.flush()

    # Daily attestation row. Phase 4 will populate
    # ``polygon_tx_hash`` after on-chain submission; Phase 2 leaves
    # it NULL.
    attestation = LedgerAttestation(
        snapshot_id=snapshot.id,
        attestation_type="daily_snapshot",
        attestation_hash=data_hash_for({"chain_signature": chain_sig}),
        polygon_tx_hash=None,
        attested_at=datetime.now(UTC),
    )
    db.add(attestation)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


__all__ = [
    "ListingNotFoundError",
    "SnapshotAlreadyExistsError",
    "SnapshotPayload",
    "create_daily_snapshot",
    "gather_performance_payload",
]


_ = Field  # silence the unused-import linter when pydantic Field
# isn't used (kept around for the SnapshotPayload's potential
# future extra-validation needs).
