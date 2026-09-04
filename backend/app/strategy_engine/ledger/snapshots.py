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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ledger_attestation import LedgerAttestation
from app.db.models.ledger_snapshot import LedgerSnapshot
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.paper_session import PaperSession
from app.db.models.strategy import Strategy
from app.db.models.strategy_position import StrategyPosition
from app.domains.pnl_reconciler.service import reconcile_strategy
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


def _format_optional_decimal(value: Decimal | None, scale: Decimal) -> str | None:
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


class NothingToPublishError(ValueError):
    """Raised when the payload would publish NOTHING real.

    Founder's rule: publish nothing rather than a zero. An append-only,
    hash-chained ledger cannot be corrected, so a "0 trades / ₹0" row is
    a permanent lie. Live strategies with no priced round trip, and paper
    strategies with no completed session, refuse to snapshot (the API
    layer returns 422 with the reason; nothing is inserted).
    """


#: ``pnl_basis`` literal stored on every live-strategy snapshot: the P&L
#: is NET of *estimated* Indian F&O charges (brokerage/STT/exchange/SEBI/
#: stamp/GST at published rates) — fills are real, charges are modelled,
#: not the broker's contract note. The ledger must say so on the chain.
PNL_BASIS_RECONCILED_NET = "reconciled_net_estimated_costs"
#: ``pnl_basis`` for paper strategies (session aggregates, no costs).
PNL_BASIS_PAPER_SESSIONS = "paper_sessions_gross"


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
    #: % of the cumulative-P&L peak — paper listings only; None for live.
    max_drawdown_pct: str | None
    total_trades: int
    win_rate: str
    sharpe_ratio: str | None  # nullable

    days_since_publish: int
    paper_trades_count: int
    live_trades_count: int

    #: Closed positions the platform could NOT price (exits taken on the
    #: broker's own app, phantom/cleanup rows, unfilled entries). Published
    #: on the chain so the coverage gap is visible, never hidden.
    unpriced_positions: int | None = None
    #: How ``cumulative_pnl_inr`` was derived — see ``PNL_BASIS_*``.
    pnl_basis: str | None = None
    #: Peak-to-trough drawdown of the cumulative NET series, in rupees.
    max_drawdown_inr: str | None = None


# ─── Public API ────────────────────────────────────────────────────────


async def gather_performance_payload(
    db: AsyncSession,
    listing: MarketplaceListing,
    snapshot_date: date,
    sequence_number: int,
) -> SnapshotPayload:
    """Aggregate performance numbers for ``listing`` as of ``snapshot_date``.

    Two sources, chosen by the strategy's ``is_paper``:

    * **Live strategy** (``is_paper = false``): a READ-ONLY pass of the P&L
      reconciler over the strategy's CLOSED positions, priced from the REAL
      broker fills in ``strategy_executions``. Only COMPLETE round trips
      count. ``cumulative_pnl_inr`` is NET of estimated costs
      (``pnl_basis = reconciled_net_estimated_costs``); ``unpriced_positions``
      carries the closed positions that could not be priced. Paper sessions
      from before go-live are NOT the live record and are never summed in.
    * **Paper strategy** (``is_paper = true``): the completed
      ``paper_sessions`` aggregation, unchanged.

    Both refuse with :class:`NothingToPublishError` when there is nothing
    real to publish — never a zero row. Pure aggregation, no DB writes.
    (The legacy ``trades`` table is no longer read: the strategy engine
    never writes it, so it counted 0 for every live strategy.)
    """
    is_paper = (
        await db.execute(select(Strategy.is_paper).where(Strategy.id == listing.strategy_id))
    ).scalar_one_or_none()
    if is_paper is None:
        raise ListingNotFoundError(
            f"Strategy {listing.strategy_id!s} behind listing {listing.id!s} not found."
        )

    if listing.published_at is not None:
        delta = snapshot_date - listing.published_at.date()
        days_since_publish = max(0, delta.days)
    else:
        days_since_publish = 0

    if not is_paper:
        return await _live_payload(db, listing, snapshot_date, sequence_number, days_since_publish)
    return await _paper_payload(db, listing, snapshot_date, sequence_number, days_since_publish)


