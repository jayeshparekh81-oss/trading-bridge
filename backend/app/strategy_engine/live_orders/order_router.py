"""Live order placement orchestrator — Phase 8B-2 Part 2.

Wires the SafetyChain (Part 1) to the existing :class:`DhanBroker` /
:class:`FyersBroker` adapters via a shared broker-factory injection
point. The flow, locked:

    1. Run :func:`run_safety_chain` — first failure short-circuits and
       emits a ``live_order_blocked`` audit event.
    2. Run a Broker-Execution-Guard slim subset (currently
       ``check_stop_loss_present``) that the SafetyChain doesn't cover.
       Failure also short-circuits and emits ``live_order_blocked``.
    3. Emit a ``live_order_attempted`` PRE event — the
       :attr:`LiveOrderResult.audit_log_id` references this event.
    4. If ``dry_run=True``: return early with
       ``order_id="DRY_RUN_SIMULATED"``.
    5. Resolve the broker via the user's active credential (the
       ``Strategy.broker_credential_id`` FK).
    6. Call ``broker.place_order`` with one-shot relogin retry on
       :class:`BrokerSessionExpiredError` (mirrors
       :func:`order_service.process_webhook_signal`'s pattern).
    7. Emit a ``live_order_attempted`` POST event with the broker
       response in metadata.
    8. Return the populated :class:`LiveOrderResult`.

Failure surface:

    * SafetyChain block → ``success=False``, ``broker_guard_passed=False``,
      ``failure_reason_hinglish`` = the blocking check's reason.
    * Broker Guard block → same shape, reason from the guard check.
    * Broker session expired and relogin failed → wrapped as a typed
      :class:`BrokerOfflineError` so the API layer can map to 503.
    * Other broker errors → propagate; API layer maps to 503 / 422
      based on the exception type.

Why this module legitimately imports broker classes:

    The SafetyChain stays free of HTTP-using imports for AST-purity;
    this orchestrator is the EXACT boundary where the HTTP-using broker
    code is allowed to land. The ``test_safety_chain`` AST-purity test
    excludes ``order_router.py`` and ``api.py`` for that reason.

Tests inject a :func:`BrokerFactory` to skip the registry lookup and
return a mocked :class:`BrokerInterface`; production passes ``None``
and the registry resolves the concrete class.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.brokers.registry import get_broker_class
from app.core.exceptions import (
    BrokerError,
    BrokerSessionExpiredError,
)
from app.core.security import decrypt_credential
from app.db.models.broker_credential import BrokerCredential
from app.db.models.strategy import Strategy
from app.schemas.broker import (
    BrokerCredentials,
    Exchange,
    OrderRequest,
    OrderResponse,
    OrderSide,
    OrderType,
    ProductType,
)
from app.strategy_engine.audit.loggers import (
    log_live_order_attempt,
)
from app.strategy_engine.broker_guard.checks import check_stop_loss_present
from app.strategy_engine.broker_guard.models import GuardCheckResult
from app.strategy_engine.live_orders.models import (
    LiveOrderRequest,
    LiveOrderResult,
)
from app.strategy_engine.live_orders.safety_chain import run_safety_chain
from app.strategy_engine.schema.strategy import StrategyJSON


class BrokerFactory(Protocol):
    """Test-injection seam — production wires the registry call below.

    The orchestrator never instantiates broker classes directly; it
    delegates here so a test can return a mock without monkey-patching
    the import machinery.
    """

    def __call__(self, credentials: BrokerCredentials) -> Any: ...


class BrokerOfflineError(RuntimeError):
    """Raised when the broker session is expired and relogin failed.

    The API layer maps this to HTTP 503. Keeping the type distinct from
    :class:`BrokerSessionExpiredError` lets the orchestrator's caller
    distinguish "transient — retry later" from "the orchestrator
    already burned its one-shot retry".
    """


class StrategyMissingBrokerCredentialError(RuntimeError):
    """The strategy row has no ``broker_credential_id`` FK.

    The SafetyChain's ``check_broker_connection`` only verifies that
    the user has at least one active credential, not that the
    *strategy* is bound to one. Catching this here surfaces the gap
    as a 422 instead of an obscure FK lookup failure.
    """


# ─── Public entry point ───────────────────────────────────────────────


async def place_live_order(
    request: LiveOrderRequest,
    *,
    user_id: uuid.UUID,
    db_session: AsyncSession,
    broker_factory: BrokerFactory | None = None,
) -> LiveOrderResult:
    """Run the full SafetyChain + Broker Guard + broker placement flow.

    Args:
        request: Validated body. The endpoint wraps Pydantic on the
            way in; callers that hold an already-validated request
            (e.g. tests) can pass it through.
        user_id: Acting user. Ownership of ``request.strategy_id`` is
            verified inside this call — the caller does not need to
            check separately.
        db_session: Open :class:`AsyncSession`. The orchestrator uses
            it for read-only queries (strategy, broker credential) and
            does not commit.
        broker_factory: Test seam. Production code passes ``None`` and
            the registry resolves the concrete broker class.

    Returns:
        :class:`LiveOrderResult` populated with the SafetyChain
        verdict, broker guard pass flag, and the broker response (or
        ``None`` for blocked / dry-run paths).
    """
    placed_at = datetime.now(UTC)

    # ── Ownership check ─────────────────────────────────────────────
    strategy = await _load_owned_strategy(
        db_session, strategy_id=request.strategy_id, user_id=user_id
    )

    # ── 1. SafetyChain ──────────────────────────────────────────────
    chain_result = await run_safety_chain(
        user_id=user_id,
        strategy_id=request.strategy_id,
        db_session=db_session,
    )
    if not chain_result.all_passed:
        return _emit_blocked_and_build_result(
            user_id=user_id,
            strategy=strategy,
            request=request,
            chain_result=chain_result,
            broker_guard_passed=False,
            failure_reason_hinglish=(
                chain_result.blocking_check.reason_hinglish
                if chain_result.blocking_check
                else "Safety chain blocked the order."
            ),
            blocking_reason=(
                chain_result.blocking_check.check_name
                if chain_result.blocking_check
                else "unknown"
            ),
            placed_at=placed_at,
        )

    # ── 2. Broker Guard slim subset ─────────────────────────────────
    guard_result = _evaluate_broker_guard_subset(strategy=strategy)
    if not guard_result.passed:
        return _emit_blocked_and_build_result(
            user_id=user_id,
            strategy=strategy,
            request=request,
            chain_result=chain_result,
            broker_guard_passed=False,
            failure_reason_hinglish=guard_result.message,
            blocking_reason=guard_result.check_name,
            placed_at=placed_at,
        )

    # ── 3. PRE-order audit event ────────────────────────────────────
    pre_event = log_live_order_attempt(
        strategy_id=request.strategy_id,
        user_id=user_id,
        allowed=True,
        blocking_reasons=None,
    )

    # ── 4. Dry-run short-circuit ────────────────────────────────────
    # Only the PRE event is emitted — the absence of a POST event
    # (and the explicit ``order_id="DRY_RUN_SIMULATED"`` /
    # ``is_dry_run=True`` on the result) is how the dry-run path is
    # distinguishable in the audit trail without adding a new
    # ``live_order_dry_run`` event_type to the closed Phase 11 enum.
    if request.dry_run:
        return LiveOrderResult(
            success=True,
            order_id="DRY_RUN_SIMULATED",
            safety_chain_result=chain_result,
            broker_guard_passed=True,
            broker_response=None,
            audit_log_id=pre_event.event_id,
            placed_at=placed_at,
            failure_reason_hinglish=None,
            is_dry_run=True,
        )

    # ── 5. Resolve broker ───────────────────────────────────────────
    if strategy.broker_credential_id is None:
        raise StrategyMissingBrokerCredentialError(
            f"Strategy {strategy.id} has no broker_credential_id linked."
        )
    cred_row = await _load_active_credential(
        db_session,
        credential_id=strategy.broker_credential_id,
        user_id=user_id,
    )
    creds = _build_broker_credentials(cred_row, user_id)
    broker = (
        broker_factory(creds)
        if broker_factory is not None
        else get_broker_class(creds.broker)(creds)
    )

    # ── 6. Place order with one-shot relogin retry ─────────────────
    order_request = _build_order_request(request)
    try:
        broker_response: OrderResponse = await _place_with_retry(
            broker=broker, order_request=order_request
        )
    except BrokerOfflineError:
        # Re-raise so the API layer maps to 503; record the failure
        # in the audit log first so the trail is complete.
        log_live_order_attempt(
            strategy_id=request.strategy_id,
            user_id=user_id,
            allowed=False,
            blocking_reasons=["broker_offline"],
        )
        raise

    # ── 7. POST-order audit event ───────────────────────────────────
    log_live_order_attempt(
        strategy_id=request.strategy_id,
        user_id=user_id,
        allowed=True,
        blocking_reasons=None,
    )

    # ── 8. Build result ─────────────────────────────────────────────
    return LiveOrderResult(
        success=True,
        order_id=broker_response.broker_order_id,
        safety_chain_result=chain_result,
        broker_guard_passed=True,
        broker_response={
            "broker_order_id": broker_response.broker_order_id,
            "status": broker_response.status.value,
            "message": broker_response.message,
            "raw": broker_response.raw_response,
        },
        audit_log_id=pre_event.event_id,
        placed_at=placed_at,
        failure_reason_hinglish=None,
        is_dry_run=False,
    )


# ─── Internals ────────────────────────────────────────────────────────


async def _load_owned_strategy(
    db: AsyncSession,
    *,
    strategy_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Strategy:
    """Fetch a strategy scoped to ``user_id``. Raises if missing/cross-user.

    Mirrors the existing CRUD / backtest endpoint pattern: 404 covers
    both "doesn't exist" and "not yours" so the endpoint can't be used
    as an enumeration oracle. We raise a generic ``LookupError`` here
    and let the API layer translate to the HTTP code; the orchestrator
    is HTTP-agnostic.
    """
    stmt = select(Strategy).where(
        Strategy.id == strategy_id, Strategy.user_id == user_id
    )
    strategy = (await db.execute(stmt)).scalar_one_or_none()
    if strategy is None:
        raise LookupError(
            f"Strategy {strategy_id} not found for user {user_id}."
        )
    return strategy


async def _load_active_credential(
    db: AsyncSession,
    *,
    credential_id: uuid.UUID,
    user_id: uuid.UUID,
) -> BrokerCredential:
    """Fetch the broker credential for the strategy, scoped to user."""
    stmt = select(BrokerCredential).where(
        BrokerCredential.id == credential_id,
        BrokerCredential.user_id == user_id,
        BrokerCredential.is_active.is_(True),
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise StrategyMissingBrokerCredentialError(
            f"Broker credential {credential_id} not active for user {user_id}."
        )
    return row


def _build_broker_credentials(
    row: BrokerCredential, user_id: uuid.UUID
) -> BrokerCredentials:
    """Decrypt the persisted columns into a :class:`BrokerCredentials`."""
    return BrokerCredentials(
        broker=row.broker_name,
        user_id=str(user_id),
        client_id=decrypt_credential(row.client_id_enc),
        api_key=decrypt_credential(row.api_key_enc),
        api_secret=decrypt_credential(row.api_secret_enc),
        access_token=(
            decrypt_credential(row.access_token_enc)
            if row.access_token_enc
            else None
        ),
        refresh_token=(
            decrypt_credential(row.refresh_token_enc)
            if row.refresh_token_enc
            else None
        ),
        token_expires_at=row.token_expires_at,
    )


def _evaluate_broker_guard_subset(
    *, strategy: Strategy
) -> GuardCheckResult:
    """Run the slim subset of Broker-Execution-Guard checks the
    SafetyChain doesn't already cover.

    The full :func:`evaluate_broker_guard` requires a full backtest +
    reliability + truth + paper-readiness report bundle that we don't
    re-run on the order path (the cached scores cover the trust/truth
    gate). The unique contribution is :func:`check_stop_loss_present`
    — a pure check that reads the strategy DSL only.

    When the strategy has no DSL (legacy row), the check fails closed:
    we cannot verify a stop-loss and the safe default for live trading
    is to block.
    """
    if not strategy.strategy_json:
        return GuardCheckResult(
            check_name="stop_loss_present",
            passed=False,
            severity="blocking",
            message=(
                "Strategy has no DSL — stop loss verify nahi ho saka. "
                "Phase 5 builder se strategy recreate karo."
            ),
        )
    try:
        dsl = StrategyJSON.model_validate(strategy.strategy_json)
    except Exception:
        return GuardCheckResult(
            check_name="stop_loss_present",
            passed=False,
            severity="blocking",
            message=(
                "Strategy DSL invalid — stop loss verify nahi ho saka. "
                "Strategy ko recreate karo."
            ),
        )
    return check_stop_loss_present(dsl)


_SIDE_FROM_LITERAL: dict[str, OrderSide] = {
    "BUY": OrderSide.BUY,
    "SELL": OrderSide.SELL,
}
_EXCHANGE_FROM_LITERAL: dict[str, Exchange] = {
    "NSE": Exchange.NSE,
    "BSE": Exchange.BSE,
    "NFO": Exchange.NFO,
    "BFO": Exchange.BFO,
    "MCX": Exchange.MCX,
    "CDS": Exchange.CDS,
}
_PRODUCT_FROM_LITERAL: dict[str, ProductType] = {
    "INTRADAY": ProductType.INTRADAY,
    "DELIVERY": ProductType.DELIVERY,
    "MARGIN": ProductType.MARGIN,
}


def _build_order_request(
    request: LiveOrderRequest,
) -> OrderRequest:
    """Translate the API-boundary request into the broker contract."""
    order_type = OrderType.LIMIT if request.price is not None else OrderType.MARKET
    return OrderRequest(
        symbol=request.symbol,
        exchange=_EXCHANGE_FROM_LITERAL[request.exchange],
        side=_SIDE_FROM_LITERAL[request.side],
        quantity=request.quantity,
        order_type=order_type,
        product_type=_PRODUCT_FROM_LITERAL[request.product_type],
        price=Decimal(str(request.price)) if request.price is not None else None,
        tag="live-orders",
    )


async def _place_with_retry(
    *,
    broker: Any,
    order_request: OrderRequest,
) -> OrderResponse:
    """Issue the broker call with one-shot relogin on session expiry.

    Mirrors the proven pattern in
    :func:`order_service.process_webhook_signal`: on the first
    :class:`BrokerSessionExpiredError`, force a ``broker.login()`` and
    replay the place_order call exactly once. A second expiry surfaces
    as :class:`BrokerOfflineError` so the API maps it to 503.
    """
    try:
        return await broker.place_order(order_request)  # type: ignore[no-any-return]
    except BrokerSessionExpiredError:
        try:
            await broker.login()
            return await broker.place_order(order_request)  # type: ignore[no-any-return]
        except BrokerError as exc:
            raise BrokerOfflineError(
                "Broker session expired and relogin failed."
            ) from exc


def _emit_blocked_and_build_result(
    *,
    user_id: uuid.UUID,
    strategy: Strategy,
    request: LiveOrderRequest,
    chain_result: Any,
    broker_guard_passed: bool,
    failure_reason_hinglish: str,
    blocking_reason: str,
    placed_at: datetime,
) -> LiveOrderResult:
    """Common path for both SafetyChain and Broker-Guard blocks."""
    _ = strategy  # parameter kept for future audit metadata
    blocked_event = log_live_order_attempt(
        strategy_id=request.strategy_id,
        user_id=user_id,
        allowed=False,
        blocking_reasons=[blocking_reason],
    )
    return LiveOrderResult(
        success=False,
        order_id=None,
        safety_chain_result=chain_result,
        broker_guard_passed=broker_guard_passed,
        broker_response=None,
        audit_log_id=blocked_event.event_id,
        placed_at=placed_at,
        failure_reason_hinglish=failure_reason_hinglish,
        is_dry_run=request.dry_run,
    )


__all__ = [
    "BrokerFactory",
    "BrokerOfflineError",
    "StrategyMissingBrokerCredentialError",
    "place_live_order",
]
