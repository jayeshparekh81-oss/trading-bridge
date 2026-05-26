"""Strategy-engine webhook receiver — TradingView → AI gate → executor.

Distinct from the legacy :mod:`app.api.webhook` endpoint at
``POST /api/webhook/{token}`` which fires a single broker order
synchronously. This new endpoint at ``POST /api/webhook/strategy/{token}``
runs the strategy engine pipeline:

    1. Token lookup (reuse the existing webhook_tokens infra).
    2. HMAC verification — header X-Signature OR ``signature`` field in
       the JSON body. TradingView free tier can't always send custom
       headers, so the in-body fallback keeps the door open.
    3. Time-of-day guard — outside 09:15-15:25 IST, reject with 403.
    4. Quantity ceiling — reject anything > 4 lots.
    5. Persist a :class:`StrategySignal` row with status='received'.
    6. Dispatch :func:`app.tasks.signal_execution.dispatch_signal` —
       pushes the signal_id onto the Celery (Redis-backed) queue.
    7. Return 202 Accepted with the signal_id immediately.

Bug #2 fix (incident 2026-05-20): TradingView marks delivery
"failed — timed out" at ~5 s. Before this refactor the full
pipeline (AI → broker HTTP → Telegram) ran inside the request
handler, regularly exceeding TV's timeout and triggering retries.
The fast-path handler now finishes in <200 ms; heavy work is
owned by ``app.tasks.signal_execution.execute_signal_async``.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
from datetime import UTC, datetime, time
from functools import lru_cache
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from pydantic import ValidationError

from app.api.webhook import _resolve_webhook_token
from app.core import redis_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import verify_hmac_signature
from app.db.models.strategy import Strategy
from app.db.models.strategy_signal import StrategySignal
from app.db.models.user import User
from app.db.session import get_session
from app.schemas.strategy_webhook import (
    PositionSide,
    StrategyAction,
    StrategyWebhookPayload,
)
from app.services.futures_resolver import resolve_or_passthrough
from app.services.kill_switch_service import kill_switch_service
from app.services.pine_mapper import (
    PineMappingError,
    is_pine_payload,
    map_to_tradetri_payload,
)
from app.services.position_lookup import find_open_position_by_strategy
from app.tasks.signal_execution import (
    ACTION_ENTRY,
    ACTION_EXIT,
    ACTION_PARTIAL,
    ACTION_SL_HIT,
    dispatch_signal,
)

logger = get_logger("app.api.strategy_webhook")

router = APIRouter(prefix="/api/webhook/strategy", tags=["strategy-webhook"])

#: Sanity ceiling on the webhook's `quantity` field, which carries the
#: total **contract count** the broker should fill (NOT lot count). 10000
#: covers any reasonable per-signal size — typical BSE Ltd. swing is
#: 750 (2 lots × 375) — while still rejecting obvious typos. The
#: lot-multiple + even-lot business rules are enforced in the executor
#: where the broker's scrip master has the per-symbol lot_size.
QUANTITY_CEILING_CONTRACTS = 10000

#: IST trading window. Outside this we reject signals to avoid accidental
#: overnight orders. The AI validator is a second-line defence.
_IST = ZoneInfo("Asia/Kolkata")
_MARKET_OPEN = time(9, 15)
_MARKET_CLOSE = time(15, 25)

#: Header name TradingView sends. We also accept ``signature`` inside the JSON body.
HMAC_HEADER = "X-Signature"

#: TTL for idempotency slots. Mirrors :mod:`app.api.webhook` — TradingView
#: retries the same alert inside ~30 s if our endpoint times out, so 60 s
#: covers the retry window without occupying Redis any longer than needed.
IDEMPOTENCY_TTL_SECONDS = 60

#: Webhook rate limit — fixed-window counter, per user (not per token), so
#: a customer with multiple tokens shares one bucket. Mirrors
#: :mod:`app.api.webhook` exactly: 60 requests per 60 s.
RATE_LIMIT_REQUESTS = 60
RATE_LIMIT_WINDOW_SECONDS = 60

#: Action vocabulary post-direct-exit refactor.
#:
#: Internal canonical actions: ENTRY (open new), PARTIAL (close
#: closePct%), EXIT (Pine clean exit), SL_HIT (Pine stop loss).
#: BUY/SELL kept as legacy aliases for ENTRY — handler logs an INFO when
#: an alias is used so callers can be migrated off them.
#:
#: Pine mapper output uses these canonical names too; the OLD
#: PARTIAL_LONG / PARTIAL_SHORT vocabulary is retired.
_ENTRY_ACTIONS: frozenset[str] = frozenset({"ENTRY", "BUY", "SELL"})
_DIRECT_EXIT_ACTIONS: frozenset[str] = frozenset({"PARTIAL", "EXIT", "SL_HIT"})
_SUPPORTED_ACTIONS: frozenset[str] = _ENTRY_ACTIONS | _DIRECT_EXIT_ACTIONS



@router.post(
    "/{webhook_token}",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Malformed JSON or quantity > ceiling"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Invalid HMAC signature"},
        status.HTTP_403_FORBIDDEN: {
            "description": "Kill switch tripped or outside market hours",
        },
        status.HTTP_404_NOT_FOUND: {"description": "Unknown webhook token"},
        status.HTTP_409_CONFLICT: {"description": "Duplicate signal"},
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Rate limit exceeded"},
    },
)
async def receive_strategy_signal(
    request: Request,
    webhook_token: str = Path(..., min_length=16, max_length=128),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Accept a TradingView strategy alert and queue it for AI validation."""
    raw_body = await request.body()

    # 1. Token lookup — reuse legacy webhook resolver (Redis cache + DB fallback)
    token_info = await _resolve_webhook_token(session, webhook_token)
    if token_info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown webhook token.",
        )
    user_id: UUID = token_info["user_id"]
    hmac_secret: str = token_info["hmac_secret"]
    token_id: UUID = token_info["token_id"]

    # 2. Rate limit — fixed-window counter, 60/min per user. Mirrors the
    #    legacy /api/webhook receiver: rejects spam BEFORE the CPU-heavy
    #    HMAC verify, since a single Redis INCR is cheaper than sha256.
    allowed = await redis_client.rate_limit_check(
        key=f"webhook:{user_id}",
        max_requests=RATE_LIMIT_REQUESTS,
        window_seconds=RATE_LIMIT_WINDOW_SECONDS,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Webhook rate limit exceeded.",
        )

    # 3. Parse JSON body — needed before HMAC verify because the
    #    in-body signature must be stripped before signing.
    try:
        payload = json.loads(raw_body or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON body: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Body must be a JSON object.",
        )

    # 4. HMAC verify — only when explicitly required by config.
    #    Default (``webhook_require_hmac=False``): the 43-char URL-token
    #    secret in the path is sufficient auth — matches industry-standard
    #    practice (TradersPost, Algogene, iNakaTrader). All other safety
    #    gates (rate limit above, idempotency / kill switch / user-active /
    #    max-trades / time-of-day below) still run.
    #
    #    When ``webhook_require_hmac=True`` (legacy behaviour): require
    #    HMAC signature, with a TradingView IP allowlist bypass for TV's
    #    free tier (which cannot sign webhooks). Spoofing-resistance: the
    #    middleware-resolved client IP only honours X-Forwarded-For when
    #    the immediate peer is a trusted proxy (configured CIDR).
    if get_settings().webhook_require_hmac:
        client_ip = _resolve_client_ip(request)
        if _is_trusted_tradingview_ip(client_ip):
            logger.info(
                "strategy_webhook.tradingview_ip_bypass",
                client_ip=client_ip,
                user_id=str(user_id),
            )
            # Strip a stray ``signature`` field if present so it doesn't
            # bleed into idempotency hashing or business-logic reads.
            payload.pop("signature", None)
        else:
            signature_header = request.headers.get(HMAC_HEADER, "")
            body_signature = str(payload.pop("signature", ""))

            if signature_header:
                if not verify_hmac_signature(raw_body, signature_header, hmac_secret):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid HMAC signature (header).",
                    )
            elif body_signature:
                # Re-sign the body without the signature key — must match
                canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
                if not verify_hmac_signature(canonical, body_signature, hmac_secret):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid HMAC signature (body).",
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=(
                        "Missing HMAC signature. Send X-Signature header OR include "
                        "a 'signature' field in the JSON body."
                    ),
                )
    else:
        # URL-token-only mode: strip stray ``signature`` field so it doesn't
        # bleed into idempotency hashing or business-logic reads.
        payload.pop("signature", None)

    # 5. Idempotency claim — Redis SET NX, 60 s TTL. Mirrors the legacy
    #    /api/webhook receiver: dedupe BEFORE business-logic gates so a
    #    TradingView retry sent at 15:25:30 IST is silently absorbed
    #    rather than confusingly rejected as "outside hours".
    signal_hash = _compute_strategy_signal_hash(user_id, payload, raw_body)
    claimed = await redis_client.set_idempotency_key(
        signal_hash, ttl_seconds=IDEMPOTENCY_TTL_SECONDS
    )
    if not claimed:
        logger.info(
            "strategy_webhook.duplicate_suppressed",
            signal_hash_prefix=signal_hash[:32],
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "duplicate",
                "message": "duplicate signal suppressed",
            },
        )

    # 6. Kill switch — operator emergency stop. Per-user Redis flag.
    #    Blocks both live AND paper trades; bypassing in paper mode would
    #    defeat the purpose of an emergency stop. Mirrors legacy
    #    /api/webhook ordering (kill-switch immediately after idempotency).
    kill_status = await redis_client.get_kill_switch_status(user_id)
    if kill_status == redis_client.KILL_SWITCH_TRIPPED:
        logger.info(
            "strategy_webhook.kill_switch_tripped", user_id=str(user_id)
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kill switch is TRIPPED — trading paused.",
        )

    # 7. User-active check (Gate B) — disabled accounts cannot trade.
    #    Single PK select on the request session. The StaticPool fixture
    #    + position-loop disable (Task #5 conftest) make the seeded row
    #    visible here under TestClient's cross-loop access pattern.
    user_row = await session.get(User, user_id)
    if user_row is None or not user_row.is_active:
        logger.info("strategy_webhook.user_inactive", user_id=str(user_id))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    # 8. Max-daily-trades gate (Gate C) — DB-backed config + Redis counter.
    #    Returns ``(True, 0, 0)`` if the user has no KillSwitchConfig row,
    #    so untouched users default to "no cap" — explicit thresholds are
    #    opt-in via :class:`KillSwitchConfig`.
    within_cap, trades_today, trades_limit = (
        await kill_switch_service.check_max_daily_trades(user_id, session)
    )
    if not within_cap:
        logger.info(
            "strategy_webhook.max_daily_trades",
            user_id=str(user_id),
            trades_today=trades_today,
            trades_limit=trades_limit,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Max daily trades reached ({trades_today}/{trades_limit}).",
        )

    # 9. Resolve strategy early — Pine mapping needs allowed_symbols for
    #    the symbol fallback, AND the per-strategy ``is_paper`` flag
    #    (migration 027) drives the time-of-day bypass below. Native
    #    payloads don't strictly need the row here either, but the lookup
    #    is a single PK select so the order is harmless.
    strategy = await _resolve_strategy(
        session, user_id=user_id, webhook_token_id=token_id
    )
    if strategy is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No active strategy is bound to this webhook token. Create "
                "one (with broker_credential_id) before sending alerts."
            ),
        )
    strategy_id: UUID = strategy.id

    # 10. Time-of-day guard (bypassed when THIS strategy is in paper mode
    #     for off-hours testing). Uses the per-strategy override so a
    #     LIVE strategy still respects market hours even when the global
    #     flag is paper, and vice versa.
    from app.services.paper_mode_resolver import resolve_paper_mode

    effective_paper_mode = resolve_paper_mode(strategy)
    if effective_paper_mode:
        logger.info(
            "time_of_day_check_bypassed_paper_mode",
            mode="paper",
            strategy_id=str(strategy_id),
        )
    else:
        now_ist = datetime.now(_IST).time()
        if not (_MARKET_OPEN <= now_ist <= _MARKET_CLOSE):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Outside market hours (09:15-15:25 IST). Local now: {now_ist}."
                ),
            )

    # 11. Pine Script v4.8.1 detection — translate to native shape so the
    #    rest of the pipeline keeps a single contract. Native payloads
    #    pass through unchanged.
    if is_pine_payload(payload):
        try:
            payload = map_to_tradetri_payload(payload, strategy)
        except PineMappingError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pine payload mapping failed: {exc}",
            ) from exc

    # 11b. Symbol normalization — delegate to the date-driven
    #      :mod:`app.services.futures_resolver`. TradingView ships
    #      "continuous" tickers (NSE:BSE, BSE1!) but Dhan's order API
    #      wants the month-stamped contract (BSE-MAY2026-FUT), which
    #      changes at every NSE F&O monthly expiry (last Thursday,
    #      15:30 IST). The resolver enumerates live -FUT rows from the
    #      Dhan scrip master, computes their expiry from the symbol's
    #      month token, and picks the active contract — no hardcoded
    #      calendar, no manual monthly rollover. Unknown tickers and
    #      already-canonical symbols pass through unchanged. Applied
    #      AFTER Pine mapping so both native + Pine payloads benefit,
    #      and BEFORE Pydantic validation so the persisted signal row
    #      carries the canonical ticker.
    raw_symbol = payload.get("symbol")
    raw_action = str(payload.get("action") or "").strip().upper()
    if raw_action in _DIRECT_EXIT_ACTIONS:
        # Exit-class (PARTIAL/EXIT/SL_HIT): NEVER re-resolve the symbol. The
        # resolver rolls to the next month in the 14:30-15:30 IST expiry-day
        # window, which would no longer match the open (current-month) position
        # — the symbol-keyed exit lookup would miss and the exit would silently
        # no-op, leaving the position to auto-settle. Pin to the held position's
        # stored entry-time symbol instead. The ENTRY path below is unchanged.
        open_position = await find_open_position_by_strategy(
            session, strategy_id=strategy_id, side=payload.get("side")
        )
        if open_position is not None:
            if isinstance(raw_symbol, str) and open_position.symbol != raw_symbol:
                logger.info(
                    "strategy_webhook.exit_symbol_pinned_to_position",
                    action=raw_action,
                    original=raw_symbol,
                    stored=open_position.symbol,
                )
            payload["symbol"] = open_position.symbol
        else:
            # Loud, NOT silent. A genuine no-open-position exit (duplicate /
            # already-closed) — leave the symbol un-re-resolved; the downstream
            # direct-exit handler returns a benign 'ignored'. Deliberately NOT an
            # HTTP error, to avoid TradingView retry storms on benign repeats.
            logger.warning(
                "strategy_webhook.exit_no_open_position",
                strategy_id=str(strategy_id),
                action=raw_action,
                symbol=raw_symbol,
                side=payload.get("side"),
            )
    elif isinstance(raw_symbol, str):
        normalized = await resolve_or_passthrough(raw_symbol)
        if normalized != raw_symbol:
            logger.info(
                "strategy_webhook.symbol_normalized",
                original=raw_symbol,
                normalized=normalized,
            )
            payload["symbol"] = normalized
            logger.info(
                "strategy_webhook.symbol_resolution_attempt_expected",
                symbol=normalized,
                expected_broker_lookup="dhan_scrip_master",
            )

    # 12. Pydantic validation — fields, types, per-action required keys.
    #     Replaces the prior dict-based extraction. Pydantic raises a
    #     ValidationError with a per-field error list; we re-package as a
    #     400 with a stable "code" so callers can detect specific
    #     misconfigs (missing closePct, etc.).
    try:
        validated = StrategyWebhookPayload.model_validate(payload)
    except ValidationError as exc:
        # Pydantic's full error dict can contain unserializable objects
        # (e.g. the original ValueError from a model_validator); strip to
        # JSON-safe primitives.
        safe_errors = [
            {
                "loc": [str(part) for part in err.get("loc", ())],
                "msg": str(err.get("msg", "")),
                "type": str(err.get("type", "")),
            }
            for err in exc.errors()
        ]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_payload", "errors": safe_errors},
        ) from exc

    # 12a. ENTRY-family ceiling check — only enforced for entries since
    #     PARTIAL/EXIT/SL_HIT derive their own quantity from position state.
    if validated.is_entry() and validated.quantity is not None:
        if validated.quantity > QUANTITY_CEILING_CONTRACTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "quantity_exceeds_ceiling",
                    "message": (
                        f"Quantity {validated.quantity} contracts exceeds "
                        f"ceiling {QUANTITY_CEILING_CONTRACTS}."
                    ),
                },
            )

    # 12b. Alias normalization — log when a legacy BUY/SELL is used so we
    #     can migrate callers off the alias. Persist with the canonical
    #     ENTRY action name; resolve side from the alias.
    canonical_action = validated.action
    payload_for_persist = dict(payload)
    if validated.action in (StrategyAction.BUY, StrategyAction.SELL):
        canonical_action = StrategyAction.ENTRY
        side = (
            PositionSide.LONG
            if validated.action == StrategyAction.BUY
            else PositionSide.SHORT
        )
        payload_for_persist["side"] = side.value
        logger.info(
            "strategy_webhook.legacy_alias_used",
            alias=validated.action.value,
            normalized_to=canonical_action.value,
            side=side.value,
        )

    # 13. Persist signal row — use the canonical action so
    #     strategy_signals.action carries one of {ENTRY, PARTIAL, EXIT,
    #     SL_HIT}. The raw payload preserves whatever the caller sent.
    quantity_to_persist = (
        validated.quantity if validated.is_entry() else None
    )
    signal = StrategySignal(
        user_id=user_id,
        strategy_id=strategy_id,
        raw_payload=payload_for_persist,
        symbol=validated.symbol,
        action=canonical_action.value,
        quantity=quantity_to_persist,
        order_type=validated.order_type or "market",
        status="received",
        received_at=datetime.now(UTC),
    )
    session.add(signal)
    await session.commit()
    await session.refresh(signal)

    # ───────────────────────────────────────────────────────────────────
    # Market Strength Shield — release pass (W3.4 port). Default OFF.
    #
    # RULE 1: only resumes Pine's pre-existing held EXIT — no autonomous
    # new broker action. RULE 2: webhook-driven, fires on closed-bar
    # arrival of any subsequent Pine signal.
    #
    # Runs FIRST (before the action-specific dispatch) so a matured
    # held EXIT for this strategy is dispatched on this bar regardless
    # of what the current signal's action is.
    # ───────────────────────────────────────────────────────────────────
    from app.services import market_shield_service as _mshield

    exit_held_by_shield = False
    exit_skipped_prior_hold = False

    if _mshield.is_enabled():
        try:
            current_price_for_release: float | None = None
            try:
                current_price_for_release = float(
                    payload_for_persist.get("price") or 0
                ) or None
            except (TypeError, ValueError):
                current_price_for_release = None

            release_outcome = await _mshield.try_release(
                strategy_id=strategy_id,
                current_price=current_price_for_release,
            )
            if release_outcome.released and release_outcome.signal_id:
                logger.info(
                    "market_shield.released",
                    held_signal_id=release_outcome.signal_id,
                    reason=release_outcome.reason,
                    strategy_id=str(strategy_id),
                )
                dispatch_signal(release_outcome.signal_id, ACTION_EXIT)
                from app.services import telegram_alerts as _alerts
                if release_outcome.reason == "atr_override":
                    await _alerts.send_alert(
                        _alerts.AlertLevel.WARNING,
                        "⚠️ *Market Shield* — ATR override, releasing held EXIT\n"
                        f"Strategy: `{strategy_id}`\n"
                        f"Held signal: `{release_outcome.signal_id}`",
                    )
                else:
                    await _alerts.send_alert(
                        _alerts.AlertLevel.INFO,
                        "⏱️ *Market Shield* — 2-bar timeout, releasing held EXIT\n"
                        f"Strategy: `{strategy_id}`\n"
                        f"Held signal: `{release_outcome.signal_id}`",
                    )
        except Exception as exc:  # noqa: BLE001 — never fail the live signal
            logger.warning(
                "market_shield.release_failed",
                strategy_id=str(strategy_id),
                error=str(exc),
            )

    # ───────────────────────────────────────────────────────────────────
    # Market Strength Shield — hold pass for EXIT only.
    # PARTIAL / SL_HIT / ENTRY are passthrough by design.
    # ───────────────────────────────────────────────────────────────────
    if (
        canonical_action == StrategyAction.EXIT
        and _mshield.is_enabled()
    ):
        try:
            if await _mshield.has_active_hold(strategy_id):
                exit_skipped_prior_hold = True
                signal.status = "ignored"
                signal.notes = (
                    "market_shield: prior EXIT already held for this strategy"
                )
                await session.commit()
                logger.info(
                    "market_shield.exit_skipped_prior_hold",
                    signal_id=str(signal.id),
                    strategy_id=str(strategy_id),
                )
            else:
                hold_decision = await _mshield.maybe_hold_exit(
                    session,
                    strategy_id=strategy_id,
                    signal=signal,
                )
                if hold_decision.held:
                    exit_held_by_shield = True
                    signal.status = "held"
                    signal.notes = f"market_shield_held: {hold_decision.reason}"
                    await session.commit()
                    logger.info(
                        "market_shield.exit_held",
                        signal_id=str(signal.id),
                        strategy_id=str(strategy_id),
                        reason=hold_decision.reason,
                        release_at=hold_decision.release_at_iso,
                    )
                    from app.services import telegram_alerts as _alerts
                    breadth = hold_decision.breadth
                    breadth_str = (
                        f"{breadth.bullish_count}/4"
                        if breadth is not None
                        else "n/a"
                    )
                    bullish_names = (
                        ", ".join(breadth.bullish_names)
                        if breadth is not None
                        else "—"
                    )
                    await _alerts.send_alert(
                        _alerts.AlertLevel.INFO,
                        "🛡️ *Market Shield* — holding EXIT (max 2 bars)\n"
                        f"Strategy: `{strategy_id}`\n"
                        f"Signal: `{signal.id}`\n"
                        f"Breadth: `{breadth_str}` ({bullish_names})\n"
                        f"Release by: `{hold_decision.release_at_iso}`",
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "market_shield.hold_failed",
                signal_id=str(signal.id),
                strategy_id=str(strategy_id),
                error=str(exc),
            )

    # 14. Dispatch — push the persisted signal to the Celery worker via
    #     :func:`app.tasks.signal_execution.dispatch_signal`. ENTRY runs
    #     the AI-validated executor; direct-exit actions skip AI (Pine
    #     has already decided) and route through the direct_exit handler.
    #     The dispatch is a single Redis LPUSH (Celery broker) — the
    #     webhook returns 202 in well under TradingView's ~5 s timeout.
    if canonical_action == StrategyAction.ENTRY:
        dispatch_signal(str(signal.id), ACTION_ENTRY)
        queued = True
    elif canonical_action == StrategyAction.PARTIAL:
        dispatch_signal(str(signal.id), ACTION_PARTIAL)
        queued = True
    elif canonical_action == StrategyAction.EXIT:
        if exit_held_by_shield or exit_skipped_prior_hold:
            queued = False
        else:
            dispatch_signal(str(signal.id), ACTION_EXIT)
            queued = True
    elif canonical_action == StrategyAction.SL_HIT:
        dispatch_signal(str(signal.id), ACTION_SL_HIT)
        queued = True
    else:
        # Pydantic should have prevented this — defensive belt-and-braces.
        queued = False

    logger.info(
        "strategy_webhook.signal_received",
        signal_id=str(signal.id),
        symbol=validated.symbol,
        action=canonical_action.value,
        quantity=quantity_to_persist,
        side=(
            payload_for_persist.get("side")
            if validated.action != StrategyAction.PARTIAL
            else f"{payload_for_persist.get('side')} closePct={validated.close_pct}"
        ),
    )
    return {
        "status": "accepted",
        "signal_id": str(signal.id),
        "strategy_id": str(strategy_id),
        "queued_for_processing": queued,
    }


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