def _max_drawdown_pct(cumulative: list[Decimal]) -> Decimal:
    """Peak-to-trough on a cumulative P&L series, as a percent of the peak.

    Only defined while the peak is positive (a series that never goes
    above zero has no drawdown from a gain); returns 0 otherwise.
    """
    max_dd_pct = Decimal("0")
    if not cumulative:
        return max_dd_pct
    peak = cumulative[0]
    for v in cumulative:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak * Decimal("100")
            if dd > max_dd_pct:
                max_dd_pct = dd
    return max_dd_pct


def _max_drawdown_inr(cumulative: list[Decimal]) -> Decimal:
    """Largest peak-to-trough fall of a cumulative P&L series, in currency.

    Defined for every series (a series that only falls has a drawdown equal to
    its fall from the starting point 0); always >= 0.
    """
    worst = Decimal("0")
    peak = Decimal("0")
    for v in cumulative:
        if v > peak:
            peak = v
        fall = peak - v
        if fall > worst:
            worst = fall
    return worst


async def _live_payload(
    db: AsyncSession,
    listing: MarketplaceListing,
    snapshot_date: date,
    sequence_number: int,
    days_since_publish: int,
) -> SnapshotPayload:
    result = await reconcile_strategy(db, listing.strategy_id, write=False)
    priced = [t for t in result.trips if t.complete and t.net_pnl is not None]
    unpriced = [t for t in result.trips if not t.complete]

    if not priced:
        raise NothingToPublishError(
            f"Listing {listing.id!s}: no closed position can be priced from real "
            f"fills ({len(unpriced)} closed, 0 complete). Nothing published."
        )

    # Order by the position's close time so the drawdown series is temporal.
    closed_at_by_id = dict(
        (
            await db.execute(
                select(StrategyPosition.id, StrategyPosition.closed_at).where(
                    StrategyPosition.strategy_id == listing.strategy_id,
                    StrategyPosition.status == "closed",
                )
            )
        ).all()
    )
    priced.sort(
        key=lambda t: closed_at_by_id.get(t.position_id) or datetime.min.replace(tzinfo=UTC)
    )

    cumulative = Decimal("0")
    series: list[Decimal] = []
    wins = 0
    for trip in priced:
        assert trip.net_pnl is not None  # narrowed above
        cumulative += trip.net_pnl
        series.append(cumulative)
        if trip.net_pnl > 0:
            wins += 1

    live_count = len(priced)
    win_rate = Decimal(wins) / Decimal(live_count)

    # Invariant: a zero P&L with zero trades is the refuse case, never a row.
    if live_count == 0:  # pragma: no cover - guarded by the refuse above
        raise NothingToPublishError("live_trades_count would be 0")

    return SnapshotPayload(
        listing_id=str(listing.id),
        snapshot_date=snapshot_date.isoformat(),
        sequence_number=sequence_number,
        cumulative_pnl_inr=_format_decimal(cumulative, _PNL_SCALE),
        # A "% of the cumulative-P&L peak" is not meaningful for a live series
        # (the real BSE series computes to 2,411% and would overflow the
        # NUMERIC(7,4) column). Live listings publish the rupee drawdown.
        max_drawdown_pct=None,
        max_drawdown_inr=_format_decimal(_max_drawdown_inr(series), _PNL_SCALE),
        total_trades=live_count,  # paper sessions are never summed into a live record
        win_rate=_format_decimal(win_rate, _WIN_RATE_SCALE),
        sharpe_ratio=None,
        days_since_publish=days_since_publish,
        paper_trades_count=0,
        live_trades_count=live_count,
        unpriced_positions=len(unpriced),
        pnl_basis=PNL_BASIS_RECONCILED_NET,
    )


