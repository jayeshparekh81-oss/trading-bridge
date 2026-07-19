"""Master emergency halt — FANOUT_DESIGN tier-3 (founder-locked). NEW · DORMANT.

PAPER / PLAN stage. :func:`master_emergency_halt` is a PURE, TESTABLE unit:
given the current open positions (owner + subscriber) and the active
subscribers, it

  * sets a platform-wide halt flag via an injectable :class:`HaltFlagStore`
    (default: an in-process store). **The DURABLE Redis/DB backing AND the
    webhook enforcement that actually BLOCKS new entries are SACRED wiring —
    a later, separately-gated step. Today this only sets/exposes the flag.**
  * builds a close-all PLAN (``positions_to_close``) — the intended close list.
    **Actual dispatch through the exit path is SACRED wiring, later.**
  * forces every subscriber to MANUAL (``subscribers_forced_manual``). The
    ``execution_mode`` DB UPDATE is a thin, injectable applier (omitted here /
    in tests) — the plan carries the intended transition.
  * emits notify payloads (Telegram/alert message objects) + a full
    ``audit_entry``.

No broker is ever built or called. This module is imported by NO sacred
execution file (``direct_exit`` / ``kill_switch_service`` / ``strategy_webhook``
/ ``signal_execution`` / ``dhan``).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from app.core.logging import get_logger

logger = get_logger("app.services.master_emergency")


# ─────────────────────────── platform halt flag ────────────────────────────
@runtime_checkable
class HaltFlagStore(Protocol):
    """Where the platform-wide halt bit lives.

    Paper/now: :class:`InProcessHaltStore` (per-process, NOT durable). The
    real-money stage swaps in a Redis/DB-backed store implementing this same
    interface + the webhook read that blocks entries — both SACRED wiring,
    later. The call sites here do not change.
    """

    def is_halted(self) -> bool: ...

    def set_halted(self, value: bool) -> None: ...


class InProcessHaltStore:
    """In-process halt flag. NOT cross-process / NOT durable — a placeholder
    until the Redis/DB-backed store is wired (sacred, later)."""

    def __init__(self) -> None:
        self._halted = False

    def is_halted(self) -> bool:
        return self._halted

    def set_halted(self, value: bool) -> None:
        self._halted = bool(value)


#: The durable halt key. Namespaced under ``platform:`` (distinct from the
#: per-user kill-switch keys in :mod:`app.core.redis_client`).
_REDIS_HALT_KEY = "platform:emergency_halt"


class RedisHaltStore:
    """Durable, cross-process halt flag — the deploy-time replacement for
    :class:`InProcessHaltStore`.

    Backed by Redis so the halt SURVIVES a process restart and is SHARED across
    the backend + worker. Reuses the app's existing ``settings.redis_url`` (the
    SAME config the async client uses — :func:`app.core.redis_client.get_redis`);
    a SYNC :class:`redis.Redis` connection is used so this satisfies the SYNC
    :class:`HaltFlagStore` interface with NO change to any caller (the halt read
    is an infrequent, single ``GET``).

    **Fail-CLOSED:** if Redis is unreachable, :meth:`is_halted` returns ``True``.
    A safety switch must default to *halted / block new entries* when it cannot
    confirm the platform is safe — never let trades through blind. A ``set``
    failure is logged, not raised, so it can never break the close-all in
    :meth:`KillSwitchService.execute_master_emergency` (the close is the critical
    action; the fail-closed read covers the redis-down window).

    ``client`` is injectable (a fake redis in tests). Not flipped in as the
    default anywhere — selection is a deploy-time config/DI choice.
    """

    def __init__(self, *, client: Any = None, url: str | None = None,
                 reason: str = "master emergency halt") -> None:
        self._client = client
        self._url = url
        self._reason = reason

    def _redis(self) -> Any:
        if self._client is not None:
            return self._client
        import redis as _redis

        from app.core.config import get_settings

        return _redis.Redis.from_url(
            self._url or get_settings().redis_url, decode_responses=True
        )

    def is_halted(self) -> bool:
        try:
            return self._redis().get(_REDIS_HALT_KEY) is not None
        except Exception:  # broad by design — FAIL-CLOSED (block when unsure)
            logger.warning("master_emergency.redis_unreachable_fail_closed")
            return True

    def set_halted(self, value: bool) -> None:
        try:
            client = self._redis()
            if value:
                client.set(_REDIS_HALT_KEY, json.dumps({
                    "halted": True,
                    "reason": self._reason,
                    "at": datetime.now(UTC).isoformat(),
                }))
            else:
                client.delete(_REDIS_HALT_KEY)
        except Exception:  # broad by design — never break the close-all
            logger.warning("master_emergency.redis_set_failed", value=value)


#: Module-level default store. Process-local only — see class docstring.
_DEFAULT_STORE = InProcessHaltStore()


def is_platform_halted(*, store: HaltFlagStore | None = None) -> bool:
    """Read the platform-wide halt flag. Defaults to :data:`_DEFAULT_STORE`."""
    return (store or _DEFAULT_STORE).is_halted()


def clear_platform_halt(*, store: HaltFlagStore | None = None) -> None:
    """Lift the halt (operational reset). Kept symmetrical with the setter."""
    (store or _DEFAULT_STORE).set_halted(False)


# ─────────────────────────────── the plan ──────────────────────────────────
@dataclass(frozen=True)
class HaltPlan:
    """The outcome of a master emergency halt (PLAN, not execution).

    ``positions_to_close`` and ``subscribers_forced_manual`` are the intended
    actions — dispatching the closes and applying the mode change to the DB are
    thin wired steps done later. ``notifications`` are message objects (built,
    not sent, here). ``audit_entry`` is the durable record to persist.
    """

    halted: bool
    reason: str
    at: str
    positions_to_close: list[dict[str, Any]] = field(default_factory=list)
    subscribers_forced_manual: list[dict[str, Any]] = field(default_factory=list)
    notifications: list[dict[str, Any]] = field(default_factory=list)
    audit_entry: dict[str, Any] = field(default_factory=dict)


def _is_open(obj: Any) -> bool:
    return str(getattr(obj, "status", "") or "").lower() in ("open", "partial")


def master_emergency_halt(
    *,
    positions: Iterable[Any],
    subscribers: Iterable[Any],
    reason: str,
    store: HaltFlagStore | None = None,
    now: datetime | None = None,
) -> HaltPlan:
    """Trip the master emergency halt and return the resulting :class:`HaltPlan`.

    PURE + side-effect-light: the ONLY mutation is setting the (injectable)
    halt flag. No broker is built/called; no position is closed; no DB row is
    written here. ``positions`` items are duck-typed on
    ``id`` / ``symbol`` / ``side`` / ``remaining_quantity`` / ``subscription_id``
    (``None`` ⇒ owner) / ``status``; ``subscribers`` on ``subscription_id`` /
    ``execution_mode``.
    """
    store = store or _DEFAULT_STORE
    ts = (now or datetime.now(UTC)).isoformat()

    # 1) Trip the platform-wide halt flag. Enforcement (webhook blocks new
    #    entries) + durable backing = SACRED wiring, later.
    store.set_halted(True)

    # 2) Close-all PLAN — every OPEN position, owner + subscriber alike.
    positions_to_close: list[dict[str, Any]] = []
    for p in positions:
        if not _is_open(p):
            continue
        sub_id = getattr(p, "subscription_id", None)
        positions_to_close.append({
            "position_id": str(getattr(p, "id", "")),
            "owner": sub_id is None,
            "subscription_id": str(sub_id) if sub_id is not None else None,
            "symbol": getattr(p, "symbol", None),
            "side": getattr(p, "side", None),
            "qty": int(getattr(p, "remaining_quantity", 0) or 0),
        })

    # 3) Force ALL subscribers to MANUAL (plan; DB apply = thin step, later).
    subscribers_forced_manual: list[dict[str, Any]] = []
    for sub in subscribers:
        from_mode = str(getattr(sub, "execution_mode", "auto") or "auto")
        subscribers_forced_manual.append({
            "subscription_id": str(getattr(sub, "subscription_id", "")),
            "from_mode": from_mode,
            "to_mode": "manual",
        })

    # 4) Notify payloads — built, NOT sent here.
    notifications: list[dict[str, Any]] = [{
        "channel": "telegram",
        "level": "CRITICAL",
        "message": (
            f"🛑 MASTER EMERGENCY HALT — reason: {reason}. Platform halted; "
            f"{len(positions_to_close)} open position(s) queued to close; "
            f"{len(subscribers_forced_manual)} subscriber(s) forced to MANUAL."
        ),
    }]
    for item in subscribers_forced_manual:
        notifications.append({
            "channel": "telegram",
            "level": "WARNING",
            "subscription_id": item["subscription_id"],
            "message": (
                "Copy-trading set to MANUAL by an emergency halt "
                f"(was {item['from_mode']}). No auto-exits will fire until the "
                "halt is cleared."
            ),
        })

    audit_entry: dict[str, Any] = {
        "event": "master_emergency_halt",
        "reason": reason,
        "at": ts,
        "halted": True,
        "positions_to_close": len(positions_to_close),
        "owner_positions": sum(1 for x in positions_to_close if x["owner"]),
        "subscriber_positions": sum(
            1 for x in positions_to_close if not x["owner"]),
        "subscribers_forced_manual": len(subscribers_forced_manual),
    }

    logger.warning(
        "master_emergency.halt",
        reason=reason,
        at=ts,
        positions_to_close=len(positions_to_close),
        subscribers_forced_manual=len(subscribers_forced_manual),
    )

    return HaltPlan(
        halted=True,
        reason=reason,
        at=ts,
        positions_to_close=positions_to_close,
        subscribers_forced_manual=subscribers_forced_manual,
        notifications=notifications,
        audit_entry=audit_entry,
    )