async def _resolve_strategy_id(
    session: AsyncSession, *, user_id: UUID, webhook_token_id: UUID
) -> UUID | None:
    stmt = select(Strategy.id).where(
        Strategy.user_id == user_id,
        Strategy.webhook_token_id == webhook_token_id,
        Strategy.is_active.is_(True),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _resolve_strategy(
    session: AsyncSession, *, user_id: UUID, webhook_token_id: UUID
) -> Strategy | None:
    """Full Strategy row — Pine mapping needs ``allowed_symbols``."""
    stmt = select(Strategy).where(
        Strategy.user_id == user_id,
        Strategy.webhook_token_id == webhook_token_id,
        Strategy.is_active.is_(True),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _resolve_client_ip(request: Request) -> str | None:
    """Resolve the originating client IP for the TV-bypass check.

    Prefers ``request.state.client_ip`` (set by
    :class:`app.middleware.security.TrustedProxyMiddleware` after honouring
    ``X-Forwarded-For`` when the immediate peer is in
    ``settings.trusted_proxy_ips``). Falls back to the immediate peer when
    the middleware didn't run (direct internal calls, some test paths).

    Spoofing-resistance is owned by the middleware: it only trusts XFF
    when the peer is in the configured trusted-proxy CIDR. Untrusted
    peers always get their own IP back regardless of XFF.
    """
    state_ip = getattr(request.state, "client_ip", None)
    if state_ip:
        return state_ip
    return request.client.host if request.client else None


@lru_cache(maxsize=4)
def _parse_tv_networks(
    entries: tuple[str, ...],
) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    """Parse TradingView trusted-IP entries (bare IPs OR CIDRs) into networks.

    Cached on the tuple of entries so we don't reparse on every webhook hit.
    Bare IPs become /32 networks; ``strict=False`` tolerates host bits set.
    """
    nets: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for entry in entries:
        try:
            nets.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            logger.warning("strategy_webhook.bad_tv_cidr", value=entry)
    return tuple(nets)


def _is_trusted_tradingview_ip(client_ip: str | None) -> bool:
    """True if ``client_ip`` falls within any configured TV CIDR/IP."""
    if not client_ip:
        return False
    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    nets = _parse_tv_networks(tuple(get_settings().tradingview_trusted_ips))
    return any(addr in net for net in nets)


def _signature_canonical(body: dict[str, Any]) -> bytes:
    """Helper kept for tests — sign the same bytes the verify path uses."""
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def _compute_strategy_signal_hash(
    user_id: UUID, payload: dict[str, Any], raw_body: bytes
) -> str:
    """Idempotency key — mirrors :func:`app.api.webhook._compute_signal_hash`.

    If the (post-mapping or native) payload supplied ``signal_id``, trust
    it so callers can explicitly suppress retries. Otherwise hash the raw
    body with the user id so two users sending identical alerts never
    collide.
    """
    sid = payload.get("signal_id")
    if sid:
        return f"{user_id}:{sid}"
    digest = hashlib.sha256(raw_body).hexdigest()
    return f"{user_id}:{digest}"


__all__ = ["QUANTITY_CEILING_CONTRACTS", "router"]