async def _paper_payload(
    db: AsyncSession,
    listing: MarketplaceListing,
    snapshot_date: date,
    sequence_number: int,
    days_since_publish: int,
) -> SnapshotPayload:
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
    if not sessions:
        raise NothingToPublishError(
            f"Listing {listing.id!s}: paper strategy has no completed session. Nothing published."
        )

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

    if paper_trades == 0:
        raise NothingToPublishError(
            f"Listing {listing.id!s}: completed paper sessions carry 0 trades. Nothing published."
        )

    win_rate = Decimal(winning_sessions) / Decimal(len(sessions))

    return SnapshotPayload(
        listing_id=str(listing.id),
        snapshot_date=snapshot_date.isoformat(),
        sequence_number=sequence_number,
        cumulative_pnl_inr=_format_decimal(cumulative_pnl, _PNL_SCALE),
        max_drawdown_pct=_format_decimal(_max_drawdown_pct(cumulative_pnls), _DRAWDOWN_SCALE),
        max_drawdown_inr=_format_decimal(_max_drawdown_inr(cumulative_pnls), _PNL_SCALE),
        total_trades=paper_trades,
        win_rate=_format_decimal(win_rate, _WIN_RATE_SCALE),
        sharpe_ratio=None,
        days_since_publish=days_since_publish,
        paper_trades_count=paper_trades,
        live_trades_count=0,
        unpriced_positions=None,
        pnl_basis=PNL_BASIS_PAPER_SESSIONS,
    )


async def build_snapshot_preview(
    db: AsyncSession,
    listing_id: Any,
    snapshot_date: date | None = None,
) -> SnapshotPayload:
    """DRY RUN — the payload the next snapshot WOULD write. Inserts nothing.

    Same listing / duplicate-day / sequence resolution as
    :func:`create_daily_snapshot`, same refusal rules; the only difference is
    that nothing is added to the session. The founder reads this before the
    first real snapshot.
    """
    listing, target_date, next_sequence, _prior_hash = await _resolve_chain_head(
        db, listing_id, snapshot_date
    )
    return await gather_performance_payload(db, listing, target_date, next_sequence)


async def _resolve_chain_head(
    db: AsyncSession, listing_id: Any, snapshot_date: date | None
) -> tuple[MarketplaceListing, date, int, str | None]:
    target_date = snapshot_date or datetime.now(UTC).date()

    listing = (
        await db.execute(select(MarketplaceListing).where(MarketplaceListing.id == listing_id))
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
    return listing, target_date, next_sequence, prior_hash


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
    listing, target_date, next_sequence, prior_hash = await _resolve_chain_head(
        db, listing_id, snapshot_date
    )

    payload = await gather_performance_payload(db, listing, target_date, next_sequence)

    data_hash = data_hash_for(payload.model_dump())
    chain_sig = chain_signature_for(data_hash=data_hash, prior_hash=prior_hash)

    snapshot = LedgerSnapshot(
        listing_id=listing.id,
        snapshot_date=target_date,
        sequence_number=next_sequence,
        cumulative_pnl_inr=Decimal(payload.cumulative_pnl_inr),
        max_drawdown_pct=(
            None if payload.max_drawdown_pct is None else Decimal(payload.max_drawdown_pct)
        ),
        max_drawdown_inr=(
            None if payload.max_drawdown_inr is None else Decimal(payload.max_drawdown_inr)
        ),
        total_trades=payload.total_trades,
        win_rate=Decimal(payload.win_rate),
        sharpe_ratio=None,
        days_since_publish=payload.days_since_publish,
        paper_trades_count=payload.paper_trades_count,
        live_trades_count=payload.live_trades_count,
        unpriced_positions=payload.unpriced_positions,
        pnl_basis=payload.pnl_basis,
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
    "PNL_BASIS_PAPER_SESSIONS",
    "PNL_BASIS_RECONCILED_NET",
    "ListingNotFoundError",
    "NothingToPublishError",
    "SnapshotAlreadyExistsError",
    "SnapshotPayload",
    "build_snapshot_preview",
    "create_daily_snapshot",
    "gather_performance_payload",
]


_ = Field  # silence the unused-import linter when pydantic Field
# isn't used (kept around for the SnapshotPayload's potential
# future extra-validation needs).
