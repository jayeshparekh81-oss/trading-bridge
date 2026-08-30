"""Marketplace subscriber fan-out — read-only subscriber lookup (Module 1).

Purpose
-------
This module is the future home of "one TradingView signal -> many
subscribers' broker accounts" execution. It is being built module-by-module
behind a flag so the live owner path is never disturbed.

What is live today (and stays byte-identical)
---------------------------------------------
The owner path is strictly **1 -> 1**: an inbound webhook resolves ONE owner
:class:`Strategy` and the executor places orders against that strategy's
single ``broker_credential_id``. The ONLY call site of this module in the
live path is a **flag-gated, LOG-ONLY** block at the end of the strategy
webhook handler (``strategy_webhook.py``), AFTER the owner dispatch. When
``settings.marketplace_fanout_enabled`` is ``False`` (the default) that block
is skipped entirely and the owner path is byte-identical. ``strategy_executor``,
``signal_execution`` and ``direct_exit`` never import this module.

Master switch
-------------
All subscriber behaviour is gated by ``settings.marketplace_fanout_enabled``
(env ``MARKETPLACE_FANOUT_ENABLED``, default ``False`` — see
:mod:`app.core.config`). Keeping the flag ``False`` guarantees owner-only
1 -> 1 execution.

Scope (this file)
-----------------
* :func:`resolve_active_subscriptions` (Module 1) — a real, **READ-ONLY** SELECT
  (join of ``marketplace_subscriptions`` to ``marketplace_listings``) returning
  the active subscriptions for a strategy. No INSERT/UPDATE/DELETE, no flush,
  no commit, no session mutation.
* :func:`dispatch_subscriber_executions` (Module 2) — **PAPER ONLY**. For each
  active subscriber it runs ONE simulated fill using the OWNER's exact paper
  primitive (:func:`app.services.strategy_executor._simulate_fill`). It NEVER
  calls a real broker / places a real order, does NOT read or honour any
  live/paper flag for subscribers, and writes NO position or order row — so the
  owner's position state is untouched (a subscriber paper position would
  otherwise sum into the owner's live position, since positions are keyed by
  ``(strategy, symbol, side)`` ignoring ``user_id``). Durable per-subscriber
  positions with real credentials + per-subscriber quantity are Module 4 (which
  needs a migration). Per-subscriber failures are isolated (log + continue).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.broker_credential import BrokerCredential
from app.db.models.marketplace_listing import MarketplaceListing
from app.db.models.marketplace_subscription import MarketplaceSubscription
from app.services.broker_position_batch import (
    POSITION_UNKNOWN,
    gather_broker_positions,
)
from app.services.symbol_match import find_matching_position

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.strategy import Strategy
    from app.db.models.strategy_signal import StrategySignal

logger = get_logger("app.services.marketplace_fanout")

#: Subscription lifecycle value that means "currently entitled". The CHECK
#: constraint on ``marketplace_subscriptions.status`` pins the vocabulary at
#: the migration layer; this matches the API layer's "active" subscribe state.
_ACTIVE_STATUS = "active"

#: TTL for the per-subscriber idempotency slot. Matches the owner webhook's
#: ``IDEMPOTENCY_TTL_SECONDS`` so subscriber dedupe tracks owner dedupe.
_SUBSCRIBER_IDEMPOTENCY_TTL_SECONDS = 60


@dataclass(frozen=True)
class SubscriberRef:
    """Read-only descriptor of one active subscriber of a strategy.

    Decoupled from the ORM identity map (so callers can log/iterate it without
    holding the session open). Carries the per-subscriber execution config added
    in Module 4 (``lots_override``, ``execution_mode``, ``is_paper``,
    ``direction_filter``, ``broker_credential_id``) with defaults matching the
    DB defaults — but the fan-out is still PAPER ONLY and does NOT branch on
    ``execution_mode`` / ``direction_filter`` / ``is_paper`` yet.
    """

    subscription_id: uuid.UUID
    subscriber_id: uuid.UUID
    listing_id: uuid.UUID
    status: str
    subscribed_at: datetime
    access_until: datetime | None
    # Module 4 per-subscriber execution config (defaults match the DB defaults).
    lots_override: int | None = None
    execution_mode: str = "auto"
    is_paper: bool = True
    direction_filter: str = "all"
    broker_credential_id: uuid.UUID | None = None


@dataclass(frozen=True)
class PaperExecutionResult:
    """Outcome of one PAPER (simulated) subscriber execution — Module 2.

    ``paper`` is always ``True`` in this module. ``status`` vocabulary (P0):
    ``filled`` (simulated fill / mirrored close), ``duplicate`` (idempotency),
    ``skipped_direction_filter`` (an ENTRY whose side the subscriber's
    ``direction_filter`` excludes — exits are never filtered),
    ``skipped_already_in_position`` (entry while a subscriber position is open
    — design #3, summing removed), ``skipped_no_position`` (exit with nothing
    to close — the unwanted-short guard), ``refused_size`` (lots/shares
    min-2/even-only violation — loud, never rounded),
    ``failed_insufficient_funds`` (margin-safety clear-fail, plain subscriber
    message in ``error``), ``failed`` (isolated per-subscriber exception),
    ``notify_only`` (a MANUAL subscriber's exit is surfaced as a message in
    ``notify_message`` and is NEVER auto-filled — Module B), or ``skipped``
    (an exit with nothing left to close — already-flat).
    """

    subscription_id: uuid.UUID
    subscriber_id: uuid.UUID
    symbol: str
    action: str
    side: str | None
    quantity: int
    paper: bool
    broker_order_id: str | None
    avg_price: str | None
    status: str
    #: The persisted/affected subscriber StrategyPosition id (entries AND
    #: mirrored exits — see :func:`fan_out_exit`); None on refusals/failures.
    position_id: str | None = None
    #: The broker credential the subscriber WOULD trade on (resolved + recorded,
    #: but NEVER used to build/call a broker in this PAPER module), + its source.
    resolved_credential_id: str | None = None
    credential_source: str | None = None
    error: str | None = None
    #: MANUAL-mode exit surface (Module B): the plain instruction a MANUAL
    #: subscriber must action by hand. Set ONLY on ``notify_only`` results;
    #: ``None`` everywhere else. No fill is ever simulated for these.
    notify_message: str | None = None


def fanout_enabled() -> bool:
    """Return the marketplace fan-out master switch.

    Reads ``settings.marketplace_fanout_enabled`` (env
    ``MARKETPLACE_FANOUT_ENABLED``). Pure, side-effect-free. Defaults to
    ``False`` so the owner 1 -> 1 path is the only behaviour today.
    """
    return bool(get_settings().marketplace_fanout_enabled)


async def resolve_active_subscriptions(
    strategy_id: uuid.UUID,
    db: AsyncSession,
) -> list[SubscriberRef]:
    """Read-only: the active subscriptions whose listing maps to ``strategy_id``.

    Joins ``marketplace_subscriptions`` to ``marketplace_listings`` on
    ``listing_id`` and selects rows where the listing's ``strategy_id`` matches
    AND ``MarketplaceSubscription.status == 'active'``.

    This is a **pure SELECT**: it performs NO INSERT/UPDATE/DELETE, no flush,
    no commit, and does not mark anything dirty. It returns lightweight,
    immutable :class:`SubscriberRef` descriptors (only fields that exist today
    — no execution fields). Callers in Module 1 only LOG the result; nothing
    is dispatched or executed.
    """
    stmt = (
        select(MarketplaceSubscription)
        .join(
            MarketplaceListing,
            MarketplaceListing.id == MarketplaceSubscription.listing_id,
        )
        .where(
            MarketplaceListing.strategy_id == strategy_id,
            MarketplaceSubscription.status == _ACTIVE_STATUS,
        )
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        SubscriberRef(
            subscription_id=row.id,
            subscriber_id=row.subscriber_id,
            listing_id=row.listing_id,
            status=row.status,
            subscribed_at=row.subscribed_at,
            access_until=row.access_until,
            lots_override=row.lots_override,
            execution_mode=row.execution_mode,
            is_paper=row.is_paper,
            direction_filter=row.direction_filter,
            broker_credential_id=row.broker_credential_id,
        )
        for row in rows
    ]


@dataclass(frozen=True)
class SubscriberCredentialResolution:
    """Which broker credential a subscriber WOULD trade on.

    PAPER ONLY in this module: the resolution is computed + recorded + logged but
    NEVER used to build/call a broker, decrypt a credential, or place a real
    order. ``source`` is ``"explicit"`` (the subscriber's chosen cred),
    ``"fallback"`` (their most-recent active cred), or ``"none"`` (no usable
    credential — the missing-credential flag, ``usable=False``).
    """

    credential_id: uuid.UUID | None
    source: str
    usable: bool
    reason: str | None = None


async def resolve_subscriber_credential(
    subscriber: SubscriberRef,
    db: AsyncSession,
) -> SubscriberCredentialResolution:
    """Resolve (read-only) the broker credential a subscriber would trade on.

    Resolution order:
      1. ``subscriber.broker_credential_id`` when it points to an ACTIVE
         credential owned by the subscriber -> ``source='explicit'``.
      2. Otherwise the subscriber's most-recently-created ACTIVE credential ->
         ``source='fallback'``.
      3. No active credential -> ``usable=False``, ``source='none'`` (the
         missing-credential flag).

    **PAPER ONLY / machinery only.** This is a pure SELECT — it NEVER builds a
    broker, calls a broker, decrypts a credential, or places an order. Wiring
    the resolved credential to a real order is a later, separately-gated phase.
    """
    explicit_id = subscriber.broker_credential_id
    if explicit_id is not None:
        row = await db.get(BrokerCredential, explicit_id)
        if (
            row is not None
            and row.user_id == subscriber.subscriber_id
            and row.is_active
        ):
            return SubscriberCredentialResolution(explicit_id, "explicit", True)

    stmt = (
        select(BrokerCredential)
        .where(
            BrokerCredential.user_id == subscriber.subscriber_id,
            BrokerCredential.is_active.is_(True),
        )
        .order_by(BrokerCredential.created_at.desc())
        .limit(1)
    )
    fallback = (await db.execute(stmt)).scalar_one_or_none()
    if fallback is not None:
        return SubscriberCredentialResolution(fallback.id, "fallback", True)

    return SubscriberCredentialResolution(
        None, "none", False, "subscriber has no active broker credential"
    )


def _subscriber_idempotency_key(subscription_id: uuid.UUID, signal_token: str) -> str:
    """Per-subscriber dedupe key — ``{subscription_id}:{signal_token}``.

    Distinct from the OWNER key (``{user_id}:{signal_hash}``, claimed unchanged
    by the webhook), so the two never collide. ``signal_token`` is the owner's
    ``signal_hash`` when threaded from the webhook, else the persisted signal id.
    """
    return f"{subscription_id}:{signal_token}"


async def _claim_subscriber_idempotency(key: str) -> bool:
    """Claim a per-subscriber idempotency slot via the EXISTING Redis mechanism.

    Returns ``True`` if this is the first time (proceed) and ``False`` ONLY when
    the slot was already taken (a genuine duplicate). **Fail-open:** if Redis is
    unavailable the claim is treated as first-time so a Redis outage can never
    block paper dispatch (a duplicate is far less harmful in PAPER than a
    silently-dropped subscriber).
    """
    from app.core import redis_client

    try:
        return await redis_client.set_idempotency_key(
            key, ttl_seconds=_SUBSCRIBER_IDEMPOTENCY_TTL_SECONDS
        )
    except Exception as exc:  # fail-open — Redis outage must not block dispatch
        logger.warning("fanout.paper.idempotency_unavailable", key=key, error=str(exc))
        return True


async def _alert_subscriber_failure(
    *, signal_id: str, subscription_id: str, subscriber_id: str, error: str
) -> None:
    """Best-effort operator alert on a subscriber failure via the EXISTING
    ``telegram_alerts`` service. An alert failure can NEVER break dispatch."""
    try:
        from app.services import telegram_alerts as _alerts

        await _alerts.send_alert(
            _alerts.AlertLevel.WARNING,
            "⚠️ *Marketplace paper fan-out* — subscriber failed\n"
            f"signal=`{signal_id}` subscription=`{subscription_id}` "
            f"subscriber=`{subscriber_id}`\nerror=`{error}`",
        )
    except Exception:  # best-effort — never propagate
        logger.warning(
            "fanout.paper.alert_failed",
            signal_id=signal_id,
            subscription_id=subscription_id,
        )


# ═══════════════════════════════════════════════════════════════════════
# FANOUT_DESIGN P0 infra — position-check, real lot-math, margin-safety
# ═══════════════════════════════════════════════════════════════════════

#: Size rules for lots_override / cash shares (mirrors the cash-module spec):
#: minimum 2 and even-only — violations REFUSE loudly, never silently rounded.
_MIN_SIZE = 2


@runtime_checkable
class SubscriberPositionProvider(Protocol):
    """Where a subscriber's CURRENT position truth comes from (design #3).

    Paper stage: :class:`PaperPositionProvider` reads the subscriber's own
    paper ``StrategyPosition`` rows. Real-money stage: a broker-backed
    provider implements this same interface (net position via the
    subscriber's OWN credential) — the call sites don't change.
    """

    async def find_open(self, db: "AsyncSession", *, strategy_id: uuid.UUID,
                        subscription_id: uuid.UUID,
                        symbol: str | None = None) -> Any: ...


class PaperPositionProvider:
    """Paper truth = the subscriber's own open/partial position rows.

    ``symbol`` is accepted for interface parity with the broker-backed provider
    and deliberately IGNORED here — the paper path must stay byte-identical and
    must never make a network call.
    """

    #: Paper never talks to a broker; the batch prefetch is skipped for it.
    BROKER_BACKED = False

    async def find_open(self, db: "AsyncSession", *, strategy_id: uuid.UUID,
                        subscription_id: uuid.UUID,
                        symbol: str | None = None):
        from app.db.models.strategy_position import StrategyPosition

        stmt = (
            select(StrategyPosition)
            .where(
                StrategyPosition.strategy_id == strategy_id,
                StrategyPosition.subscription_id == subscription_id,
                StrategyPosition.status.in_(("open", "partial")),
            )
            .order_by(StrategyPosition.opened_at.desc())
        )
        return (await db.execute(stmt)).scalars().first()


class BrokerBackedPositionProvider:
    """REAL-money truth: the broker's live positions, not our stored row.

    Implements design #3's first principle — "position hai ya nahi, iska SACH
    BROKER ki live position hai, TRADETRI ka stored record NAHI".

    Three-valued, and the third value is the point:
      * a stored position object — the broker CONFIRMS we hold it
      * ``None``                 — the broker confidently reports FLAT
      * ``POSITION_UNKNOWN``     — we could not tell (unreachable, slow, budget
        exhausted, or an unparseable symbol on either side)

    ``POSITION_UNKNOWN`` must never be collapsed into "flat", because "flat"
    authorises an entry and "not flat" authorises an exit. Both call sites
    place NOTHING on UNKNOWN.

    CONCURRENCY: :meth:`prefetch` resolves EVERY subscriber's broker positions
    in one bounded, budgeted batch BEFORE the dispatch loop, so the webhook
    never performs a per-subscriber serial network await. :meth:`find_open`
    then does local, pure symbol matching against that cache.
    """

    BROKER_BACKED = True

    def __init__(
        self,
        fetch_positions,
        *,
        per_call_timeout: float | None = None,
        concurrency: int | None = None,
        total_budget: float | None = None,
    ) -> None:
        #: async (subscription_id) -> iterable of broker positions
        self._fetch = fetch_positions
        self._per_call_timeout = per_call_timeout
        self._concurrency = concurrency
        self._total_budget = total_budget
        self._cache: dict[uuid.UUID, Any] = {}
        self._prefetched = False
        self._paper = PaperPositionProvider()

    async def prefetch(self, subscription_ids) -> None:
        """One bounded+budgeted batch for the whole dispatch. Never raises."""
        kwargs: dict[str, Any] = {}
        if self._per_call_timeout is not None:
            kwargs["per_call_timeout"] = self._per_call_timeout
        if self._concurrency is not None:
            kwargs["concurrency"] = self._concurrency
        if self._total_budget is not None:
            kwargs["total_budget"] = self._total_budget
        self._cache = await gather_broker_positions(
            list(subscription_ids), self._fetch, **kwargs
        )
        self._prefetched = True

    async def find_open(self, db: AsyncSession, *, strategy_id: uuid.UUID,
                        subscription_id: uuid.UUID,
                        symbol: str | None = None):
        # The STORED row is still what downstream mutates on an exit, so read it
        # first (cheap, no network). The broker decides whether we may act.
        stored = await self._paper.find_open(
            db, strategy_id=strategy_id, subscription_id=subscription_id
        )

        if not self._prefetched:
            # Defensive: a caller that forgot prefetch() must not silently fall
            # back to stored-only truth.
            logger.error(
                "fanout.broker_provider.not_prefetched",
                subscription_id=str(subscription_id),
            )
            return POSITION_UNKNOWN

        raw = self._cache.get(subscription_id, POSITION_UNKNOWN)
        if raw is POSITION_UNKNOWN:
            return POSITION_UNKNOWN

        verify_symbol = symbol or getattr(stored, "symbol", None)
        if verify_symbol is None:
            # Nothing to verify against (no stored row, no signal symbol).
            return stored

        # Pure, local matching through the SHARED normaliser — an ambiguous or
        # unparseable symbol is UNKNOWN, never "flat".
        match, certain = find_matching_position(verify_symbol, raw)
        if not certain:
            logger.warning(
                "fanout.broker_position.symbol_ambiguous",
                subscription_id=str(subscription_id),
                stored_symbol=verify_symbol,
            )
            return POSITION_UNKNOWN

        if match is None:
            # Broker confidently FLAT. On an exit this yields the existing
            # ``skipped_no_position`` guard; on an entry it permits the entry.
            return None

        # Broker CONFIRMS a position.
        if stored is not None:
            return stored          # exits mutate the stored row, so return it

        # No stored row of ours, but the broker holds it. On the ENTRY path
        # (which passes an explicit ``symbol``) this must still BLOCK the
        # entry — the customer is already in this contract, and re-entering
        # would double their exposure. Returning None here would have let the
        # entry through, which is precisely the bug this gate exists to stop.
        # On the EXIT path (no explicit symbol) we have no record of our own,
        # so we deliberately do NOT claim a position to close.
        return match if symbol is not None else None


async def _prefetch_if_broker_backed(provider: Any, subscribers) -> None:
    """Run the batched broker prefetch when (and only when) it applies."""
    if getattr(provider, "BROKER_BACKED", False) and hasattr(provider, "prefetch"):
        await provider.prefetch([s.subscription_id for s in subscribers])


def _unknown_result(sub, *, symbol: str, action: str, side, cred, resolved_cred,
                    what: str) -> PaperExecutionResult:
    """The fail-safe outcome: we could not verify, so we placed NOTHING."""
    return PaperExecutionResult(
        subscription_id=sub.subscription_id,
        subscriber_id=sub.subscriber_id,
        symbol=symbol,
        action=action,
        side=side,
        quantity=0,
        paper=True,
        broker_order_id=None,
        avg_price=None,
        status="skipped_broker_unknown",
        resolved_credential_id=resolved_cred,
        credential_source=cred.source,
        notify_message=(
            f"Could not verify your {symbol} position at the broker, so "
            f"TRADETRI {what}. Please check your broker and act manually "
            "if needed."
        ),
    )


@runtime_checkable
class MarginProvider(Protocol):
    """Margin-safety hook (design #4). Returns ``(ok, subscriber_message)``.

    Paper stage: :func:`paper_margin_provider` (always ok — no broker).
    Real-money stage: a fundlimit-backed provider; on shortfall the dispatch
    records ``failed_insufficient_funds`` with the PLAIN message so the
    subscriber sees exactly why their copy did not execute.
    """

    async def __call__(self, *, subscriber: SubscriberRef, quantity: int,
                       symbol: str) -> tuple[bool, str]: ...


async def paper_margin_provider(*, subscriber: SubscriberRef, quantity: int,
                                symbol: str) -> tuple[bool, str]:
    return True, "paper — margin not checked"


def _is_cash_strategy(strategy: "Strategy") -> bool:
    sj = getattr(strategy, "strategy_json", None) or {}
    return str(sj.get("instrument_type") or "").strip().lower() == "cash"


def _validated_even(value: Any, *, what: str) -> int:
    """min-2 + even-only (refuse, never round) — raises ValueError with the
    loud reason on violation."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{what} {value!r} is not an integer") from None
    if n < _MIN_SIZE:
        raise ValueError(f"{what} {n} below minimum {_MIN_SIZE}")
    if n % 2 != 0:
        raise ValueError(f"{what} {n} is odd — even-only by spec")
    return n


#: The values ``marketplace_subscriptions.direction_filter`` may hold. CHECK-
#: enforced by migration 035, so anything else means the row was edited around
#: the constraint.
_DIRECTION_ALL = "all"
#: OrderSide.BUY.value / OrderSide.SELL.value, spelled out rather than imported:
#: this module deliberately keeps a narrow import surface (see the byte-identical
#: owner-path note at the top), and the values are pinned by a test against the
#: real enum so they cannot drift.
_DIRECTION_BY_SIDE: dict[str, str] = {"buy": "long", "sell": "short"}


def _direction_allows(direction_filter: str | None, side_value: str) -> bool:
    """Does this subscriber's direction filter permit an ENTRY on ``side``?

    ⚠️ ENTRIES ONLY. Never call this on an exit. A subscriber who is already in
    a position must ALWAYS be able to close it, whatever their filter says —
    filtering an exit would strand them in a position they cannot get out of,
    which is a far worse failure than taking a side they did not want.

    The two vocabularies differ and the mapping is the whole point of this
    function: ``side_value`` is an ``OrderSide`` value (buy/sell), while
    ``direction_filter`` is long/short.
    ``_resolve_side`` maps long->BUY and short->SELL, so BUY<->long and
    SELL<->short.

    An unrecognised value falls back to ``all`` (permit) and logs loudly. It is
    the column's own default, and the alternative — silently refusing every
    entry on a malformed string — looks exactly like the strategy going dead,
    which is the harder failure to diagnose. Case and surrounding whitespace are
    normalised first so "Long" narrows as intended rather than falling back.
    """
    raw = (direction_filter or _DIRECTION_ALL).strip().lower()
    if raw == _DIRECTION_ALL:
        return True
    wanted = _DIRECTION_BY_SIDE.get((side_value or "").strip().lower())
    if raw in ("long", "short"):
        return raw == wanted
    logger.warning(
        "fanout.direction.unrecognised",
        direction_filter=str(direction_filter),
        note="not in {all,long,short}; treating as 'all'",
    )
    return True


def _real_lot_size(symbol: str, scrip_master: Any | None) -> int:
    """REAL lot_size via a read-only scrip-master lookup (design #5).

    ``scrip_master`` is injectable for tests; default = the shared Dhan
    master. Unresolvable symbol → paper fallback 1 (logged, never fatal).
    """
    master = scrip_master
    if master is None:
        from app.brokers.dhan import _SCRIP_MASTER as master  # noqa: N811
    try:
        sid = master.lookup(str(symbol).upper(), "NSE_FNO")
        if sid:
            ls = master.lot_size(sid)
            if ls and int(ls) > 0:
                return int(ls)
    except Exception:  # noqa: BLE001 — lookup is best-effort in paper
        pass
    logger.info("fanout.size.lot_size_unresolved", symbol=symbol,
                fallback=1)
    return 1


def _resolve_subscriber_size(strategy: "Strategy", sub: SubscriberRef,
                             symbol: str, scrip_master: Any | None) -> int:
    """Per-subscriber quantity (design #5 + cash spec). Raises ValueError
    with a loud reason when the override violates min-2/even-only.

    * CASH strategy → SHARES: ``lots_override`` (validated) else
      ``strategy_json.entry_shares`` (default 2, validated).
    * else (futures/options) → LOTS: ``lots_override`` (validated) else the
      strategy default ``entry_lots``; qty = lots × REAL lot_size.
    """
    if _is_cash_strategy(strategy):
        sj = strategy.strategy_json or {}
        raw = sub.lots_override if sub.lots_override is not None \
            else sj.get("entry_shares", _MIN_SIZE)
        return _validated_even(raw, what="cash shares")
    if sub.lots_override is not None:
        lots = _validated_even(sub.lots_override, what="lots_override")
    else:
        lots = int(strategy.entry_lots or 1)
    return lots * _real_lot_size(symbol, scrip_master)


async def dispatch_subscriber_executions(
    signal: StrategySignal,
    strategy: Strategy,
    subscribers: list[SubscriberRef],
    db: AsyncSession,
    signal_hash: str | None = None,
    *,
    scrip_master: Any | None = None,
    margin_provider: "MarginProvider | None" = None,
    position_provider: "SubscriberPositionProvider | None" = None,
) -> list[PaperExecutionResult]:
    """PAPER ONLY — run + persist one simulated execution per active subscriber.

    For every subscriber this runs ONE simulated (paper) fill using the SAME
    primitive the owner's paper path uses
    (:func:`app.services.strategy_executor._simulate_fill`) and, for ENTRY
    signals, persists an ISOLATED subscriber ``StrategyPosition`` +
    ``StrategyExecution`` tagged with the row's ``subscription_id``
    (migration 034). Returns one :class:`PaperExecutionResult` per subscriber.

    Hard guarantees:
      * **PAPER ONLY.** The only execution primitive used is ``_simulate_fill``
        (pure — no broker). No real broker is built or called, no real order is
        placed, for any subscriber, under any config. This module does NOT read
        or honour ``strategy.is_paper`` / ``settings.strategy_paper_mode`` /
        ``subscription.is_paper`` / ``execution_mode`` / ``direction_filter`` to
        go live — subscribers are forced to paper regardless.
      * **Per-subscriber credential RESOLVED, never used (Module 4).** Each
        subscriber's broker credential is resolved + validated via
        :func:`resolve_subscriber_credential` and RECORDED (in the execution's
        ``broker_response`` + logs + result), but it is NEVER used to build/call
        a broker or place a real order here. The position/execution FK stays the
        owner's strategy credential (paper placeholder). Wiring the resolved
        credential to a real order is a later, separately-gated phase.
      * **Owner isolation.** Subscriber rows carry a NON-NULL ``subscription_id``
        and are scoped to it. The owner's entry-sum / exit / position-loop /
        reconciliation lookups all filter ``subscription_id IS NULL``, so a
        subscriber row can NEVER sum into, close, or be managed alongside the
        owner's (LIVE) position, and the position loop never polls subscriber
        rows — so they never trigger a broker call.
      * **Subscriber-aware idempotency (Module 5).** Before persisting an ENTRY,
        each subscriber claims a per-subscription dedupe slot
        ``{subscription_id}:{signal_hash or signal.id}`` via the EXISTING Redis
        idempotency mechanism — distinct from the owner key
        (``{user_id}:{signal_hash}``, claimed unchanged by the webhook). A
        re-dispatched/duplicate signal therefore does NOT create a second paper
        position/execution for the same subscriber+signal (``status='duplicate'``).
        Fail-open: a Redis outage never blocks dispatch.
      * **Per-subscriber isolation + alerting (Module 5).** Each subscriber's
        write runs in its own SAVEPOINT; one subscriber failing (bad/missing
        cred, sim error, …) rolls back ONLY its row, is logged structured,
        recorded as ``status='failed'`` with the reason, and best-effort alerted
        via the EXISTING operator channel (``telegram_alerts``) — the others
        (and the owner) proceed. An alert failure can never break dispatch.

    Per-subscriber size (P0, design #5): ``subscription.lots_override`` when
    set — validated min-2/even-only (violations → ``refused_size``, loud,
    never rounded) — else the strategy default; qty = lots × REAL lot_size via
    a read-only scrip-master lookup (injectable; unresolvable → paper fallback
    1). CASH strategies use SHARES semantics (min-2/even). Entries where the
    subscriber is ALREADY in a position are ``skipped_already_in_position``
    (design #3 — the old sum-into-existing behaviour was drifted and is
    REMOVED). Margin-safety (design #4) runs via the injectable
    ``margin_provider`` → ``failed_insufficient_funds`` with a plain message.
    Subscriber EXIT mirroring lives in :func:`fan_out_exit` (design #1) — for
    non-entry actions THIS function still only logs a paper simulation; the
    wiring of exits is a separate founder-gated module.

    The returned list is the per-subscriber summary: one
    :class:`PaperExecutionResult` each, ``status`` in
    ``{"filled", "duplicate", "failed"}`` (failed carries ``error``).
    """
    # OPTIONS gate (Brick #4 slice-①, audit landmine): an options strategy's
    # fan-out would mirror the UNDERLYING (signal.symbol is the futures-resolved
    # symbol; map_pine_to_option_order is never called here) at the underlying's
    # lot size — wrong instrument, wrong size — and, with no options exit hook,
    # the mirror would be a permanent orphan. Until proper option-leg mirroring
    # lands (a later slice), options-strategy fan-out is SKIPPED entirely: no
    # mirror row, no execution row, for every subscriber. FUTURES/CASH
    # strategies are untouched (futures-default classifier — the live
    # strategy_json IS NULL rows classify futures and never hit this).
    from app.strategy_engine.instrument_router import (
        OPTIONS as _OPTIONS,
    )
    from app.strategy_engine.instrument_router import (
        resolve_instrument_type as _resolve_instrument_type,
    )

    if _resolve_instrument_type(strategy) == _OPTIONS:
        logger.info(
            "fanout.options_not_supported_skip",
            strategy_id=str(strategy.id),
            signal_id=str(signal.id),
            subscribers=len(subscribers),
        )
        return []

    # Lazy imports mirror signal_execution.py's executor-import pattern and bind
    # the EXACT paper primitives the owner path runs (never the live-order code).
    from app.db.models.strategy_execution import StrategyExecution
    from app.db.models.strategy_position import StrategyPosition
    from app.services.strategy_executor import (
        StrategyExecutorError,
        _resolve_side,
        _simulate_fill,
    )

    provider = position_provider or PaperPositionProvider()
    check_margin = margin_provider or paper_margin_provider

    # ONE bounded+budgeted broker batch for the whole dispatch. No-op for the
    # default paper provider, so the paper path performs ZERO network calls and
    # stays byte-identical.
    await _prefetch_if_broker_backed(provider, subscribers)

    side_hint = (signal.raw_payload or {}).get("side")

    # ENTRY actions resolve to an OrderSide; EXIT / PARTIAL / SL_HIT raise here —
    # those are subscriber exits, deferred to a later phase (log-only here).
    try:
        entry_side = _resolve_side(signal.action, side_hint=side_hint)
    except StrategyExecutorError:
        entry_side = None

    results: list[PaperExecutionResult] = []
    wrote_any = False

    for sub in subscribers:
        # ── DIRECTION FILTER (Module B) ────────────────────────────────
        # ENTRIES ONLY. ``entry_side is None`` means this dispatch is not an
        # entry, and an exit is NEVER filtered — a subscriber already holding a
        # position must always be able to close it, whatever their filter says.
        # Checked FIRST so a filtered-out subscriber costs no credential
        # resolution, no sizing and no idempotency claim.
        if entry_side is not None and not _direction_allows(
            sub.direction_filter, entry_side.value
        ):
            results.append(
                PaperExecutionResult(
                    subscription_id=sub.subscription_id,
                    subscriber_id=sub.subscriber_id,
                    symbol=signal.symbol,
                    action=signal.action,
                    side=entry_side.value,
                    quantity=0,
                    paper=True,
                    broker_order_id=None,
                    avg_price=None,
                    status="skipped_direction_filter",
                    resolved_credential_id=None,
                    credential_source=None,
                )
            )
            logger.info(
                "fanout.direction.skipped",
                signal_id=str(signal.id),
                subscription_id=str(sub.subscription_id),
                subscriber_id=str(sub.subscriber_id),
                side=entry_side.value,
                direction_filter=str(sub.direction_filter),
            )
            continue

        qty = 0  # resolved inside the try; stays 0 in early-refusal results
        try:
            # Resolve (read-only) the credential this subscriber WOULD trade on.
            # PAPER ONLY: recorded + logged below, but NEVER used to build/call a
            # broker or place a real order in this module.
            cred = await resolve_subscriber_credential(sub, db)
            resolved_cred = (
                str(cred.credential_id) if cred.credential_id is not None else None
            )

            # Real lot-math (design #5): lots_override validated min-2/even-only
            # (refuse loudly, never round) × REAL lot_size; CASH mode = shares.
            try:
                qty = _resolve_subscriber_size(
                    strategy, sub, signal.symbol, scrip_master
                )
            except ValueError as verr:
                results.append(
                    PaperExecutionResult(
                        subscription_id=sub.subscription_id,
                        subscriber_id=sub.subscriber_id,
                        symbol=signal.symbol,
                        action=signal.action,
                        side=str(side_hint) if side_hint is not None else None,
                        quantity=0,
                        paper=True,
                        broker_order_id=None,
                        avg_price=None,
                        status="refused_size",
                        resolved_credential_id=resolved_cred,
                        credential_source=cred.source,
                        error=str(verr),
                    )
                )
                logger.warning(
                    "fanout.size.refused",
                    signal_id=str(signal.id),
                    subscription_id=str(sub.subscription_id),
                    subscriber_id=str(sub.subscriber_id),
                    reason=str(verr),
                )
                continue

            sim = _simulate_fill(signal, qty)  # FORCED paper — pure, no broker
            avg = sim.get("avg_price")
            order_id = str(sim.get("broker_order_id"))
            position_id: str | None = None

            if entry_side is not None:
                if strategy.broker_credential_id is None:
                    raise StrategyExecutorError(
                        "strategy has no broker_credential_id for the paper "
                        "placeholder; cannot persist subscriber position"
                    )
                # Subscriber-aware idempotency (Module 5) — dedupe a re-delivered
                # signal per (subscription, signal). Distinct from the owner key
                # (claimed unchanged by the webhook). A duplicate is a no-op.
                idem_key = _subscriber_idempotency_key(
                    sub.subscription_id, signal_hash or str(signal.id)
                )
                if not await _claim_subscriber_idempotency(idem_key):
                    results.append(
                        PaperExecutionResult(
                            subscription_id=sub.subscription_id,
                            subscriber_id=sub.subscriber_id,
                            symbol=signal.symbol,
                            action=signal.action,
                            side=entry_side.value,
                            quantity=qty,
                            paper=True,
                            broker_order_id=None,
                            avg_price=None,
                            status="duplicate",
                            resolved_credential_id=resolved_cred,
                            credential_source=cred.source,
                        )
                    )
                    logger.info(
                        "fanout.paper.duplicate_skipped",
                        signal_id=str(signal.id),
                        strategy_id=str(strategy.id),
                        subscription_id=str(sub.subscription_id),
                        subscriber_id=str(sub.subscriber_id),
                        idempotency_key=idem_key,
                    )
                    continue

                # AUTO vs MANUAL on ENTRY (design-locked — Module B+ PIECE 0).
                # A MANUAL subscriber is NEVER auto-entered: emit a notify_only
                # result (what they COULD open) and write NOTHING — no fill, no
                # position. Idempotency is claimed above, so a re-delivered
                # entry does not re-notify. Only AUTO subscribers reach the
                # position-check + margin + persist below.
                if str(sub.execution_mode).strip().lower() != "auto":
                    notify_msg = (
                        f"Manual entry — {entry_side.value} signal on "
                        f"{signal.symbol} ({qty}). Your copy is set to MANUAL, "
                        "so no position was opened."
                    )
                    results.append(
                        PaperExecutionResult(
                            subscription_id=sub.subscription_id,
                            subscriber_id=sub.subscriber_id,
                            symbol=signal.symbol,
                            action=signal.action,
                            side=entry_side.value,
                            quantity=qty,
                            paper=True,
                            broker_order_id=None,
                            avg_price=None,
                            status="notify_only",
                            resolved_credential_id=resolved_cred,
                            credential_source=cred.source,
                            notify_message=notify_msg,
                        )
                    )
                    logger.info(
                        "fanout.entry.notify_only",
                        signal_id=str(signal.id),
                        strategy_id=str(strategy.id),
                        subscription_id=str(sub.subscription_id),
                        subscriber_id=str(sub.subscriber_id),
                        symbol=signal.symbol,
                        quantity=qty,
                        execution_mode=sub.execution_mode,
                    )
                    continue

                # Position-check (design #3): a subscriber who is ALREADY in a
                # position must not re-enter — summing is REMOVED (drifted
                # behaviour); the mirror model keeps subscriber exposure equal
                # to one owner cycle.
                existing_pos = await provider.find_open(
                    db, strategy_id=strategy.id,
                    subscription_id=sub.subscription_id,
                    symbol=signal.symbol,
                )
                # FAIL-SAFE: an unverified broker state must NEVER authorise an
                # entry. Treated exactly like "already in a position" — we place
                # nothing and tell the customer.
                if existing_pos is POSITION_UNKNOWN:
                    results.append(_unknown_result(
                        sub, symbol=signal.symbol, action=signal.action,
                        side=entry_side.value, cred=cred,
                        resolved_cred=resolved_cred,
                        what="did not open a position",
                    ))
                    logger.warning(
                        "fanout.entry.skipped_broker_unknown",
                        signal_id=str(signal.id),
                        subscription_id=str(sub.subscription_id),
                        symbol=signal.symbol,
                    )
                    continue
                if existing_pos is not None:
                    results.append(
                        PaperExecutionResult(
                            subscription_id=sub.subscription_id,
                            subscriber_id=sub.subscriber_id,
                            symbol=signal.symbol,
                            action=signal.action,
                            side=entry_side.value,
                            quantity=0,
                            paper=True,
                            broker_order_id=None,
                            avg_price=None,
                            status="skipped_already_in_position",
                            position_id=str(existing_pos.id),
                            resolved_credential_id=resolved_cred,
                            credential_source=cred.source,
                        )
                    )
                    logger.warning(
                        "fanout.entry.already_in_position",
                        signal_id=str(signal.id),
                        subscription_id=str(sub.subscription_id),
                        subscriber_id=str(sub.subscriber_id),
                        position_id=str(existing_pos.id),
                    )
                    continue

                # Margin-safety shape (design #4): clear-fail with a PLAIN
                # subscriber-facing message. Paper provider always passes.
                margin_ok, margin_msg = await check_margin(
                    subscriber=sub, quantity=qty, symbol=signal.symbol
                )
                if not margin_ok:
                    results.append(
                        PaperExecutionResult(
                            subscription_id=sub.subscription_id,
                            subscriber_id=sub.subscriber_id,
                            symbol=signal.symbol,
                            action=signal.action,
                            side=entry_side.value,
                            quantity=qty,
                            paper=True,
                            broker_order_id=None,
                            avg_price=None,
                            status="failed_insufficient_funds",
                            resolved_credential_id=resolved_cred,
                            credential_source=cred.source,
                            error=margin_msg,
                        )
                    )
                    logger.warning(
                        "fanout.entry.insufficient_funds",
                        signal_id=str(signal.id),
                        subscription_id=str(sub.subscription_id),
                        subscriber_id=str(sub.subscriber_id),
                        quantity=qty,
                        message=margin_msg,
                    )
                    await _alert_subscriber_failure(
                        signal_id=str(signal.id),
                        subscription_id=str(sub.subscription_id),
                        subscriber_id=str(sub.subscriber_id),
                        error=margin_msg,
                    )
                    continue

                # Per-subscriber SAVEPOINT — a single failure rolls back ONLY
                # this subscriber's rows, never the others'.
                async with db.begin_nested():
                    now = datetime.now(UTC)
                    # No per-subscriber levels: the drifted local-SL
                    # (target/stop/trail via _compute_levels) is REMOVED —
                    # exits MIRROR the owner's signals (fan_out_exit below).
                    position = StrategyPosition(
                        user_id=sub.subscriber_id,
                        strategy_id=strategy.id,
                        # Paper placeholder FK — no broker is ever built or
                        # called in paper mode. Real per-subscriber creds = M4.
                        broker_credential_id=strategy.broker_credential_id,
                        subscription_id=sub.subscription_id,
                        signal_id=signal.id,
                        symbol=signal.symbol,
                        side=entry_side.value,
                        total_quantity=qty,
                        remaining_quantity=qty,
                        avg_entry_price=avg,
                        status="open",
                        opened_at=now,
                    )
                    db.add(position)
                    await db.flush()
                    position_id = str(position.id)

                    execution = StrategyExecution(
                        signal_id=signal.id,
                        broker_credential_id=strategy.broker_credential_id,
                        subscription_id=sub.subscription_id,
                        leg_number=1,
                        leg_role="entry",
                        symbol=signal.symbol,
                        side=entry_side.value,
                        quantity=qty,
                        order_type="market",
                        price=avg,
                        broker_order_id=order_id,
                        broker_status="complete",
                        broker_response={
                            "paper": True,
                            "marketplace_subscription_id": str(sub.subscription_id),
                            "broker_order_id": order_id,
                            "avg_price": str(avg) if avg is not None else None,
                            "quantity": qty,
                            "lots_override": sub.lots_override,
                            "execution_mode": sub.execution_mode,
                            # Resolved-but-UNUSED credential (recorded for the
                            # future real-order phase; never used to call a broker).
                            "resolved_credential_id": resolved_cred,
                            "credential_source": cred.source,
                            "credential_usable": cred.usable,
                            "source": "marketplace_fanout",
                        },
                        placed_at=now,
                        completed_at=now,
                    )
                    db.add(execution)
                    await db.flush()
                wrote_any = True

            results.append(
                PaperExecutionResult(
                    subscription_id=sub.subscription_id,
                    subscriber_id=sub.subscriber_id,
                    symbol=signal.symbol,
                    action=signal.action,
                    side=(
                        entry_side.value
                        if entry_side is not None
                        else (str(side_hint) if side_hint is not None else None)
                    ),
                    quantity=qty,
                    paper=True,
                    broker_order_id=order_id,
                    avg_price=str(avg) if avg is not None else None,
                    status="filled",
                    position_id=position_id,
                    resolved_credential_id=resolved_cred,
                    credential_source=cred.source,
                )
            )
            logger.info(
                "fanout.paper.executed"
                if entry_side is not None
                else "fanout.paper.simulated_no_persist",
                paper=True,
                persisted=entry_side is not None,
                signal_id=str(signal.id),
                strategy_id=str(strategy.id),
                subscription_id=str(sub.subscription_id),
                subscriber_id=str(sub.subscriber_id),
                symbol=signal.symbol,
                action=signal.action,
                quantity=qty,
                lots_override=sub.lots_override,
                broker_order_id=order_id,
                position_id=position_id,
                credential_source=cred.source,
                resolved_credential_id=resolved_cred,
            )
        except Exception as exc:  # isolate per-subscriber failures — never escalate
            results.append(
                PaperExecutionResult(
                    subscription_id=sub.subscription_id,
                    subscriber_id=sub.subscriber_id,
                    symbol=signal.symbol,
                    action=signal.action,
                    side=str(side_hint) if side_hint is not None else None,
                    quantity=qty,
                    paper=True,
                    broker_order_id=None,
                    avg_price=None,
                    status="failed",
                    error=str(exc),
                )
            )
            logger.warning(
                "fanout.paper.subscriber_failed",
                signal_id=str(signal.id),
                strategy_id=str(strategy.id),
                subscription_id=str(sub.subscription_id),
                subscriber_id=str(sub.subscriber_id),
                error=str(exc),
            )
            # Best-effort operator alert via the EXISTING service — failure to
            # alert can never break dispatch or the other subscribers.
            await _alert_subscriber_failure(
                signal_id=str(signal.id),
                subscription_id=str(sub.subscription_id),
                subscriber_id=str(sub.subscriber_id),
                error=str(exc),
            )

    if wrote_any:
        await db.commit()

    filled = sum(1 for r in results if r.status == "filled")
    duplicate = sum(1 for r in results if r.status == "duplicate")
    notify_only = sum(1 for r in results if r.status == "notify_only")
    failed = sum(1 for r in results if r.status == "failed")
    logger.info(
        "fanout.paper.summary",
        signal_id=str(signal.id),
        strategy_id=str(strategy.id),
        subscriber_count=len(subscribers),
        paper_filled=filled,
        paper_duplicate=duplicate,
        paper_notify_only=notify_only,
        paper_failed=failed,
        persisted=entry_side is not None,
    )
    return results


async def fan_out_exit(
    *,
    signal: StrategySignal,
    strategy: Strategy,
    subscribers: list[SubscriberRef],
    db: AsyncSession,
    action_kind: str,
    signal_hash: str | None = None,
    position_provider: "SubscriberPositionProvider | None" = None,
) -> list[PaperExecutionResult]:
    """MIRROR the owner's exit signal per subscriber (design #1). PAPER ONLY.

    For each subscriber the CURRENT position comes from the (injectable)
    :class:`SubscriberPositionProvider` — design #3's unwanted-short guard:
    a subscriber with NO open position yields ``skipped_no_position`` (loud
    log) and nothing is written; a short can never be created by an exit.

    * ``partial``  → close the payload's ``closePct`` (default 50) percent of
      the SUBSCRIBER'S OWN remaining quantity (owner 50% on a sub holding 8
      closes 4 — never the owner's absolute quantity);
    * ``exit`` / ``sl_hit`` → full close.

    AUTO vs MANUAL (design-locked, Module B): only an AUTO subscriber gets the
    paper mirror-fill. A MANUAL subscriber's exit is surfaced as a
    ``notify_only`` result (``notify_message`` = exactly what to close) and is
    NEVER auto-filled — no simulated fill, no leg, no position mutation. An
    already-flat position yields ``skipped``; a subscriber with no position at
    all yields ``skipped_no_position`` (the loud unwanted-short guard). A
    re-delivered exit is idempotent (``duplicate``) and never double-closes.

    Fills are simulated (``_simulate_fill`` — no broker, ever); the close is
    applied to the STORED ``position.symbol`` (never re-resolved). Failures
    are isolated per subscriber exactly like the entry dispatch.
    """
    from app.db.models.strategy_execution import StrategyExecution
    from app.services.strategy_executor import _simulate_fill

    provider = position_provider or PaperPositionProvider()
    payload = signal.raw_payload or {}
    exit_price = Decimal(str(payload.get("price") or 0))

    # Same single batch on the exit path — bounded webhook latency regardless
    # of subscriber count; no-op (and no network) for the paper provider.
    await _prefetch_if_broker_backed(provider, subscribers)

    results: list[PaperExecutionResult] = []
    wrote_any = False

    for sub in subscribers:
        try:
            cred = await resolve_subscriber_credential(sub, db)
            resolved_cred = (
                str(cred.credential_id) if cred.credential_id is not None else None
            )

            # Per-subscriber idempotency for exits too — a re-delivered exit
            # must not double-close a partial.
            idem_key = _subscriber_idempotency_key(
                sub.subscription_id, signal_hash or str(signal.id)
            )
            if not await _claim_subscriber_idempotency(idem_key):
                results.append(
                    PaperExecutionResult(
                        subscription_id=sub.subscription_id,
                        subscriber_id=sub.subscriber_id,
                        symbol=signal.symbol,
                        action=signal.action,
                        side=None,
                        quantity=0,
                        paper=True,
                        broker_order_id=None,
                        avg_price=None,
                        status="duplicate",
                        resolved_credential_id=resolved_cred,
                        credential_source=cred.source,
                    )
                )
                continue

            position = await provider.find_open(
                db, strategy_id=strategy.id,
                subscription_id=sub.subscription_id,
            )
            # FAIL-SAFE on exits too. Closing against an UNVERIFIED position is
            # how an unwanted SHORT gets opened — the same failure design #3
            # already guards for `None`. Unknown gets the same treatment.
            if position is POSITION_UNKNOWN:
                results.append(_unknown_result(
                    sub, symbol=signal.symbol, action=signal.action,
                    side=None, cred=cred, resolved_cred=resolved_cred,
                    what="did not close anything",
                ))
                logger.warning(
                    "fanout.exit.skipped_broker_unknown",
                    signal_id=str(signal.id),
                    subscription_id=str(sub.subscription_id),
                    symbol=signal.symbol,
                )
                continue
            if position is None:
                # Design #3 guard: exiting a position that does not exist would
                # open an unwanted SHORT at the broker — skip loudly instead.
                results.append(
                    PaperExecutionResult(
                        subscription_id=sub.subscription_id,
                        subscriber_id=sub.subscriber_id,
                        symbol=signal.symbol,
                        action=signal.action,
                        side=None,
                        quantity=0,
                        paper=True,
                        broker_order_id=None,
                        avg_price=None,
                        status="skipped_no_position",
                        resolved_credential_id=resolved_cred,
                        credential_source=cred.source,
                    )
                )
                logger.warning(
                    "fanout.exit.no_position",
                    signal_id=str(signal.id),
                    strategy_id=str(strategy.id),
                    subscription_id=str(sub.subscription_id),
                    subscriber_id=str(sub.subscriber_id),
                    action_kind=action_kind,
                )
                continue

            # ── already-flat guard (design #3, quiet): a position row with
            # nothing left to close is skipped — never a 0-qty paper fill and
            # never re-opened. Distinct from ``skipped_no_position`` (no row at
            # all — the loud unwanted-short guard above).
            if int(position.remaining_quantity) <= 0:
                results.append(
                    PaperExecutionResult(
                        subscription_id=sub.subscription_id,
                        subscriber_id=sub.subscriber_id,
                        symbol=position.symbol,
                        action=signal.action,
                        side=position.side,
                        quantity=0,
                        paper=True,
                        broker_order_id=None,
                        avg_price=None,
                        status="skipped",
                        position_id=str(position.id),
                        resolved_credential_id=resolved_cred,
                        credential_source=cred.source,
                    )
                )
                logger.info(
                    "fanout.exit.already_flat",
                    signal_id=str(signal.id),
                    subscription_id=str(sub.subscription_id),
                    position_id=str(position.id),
                )
                continue

            if action_kind == "partial":
                pct = Decimal(str(payload.get("closePct") or 50))
                close_qty = int(
                    Decimal(position.remaining_quantity) * pct / Decimal("100")
                )
                close_qty = max(1, min(close_qty, position.remaining_quantity))
            else:  # exit | sl_hit → full close
                close_qty = position.remaining_quantity

            # ── AUTO vs MANUAL (design-locked). A MANUAL subscriber's copy is
            # NEVER auto-filled on an exit: emit a ``notify_only`` result naming
            # exactly what they must close (on their OWN stored symbol/qty) and
            # write NOTHING — no simulated fill, no leg, no position mutation.
            # Only AUTO subscribers reach the paper mirror-fill below.
            if str(sub.execution_mode).strip().lower() != "auto":
                notify_msg = (
                    f"Manual exit required — close {close_qty} of "
                    f"{position.symbol} ({action_kind}). Your copy is set to "
                    "MANUAL, so it was not auto-exited."
                )
                results.append(
                    PaperExecutionResult(
                        subscription_id=sub.subscription_id,
                        subscriber_id=sub.subscriber_id,
                        symbol=position.symbol,
                        action=signal.action,
                        side=position.side,
                        quantity=close_qty,
                        paper=True,
                        broker_order_id=None,
                        avg_price=None,
                        status="notify_only",
                        position_id=str(position.id),
                        resolved_credential_id=resolved_cred,
                        credential_source=cred.source,
                        notify_message=notify_msg,
                    )
                )
                logger.info(
                    "fanout.exit.notify_only",
                    signal_id=str(signal.id),
                    strategy_id=str(strategy.id),
                    subscription_id=str(sub.subscription_id),
                    subscriber_id=str(sub.subscriber_id),
                    action_kind=action_kind,
                    symbol=position.symbol,
                    close_qty=close_qty,
                    execution_mode=sub.execution_mode,
                )
                continue

            sim = _simulate_fill(signal, close_qty)  # paper — no broker (AUTO)
            order_id = str(sim.get("broker_order_id"))

            async with db.begin_nested():
                now = datetime.now(UTC)
                position.remaining_quantity -= close_qty
                entry_price = Decimal(str(position.avg_entry_price or 0))
                direction = 1 if str(position.side).lower() in ("buy", "long") else -1
                leg_pnl = (exit_price - entry_price) * close_qty * direction
                position.final_pnl = (
                    Decimal(str(position.final_pnl or 0)) + leg_pnl
                )
                if position.remaining_quantity <= 0:
                    position.status = "closed"
                    position.closed_at = now
                else:
                    position.status = "partial"

                db.add(StrategyExecution(
                    signal_id=signal.id,
                    broker_credential_id=strategy.broker_credential_id,
                    subscription_id=sub.subscription_id,
                    leg_number=1,
                    leg_role=action_kind,
                    symbol=position.symbol,       # STORED symbol
                    side="sell" if direction == 1 else "buy",
                    quantity=close_qty,
                    order_type="market",
                    price=exit_price,
                    broker_order_id=order_id,
                    broker_status="complete",
                    broker_response={
                        "paper": True,
                        "marketplace_subscription_id": str(sub.subscription_id),
                        "action_kind": action_kind,
                        "closed_qty": close_qty,
                        "exit_price": str(exit_price),
                        "leg_pnl": str(leg_pnl),
                        "source": "marketplace_fanout_exit",
                    },
                    placed_at=now,
                    completed_at=now,
                ))
                await db.flush()
            wrote_any = True

            results.append(
                PaperExecutionResult(
                    subscription_id=sub.subscription_id,
                    subscriber_id=sub.subscriber_id,
                    symbol=position.symbol,
                    action=signal.action,
                    side=position.side,
                    quantity=close_qty,
                    paper=True,
                    broker_order_id=order_id,
                    avg_price=str(exit_price),
                    status="filled",
                    position_id=str(position.id),
                    resolved_credential_id=resolved_cred,
                    credential_source=cred.source,
                )
            )
            logger.info(
                "fanout.exit.executed",
                paper=True,
                signal_id=str(signal.id),
                strategy_id=str(strategy.id),
                subscription_id=str(sub.subscription_id),
                subscriber_id=str(sub.subscriber_id),
                action_kind=action_kind,
                symbol=position.symbol,
                closed_qty=close_qty,
                position_status=position.status,
            )
        except Exception as exc:  # isolate per-subscriber failures
            results.append(
                PaperExecutionResult(
                    subscription_id=sub.subscription_id,
                    subscriber_id=sub.subscriber_id,
                    symbol=signal.symbol,
                    action=signal.action,
                    side=None,
                    quantity=0,
                    paper=True,
                    broker_order_id=None,
                    avg_price=None,
                    status="failed",
                    error=str(exc),
                )
            )
            logger.warning(
                "fanout.exit.subscriber_failed",
                signal_id=str(signal.id),
                subscription_id=str(sub.subscription_id),
                error=str(exc),
            )
            await _alert_subscriber_failure(
                signal_id=str(signal.id),
                subscription_id=str(sub.subscription_id),
                subscriber_id=str(sub.subscriber_id),
                error=str(exc),
            )

    if wrote_any:
        await db.commit()

    logger.info(
        "fanout.exit.summary",
        signal_id=str(signal.id),
        strategy_id=str(strategy.id),
        action_kind=action_kind,
        subscriber_count=len(subscribers),
        closed=sum(1 for r in results if r.status == "filled"),
        notify_only=sum(1 for r in results if r.status == "notify_only"),
        duplicate=sum(1 for r in results if r.status == "duplicate"),
        skipped=sum(1 for r in results if r.status == "skipped"),
        skipped_no_position=sum(
            1 for r in results if r.status == "skipped_no_position"),
        failed=sum(1 for r in results if r.status == "failed"),
    )
    return results


# ═══════════════════════════════════════════════════════════════════════
# FANOUT_DESIGN #2 — subscriber-inclusive reconcile LOGIC (Module B+ Part 2)
# ═══════════════════════════════════════════════════════════════════════
# The live reconciliation loop (``app.workers.reconciliation_loop``) is a
# live/sacred worker that today filters owner-only (``subscription_id IS NULL``).
# This is the STANDALONE, PURE logic that extends the drift check to
# subscribers. Wiring it INTO that loop is a SEPARATE gated step — not here.


@dataclass(frozen=True)
class ReconcileMismatch:
    """One owner↔subscriber inconsistency found by :func:`reconcile_owner_and_subscribers`.

    ``kind`` is ``"orphan"`` (subscriber open but owner flat — the sub is
    exposed alone and must be closed) or ``"gap"`` (owner open but an active
    subscriber has no mirrored position — the sub is missing its copy).
    """

    kind: str
    strategy_id: str
    subscription_id: str | None
    symbol: str | None
    detail: str


@dataclass(frozen=True)
class ReconcileReport:
    """Result of a subscriber-inclusive reconcile. ``clean`` iff no mismatch."""

    orphans: list[ReconcileMismatch]
    gaps: list[ReconcileMismatch]
    matched: int
    clean: bool


def _pos_open(obj: Any) -> bool:
    return str(getattr(obj, "status", "") or "").lower() in ("open", "partial")


def reconcile_owner_and_subscribers(
    *,
    owner_positions: Iterable[Any],
    subscriber_positions: Iterable[Any],
    active_subscriptions: Iterable[Any],
) -> ReconcileReport:
    """Detect owner↔subscriber position drift (design #2). PURE — no DB, no broker.

    * **orphan** — a subscriber position is OPEN but the owner is FLAT on that
      strategy (an exit that should have mirrored did not; the subscriber is
      exposed alone and must be closed).
    * **gap** — the owner is OPEN on a strategy but an ACTIVE subscriber has NO
      open mirrored position (an entry that should have fanned did not; the
      subscriber is missing its copy).

    Everything else that has a matching open owner is counted in ``matched``.
    ``clean`` is ``True`` iff there are no orphans and no gaps.

    Inputs are duck-typed: ``owner_positions`` / ``subscriber_positions`` on
    ``strategy_id`` / ``symbol`` / ``status`` (+ ``subscription_id`` on the
    subscriber side); ``active_subscriptions`` on ``subscription_id`` /
    ``strategy_id``. Wiring into the live/sacred reconciliation loop = later.
    """
    owner_open_by_strategy: dict[str, Any] = {}
    for p in owner_positions:
        if _pos_open(p):
            owner_open_by_strategy.setdefault(str(p.strategy_id), p)

    orphans: list[ReconcileMismatch] = []
    matched = 0
    sub_open_ids: set[str] = set()
    for p in subscriber_positions:
        if not _pos_open(p):
            continue
        sub_id = str(getattr(p, "subscription_id", "") or "")
        sub_open_ids.add(sub_id)
        strat = str(p.strategy_id)
        if strat in owner_open_by_strategy:
            matched += 1
        else:
            orphans.append(ReconcileMismatch(
                kind="orphan",
                strategy_id=strat,
                subscription_id=sub_id,
                symbol=getattr(p, "symbol", None),
                detail="subscriber position open but owner flat on this strategy",
            ))

    gaps: list[ReconcileMismatch] = []
    for sub in active_subscriptions:
        strat = str(getattr(sub, "strategy_id", "") or "")
        sub_id = str(getattr(sub, "subscription_id", "") or "")
        if strat in owner_open_by_strategy and sub_id not in sub_open_ids:
            gaps.append(ReconcileMismatch(
                kind="gap",
                strategy_id=strat,
                subscription_id=sub_id,
                symbol=getattr(owner_open_by_strategy[strat], "symbol", None),
                detail="owner open but subscriber has no mirrored position",
            ))

    clean = not orphans and not gaps
    logger.info(
        "fanout.reconcile.report",
        orphans=len(orphans),
        gaps=len(gaps),
        matched=matched,
        clean=clean,
    )
    return ReconcileReport(
        orphans=orphans, gaps=gaps, matched=matched, clean=clean)
