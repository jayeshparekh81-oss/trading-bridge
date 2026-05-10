"""Market Strength Shield — EXIT DELAY when 4-index breadth is strong.

Faithful but hardened port of:
* ``/tmp/cowork_legacy/market_strength_shield.py`` — 4-index breadth
  computation + ``should_shield_block_exit`` decision logic.
* ``/tmp/cowork_legacy/position_guardian.py`` — Guardian's call site
  that consulted the shield before force/trail exits.

The legacy bot **blocked exits indefinitely** while breadth was strong,
which is incompatible with ``state_divergence_rule.md``:

* **RULE 1** — never decides to trade. The shield only **delays** Pine's
  pre-existing EXIT signal. Max delay = 2 closed 15-min bars (30 min).
  After delay or ATR override, the original EXIT is released and
  dispatched to :mod:`app.services.direct_exit` unchanged.
* **RULE 2** — closed-bar evaluation only. Index OHLC read from Redis
  snapshots written by an out-of-band worker (deferred to Phase 2 — see
  cold-start note below). ATR-override re-evaluation only on next Pine
  webhook arrival (which itself fires on bar close).
* **Pine alignment** — Pine's EXIT *always* executes within 2 bars OR
  immediately on >1×ATR drop. The hold queue lives in Redis with a
  31-minute TTL safety fallback.

Indices
-------
4 indices: ``NIFTY50``, ``BANKNIFTY``, ``SENSEX``, ``BSE_MIDCAP``.
Each is "bullish" when ≥3 of 4 sub-checks pass:

  1. LTP > VWAP proxy (= ``(H + L + C) / 3``, the typical price)
  2. LTP > intraday open
  3. LTP > previous-day close
  4. LTP sits in the upper 60% of the day's H–L range

Shield activates when ≥3 of 4 indices are bullish (relaxed from the
legacy bot's 4-of-4 to lift the actual fire rate, per Sun 2026-05-10
product call).

Cold start
----------
Phase-1 ships **without an index data fetcher**. Until a Phase-2 worker
populates ``mshield:idx:{INDEX_KEY}`` keys, every breadth evaluation
returns ``cold_start=True`` and the shield is a pure pass-through. This
is intentional: the shield can't accidentally hold an EXIT before its
data source is wired.

Default OFF
-----------
``settings.market_shield_enabled`` is False by default. When False every
public function short-circuits to a no-op (no Redis I/O, no compute).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core import redis_client
from app.core.config import get_settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.strategy_signal import StrategySignal

logger = get_logger("app.services.market_shield")


# ═══════════════════════════════════════════════════════════════════════
# Tunables (constants — env knobs go in app.core.config.Settings)
# ═══════════════════════════════════════════════════════════════════════

#: 4 broad-market indices monitored by the shield. ``BSE_MIDCAP`` is the
#: BSE-aligned variant chosen for the BSE 0DTE strategy (legacy bot
#: used MIDCAP_SELECT, the NSE Nifty Midcap Select; we swap to BSE
#: Midcap for venue alignment).
INDEX_KEYS: tuple[str, ...] = ("NIFTY50", "BANKNIFTY", "SENSEX", "BSE_MIDCAP")

INDEX_NAMES: dict[str, str] = {
    "NIFTY50": "Nifty 50",
    "BANKNIFTY": "Bank Nifty",
    "SENSEX": "Sensex",
    "BSE_MIDCAP": "BSE Midcap",
}

#: Per-index sub-checks needed to call that index "bullish".
_INDEX_BULLISH_MIN_CHECKS: int = 3

#: Number of indices (out of 4) that must be bullish for the shield to
#: activate. Relaxed from legacy 4 to 3 per product call.
_BREADTH_MIN_BULLISH: int = 3

#: Lower bound (fraction of day's H-L range) for the "upper 60%" check.
_RANGE_UPPER_THRESHOLD: float = 0.40

#: ATR-multiple drop from entry that releases an in-flight hold or skips
#: a hold at decision time. 1.0 ATR matches the legacy bot's
#: SHIELD_FALL_ATR_THRESHOLD.
_ATR_OVERRIDE_THRESHOLD: float = 1.0

#: Max hold wallclock duration (seconds). 30 min = 2 × 15-min bars on
#: the BSE 0DTE timeframe.
_HOLD_MAX_SECONDS: int = 30 * 60

#: Redis TTL on the hold record. Slightly larger than the max hold so
#: a successful release-by-timeout always finds the record present.
_HOLD_TTL_SECONDS: int = 31 * 60


# ═══════════════════════════════════════════════════════════════════════
# Redis key helpers
# ═══════════════════════════════════════════════════════════════════════

def _idx_key(index_key: str) -> str:
    """Per-index OHLC snapshot key. Phase-2 fetcher writes these."""
    return f"mshield:idx:{index_key}"


def _hold_key(strategy_id: UUID | str) -> str:
    """One held EXIT per strategy. Newer holds overwrite older."""
    return f"mshield:held:{strategy_id}"


# ═══════════════════════════════════════════════════════════════════════
# Result dataclasses
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class IndexBullishCheck:
    """Per-index outcome of the 4 sub-checks."""

    index_key: str
    name: str
    is_bullish: bool
    score: float
    error: str | None = None


@dataclass(frozen=True)
class BreadthResult:
    """Outcome of one breadth evaluation pass."""

    bullish_count: int
    bullish_names: list[str]
    bearish_names: list[str]
    cold_start: bool  # True iff <4 indices have OHLC available in Redis
    indices: list[IndexBullishCheck] = field(default_factory=list)

    @property
    def shield_active(self) -> bool:
        return (not self.cold_start) and self.bullish_count >= _BREADTH_MIN_BULLISH


@dataclass(frozen=True)
class HoldDecision:
    """Outcome of a single ``maybe_hold_exit`` call."""

    held: bool
    reason: str
    release_at_iso: str | None = None
    breadth: BreadthResult | None = None


@dataclass(frozen=True)
class ReleaseResult:
    """Outcome of a single ``try_release`` call."""

    released: bool
    signal_id: str | None = None
    reason: str | None = None  # "timeout" | "atr_override"
    held_record: dict[str, Any] | None = None


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

def is_enabled() -> bool:
    """Master toggle. False unless ``MARKET_SHIELD_ENABLED`` is set."""
    return bool(get_settings().market_shield_enabled)


def _coerce_float(value: Any) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _compute_vwap_proxy(ohlc: dict[str, Any]) -> float:
    """Typical-price VWAP approximation: ``(H + L + C) / 3``.

    True VWAP needs volume-weighted ticks. Index-level volume isn't
    consistently exposed, so legacy bot used the typical-price form for
    all 4 indices. Same formula here for SENSEX (Hidden Gem #7 from the
    feature audit) and the rest.
    """
    h = _coerce_float(ohlc.get("high"))
    l = _coerce_float(ohlc.get("low"))
    c = _coerce_float(ohlc.get("ltp"))
    if h > 0 and l > 0 and c > 0:
        return (h + l + c) / 3.0
    return 0.0


def _evaluate_index(index_key: str, ohlc: dict[str, Any]) -> IndexBullishCheck:
    """Run the 4-check bullish classification on a single index."""
    name = INDEX_NAMES.get(index_key, index_key)
    ltp = _coerce_float(ohlc.get("ltp"))
    open_p = _coerce_float(ohlc.get("open"))
    high = _coerce_float(ohlc.get("high"))
    low = _coerce_float(ohlc.get("low"))
    prev_close = _coerce_float(ohlc.get("prev_close"))

    if ltp <= 0 or open_p <= 0:
        return IndexBullishCheck(index_key, name, False, 0.0, "missing_ohlc")

    checks_passed = 0
    score = 0.0

    # Check 1: above VWAP proxy
    vwap = _compute_vwap_proxy(ohlc)
    if vwap > 0 and ltp > vwap:
        checks_passed += 1
        score += 25

    # Check 2: above intraday open
    if ltp > open_p:
        checks_passed += 1
        pct = ((ltp - open_p) / open_p) * 100
        score += min(25, pct * 50)

    # Check 3: above previous-day close
    if prev_close > 0 and ltp > prev_close:
        checks_passed += 1
        pct = ((ltp - prev_close) / prev_close) * 100
        score += min(25, pct * 30)

    # Check 4: in upper 60% of day's H-L range
    rng = high - low
    if rng > 0:
        position_in_range = (ltp - low) / rng
        if position_in_range >= _RANGE_UPPER_THRESHOLD:
            checks_passed += 1
            score += 25 * position_in_range

    is_bullish = checks_passed >= _INDEX_BULLISH_MIN_CHECKS
    return IndexBullishCheck(
        index_key=index_key,
        name=name,
        is_bullish=is_bullish,
        score=round(min(100.0, max(-100.0, score)), 1),
    )


async def evaluate_breadth() -> BreadthResult:
    """Read 4-index OHLC from Redis and compute current breadth.

    Cold-start (any index missing) returns ``cold_start=True`` and the
    caller treats the shield as inactive. Redis-read errors fall through
    the same path — a poisoned cache must never block (or worse, hold)
    a live signal.
    """
    indices: list[IndexBullishCheck] = []
    available = 0
    for key in INDEX_KEYS:
        ohlc: Any = None
        try:
            ohlc = await redis_client.cache_get_json(_idx_key(key))
        except Exception as exc:  # noqa: BLE001 — never fail signal
            logger.warning(
                "market_shield.idx_read_failed",
                index=key,
                error=str(exc),
            )
            ohlc = None
        if ohlc and isinstance(ohlc, dict):
            available += 1
            indices.append(_evaluate_index(key, ohlc))
        else:
            indices.append(
                IndexBullishCheck(
                    index_key=key,
                    name=INDEX_NAMES[key],
                    is_bullish=False,
                    score=0.0,
                    error="no_redis_data",
                )
            )

    bullish_names = [i.name for i in indices if i.is_bullish]
    bearish_names = [i.name for i in indices if not i.is_bullish]
    cold_start = available < len(INDEX_KEYS)

    return BreadthResult(
        bullish_count=len(bullish_names),
        bullish_names=bullish_names,
        bearish_names=bearish_names,
        cold_start=cold_start,
        indices=indices,
    )


async def has_active_hold(strategy_id: UUID | str) -> bool:
    """True iff a held EXIT for this strategy currently lives in Redis."""
    if not is_enabled():
        return False
    try:
        rec = await redis_client.cache_get_json(_hold_key(strategy_id))
        return bool(rec)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "market_shield.hold_check_failed",
            strategy_id=str(strategy_id),
            error=str(exc),
        )
        return False


async def maybe_hold_exit(
    session: "AsyncSession",
    *,
    strategy_id: UUID,
    signal: "StrategySignal",
) -> HoldDecision:
    """Decide whether to hold this EXIT. Writes the Redis record on hold.

    Returns ``HoldDecision(held=False, ...)`` when:
      * shield disabled (``"disabled"``)
      * payload missing side / no open position (``"no_open_position"``)
      * entry/atr/price unusable (``"insufficient_data_at_hold"``)
      * cold-start — any index OHLC missing (``"cold_start_index_data"``)
      * breadth weak — fewer than 3 of 4 bullish (``"breadth_weak(...)"`)
      * already actively falling — loss ≥1×ATR (``"atr_override_at_hold"``)

    On ``held=True`` the Redis hold record is set with TTL
    ``_HOLD_TTL_SECONDS``. Caller is responsible for marking the signal
    row's ``status`` and skipping the direct-exit dispatch.
    """
    if not is_enabled():
        return HoldDecision(False, "disabled")

    payload = signal.raw_payload or {}
    side = str(payload.get("side") or "").lower()
    if side not in ("long", "short"):
        return HoldDecision(False, "missing_side")

    # Look up the open position to source entry_price / current_atr.
    # Importing inline avoids a circular: direct_exit imports schemas
    # which transitively reference this module via webhook wire-up.
    from app.services.direct_exit import get_open_position

    position = await get_open_position(
        session,
        strategy_id=strategy_id,
        symbol=signal.symbol,
        side=side,
    )
    if position is None or (position.remaining_quantity or 0) <= 0:
        return HoldDecision(False, "no_open_position")

    entry_price = _coerce_float(position.avg_entry_price)
    indicators = payload.get("indicators") or {}
    atr = _coerce_float(
        indicators.get("ATR")
        or indicators.get("atr")
        or position.current_atr
    )
    current_price = _coerce_float(payload.get("price"))

    if entry_price <= 0 or atr <= 0 or current_price <= 0:
        return HoldDecision(False, "insufficient_data_at_hold")

    breadth = await evaluate_breadth()
    if breadth.cold_start:
        return HoldDecision(False, "cold_start_index_data", breadth=breadth)
    if not breadth.shield_active:
        return HoldDecision(
            False,
            f"breadth_weak({breadth.bullish_count}/4)",
            breadth=breadth,
        )

    # Loss in ATR multiples — only count adverse moves.
    if side == "long":
        loss_atr = (
            (entry_price - current_price) / atr
            if current_price < entry_price
            else 0.0
        )
    else:  # short
        loss_atr = (
            (current_price - entry_price) / atr
            if current_price > entry_price
            else 0.0
        )

    if loss_atr >= _ATR_OVERRIDE_THRESHOLD:
        return HoldDecision(
            False,
            f"atr_override_at_hold(loss={loss_atr:.2f}ATR)",
            breadth=breadth,
        )

    held_at = datetime.now(UTC)
    release_at = held_at + timedelta(seconds=_HOLD_MAX_SECONDS)
    record: dict[str, Any] = {
        "signal_id": str(signal.id),
        "strategy_id": str(strategy_id),
        "side": side,
        "symbol": signal.symbol,
        "entry_price": entry_price,
        "atr_at_hold": atr,
        "held_at_iso": held_at.isoformat(),
        "release_at_iso": release_at.isoformat(),
        "breadth_bullish_count": breadth.bullish_count,
        "reason_at_hold": (
            f"breadth={breadth.bullish_count}/4|loss={loss_atr:.2f}ATR"
        ),
    }
    try:
        await redis_client.cache_set_json(
            _hold_key(strategy_id),
            record,
            ttl_seconds=_HOLD_TTL_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "market_shield.hold_write_failed",
            strategy_id=str(strategy_id),
            error=str(exc),
        )
        return HoldDecision(False, "redis_write_failed", breadth=breadth)

    return HoldDecision(
        held=True,
        reason=f"breadth={breadth.bullish_count}/4_bullish_no_active_fall",
        release_at_iso=release_at.isoformat(),
        breadth=breadth,
    )


async def try_release(
    *,
    strategy_id: UUID | str,
    current_price: float | None,
) -> ReleaseResult:
    """Check if any held EXIT for this strategy should be released now.

    Called on every Pine webhook arrival (any action). Releases on:
      * timeout — wallclock past ``release_at_iso`` (≥30 min since hold)
      * atr_override — drop from snapshotted entry ≥ 1×ATR

    On release, deletes the Redis hold record. Caller is responsible
    for re-dispatching the held signal_id into the direct-exit path.
    """
    if not is_enabled():
        return ReleaseResult(False)
    try:
        record = await redis_client.cache_get_json(_hold_key(strategy_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "market_shield.hold_read_failed",
            strategy_id=str(strategy_id),
            error=str(exc),
        )
        return ReleaseResult(False)
    if not record or not isinstance(record, dict):
        return ReleaseResult(False)

    signal_id = record.get("signal_id")
    if not signal_id:
        # Malformed record — clean up so it doesn't block forever.
        await _consume_hold(strategy_id)
        return ReleaseResult(False)

    # (a) Timeout?
    release_at: datetime | None = None
    try:
        release_at = datetime.fromisoformat(str(record["release_at_iso"]))
    except (KeyError, TypeError, ValueError):
        release_at = None

    now = datetime.now(UTC)
    if release_at is not None and now >= release_at:
        await _consume_hold(strategy_id)
        return ReleaseResult(
            released=True,
            signal_id=signal_id,
            reason="timeout",
            held_record=record,
        )

    # (b) ATR override?
    side = str(record.get("side", "")).lower()
    entry_price = _coerce_float(record.get("entry_price"))
    atr_at_hold = _coerce_float(record.get("atr_at_hold"))

    if (
        current_price is not None
        and current_price > 0
        and entry_price > 0
        and atr_at_hold > 0
    ):
        if side == "long":
            loss_atr = (
                (entry_price - current_price) / atr_at_hold
                if current_price < entry_price
                else 0.0
            )
        else:
            loss_atr = (
                (current_price - entry_price) / atr_at_hold
                if current_price > entry_price
                else 0.0
            )
        if loss_atr >= _ATR_OVERRIDE_THRESHOLD:
            await _consume_hold(strategy_id)
            return ReleaseResult(
                released=True,
                signal_id=signal_id,
                reason="atr_override",
                held_record=record,
            )

    return ReleaseResult(False)


async def _consume_hold(strategy_id: UUID | str) -> None:
    """Delete the Redis hold record. Tolerates Redis errors."""
    try:
        await redis_client.cache_delete(_hold_key(strategy_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "market_shield.hold_delete_failed",
            strategy_id=str(strategy_id),
            error=str(exc),
        )


# ═══════════════════════════════════════════════════════════════════════
# Test-only helper — Phase-2 fetcher will write these via real worker.
# ═══════════════════════════════════════════════════════════════════════

async def _set_index_ohlc_for_test(
    index_key: str, ohlc: dict[str, Any], ttl_seconds: int = 60
) -> None:
    """Write a single index OHLC snapshot to Redis. Phase-1 has no real
    fetcher — this helper exists so tests can populate breadth state."""
    await redis_client.cache_set_json(
        _idx_key(index_key), ohlc, ttl_seconds=ttl_seconds,
    )


__all__ = [
    "INDEX_KEYS",
    "INDEX_NAMES",
    "IndexBullishCheck",
    "BreadthResult",
    "HoldDecision",
    "ReleaseResult",
    "is_enabled",
    "evaluate_breadth",
    "maybe_hold_exit",
    "try_release",
    "has_active_hold",
]
