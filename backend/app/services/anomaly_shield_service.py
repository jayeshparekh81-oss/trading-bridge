"""Black-Swan Anomaly Shield — entry-block on multivariate indicator anomaly.

Faithful port of the AWS bot's ``trade_brain._detect_anomaly`` logic
(``/tmp/cowork_legacy/trade_brain.py:363``), reframed to satisfy
``state_divergence_rule.md``:

* **RULE 1** — never takes a broker action. The shield only **blocks new
  entries** by returning a REJECTED ``AIDecision`` from the upstream
  webhook handler. Existing positions are untouched.
* **RULE 2** — evaluation runs on confirmed bar close only. Each TV
  webhook = one bar; we never poll mid-bar. Cooldown is enforced via
  Redis TTL — no scheduled job required.
* **Pine alignment** — purely additive. The shield can only tighten the
  entry gate; Pine's own filters still apply on top.

How it works
------------
1. **Baseline** — for every confirmed ENTRY signal we append the 22-d
   indicator vector to a per-strategy rolling window in Redis (max 200
   bars, TTL 7d). The window is the empirical distribution.
2. **Cold start** — until 50 bars are collected, the shield is disabled
   (returns ``warming_up``) but still records data.
3. **Z-score** — for the current bar, compute ``z = |val - mean| / std``
   per indicator using the rolling window's mean/std.
4. **Composite score** — combines the **count** of indicators in extreme
   territory (|z| > 2.5) and the **average severity** of those
   indicators::

       composite = (extreme_count / 22) * 50 + (avg_extreme_z / 5) * 50

   Capped at 100. ``> 70`` = trip (stricter than the legacy bot's 80
   threshold per Sun 2026-05-10 product call).
5. **Cooldown** — on trip, set a per-strategy block flag with TTL =
   ``anomaly_block_bars * 900s`` (4 bars × 15 min = 1 h). While set,
   every ENTRY is rejected without re-evaluation. Auto-expires.
6. **Telegram** — fire WARNING on trip, INFO on lazy release (i.e. the
   first signal landing after the cooldown TTL elapses). No alerts
   on each blocked signal in between — we don't want to spam.

Default OFF
-----------
``settings.black_swan_shield_enabled`` is False by default. When False,
:func:`is_enabled` returns False and every other call short-circuits to
a no-op — no Redis writes, no compute, zero cost.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.core import redis_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.services._dna_vector import DNA_KEYS as _DNA_KEYS
from app.services._dna_vector import coerce_float as _coerce_float

logger = get_logger("app.services.anomaly_shield")

# ═══════════════════════════════════════════════════════════════════════
# Tunables (constants — env knobs live in app.core.config.Settings)
# ═══════════════════════════════════════════════════════════════════════

#: Minimum bars before the shield is allowed to evaluate. Below this we
#: return ``warming_up`` and skip evaluation. Recording still happens.
MIN_BARS_REQUIRED: int = 50

#: Hard cap on the rolling window. ~200 × 22 floats × 8 bytes ≈ 35KB
#: per strategy in Redis JSON form — cheap.
MAX_BARS_KEPT: int = 200

#: Bar-cadence in seconds — TradingView webhooks fire on 15-min closes.
_BAR_SECONDS: int = 15 * 60

#: TTL for the rolling window; refreshed on every record. 7 days means
#: an idle strategy resets cleanly without manual cleanup.
_BAR_HISTORY_TTL_SECONDS: int = 7 * 24 * 3600

#: TTL for the lazy-release marker. Outlives any conceivable cooldown
#: so the release alert fires on the first post-cooldown signal even
#: if it's hours later.
_RELEASE_PENDING_TTL_SECONDS: int = 24 * 3600


# ═══════════════════════════════════════════════════════════════════════
# Redis key helpers
# ═══════════════════════════════════════════════════════════════════════

def _bar_key(strategy_id: UUID | str) -> str:
    return f"anom:bar:{strategy_id}"


def _block_key(strategy_id: UUID | str) -> str:
    return f"anom:block:{strategy_id}"


def _release_pending_key(strategy_id: UUID | str) -> str:
    return f"anom:release_pending:{strategy_id}"


# ═══════════════════════════════════════════════════════════════════════
# Result dataclass
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AnomalyResult:
    """Outcome of one evaluation pass.

    Attributes:
        tripped: True iff composite > anomaly_composite_threshold.
        composite_score: 0-100. 0 = perfectly normal, 100 = max extreme.
        extreme_indicators: List of dicts ``{indicator, z, value}`` for
            every indicator with ``z > anomaly_z_threshold``. Sorted by
            descending z.
        reason: One of: ``"disabled"``, ``"warming_up"``, ``"normal"``,
            ``"tripped"``. Free-form for log/alert use.
        bars_collected: Size of the rolling window when this evaluation
            ran. Useful for "X / 50 bars" warming-up messaging.
    """

    tripped: bool
    composite_score: float
    reason: str
    bars_collected: int
    extreme_indicators: list[dict[str, Any]] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════
# Public API — used by strategy_webhook
# ═══════════════════════════════════════════════════════════════════════

def is_enabled() -> bool:
    """Master toggle. False unless ``BLACK_SWAN_SHIELD_ENABLED`` is set."""
    return bool(get_settings().black_swan_shield_enabled)


async def record_indicator_bar(
    strategy_id: UUID | str, indicators: dict[str, Any]
) -> None:
    """Append the current bar's indicator vector to the rolling window.

    Always called before evaluation so the very first bar contributes to
    its own baseline distribution (matters less once the window grows,
    but it keeps the cold-start arithmetic well-defined).

    No-op when the shield is disabled. No-op on Redis errors — a poisoned
    cache must never fail a live signal.
    """
    if not is_enabled():
        return
    try:
        history = await redis_client.cache_get_json(_bar_key(strategy_id)) or []
        if not isinstance(history, list):
            history = []
        vec = [_coerce_float(indicators.get(k)) for k in _DNA_KEYS]
        history.append(vec)
        if len(history) > MAX_BARS_KEPT:
            history = history[-MAX_BARS_KEPT:]
        await redis_client.cache_set_json(
            _bar_key(strategy_id),
            history,
            ttl_seconds=_BAR_HISTORY_TTL_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 — never fail the signal
        logger.warning(
            "anomaly_shield.record_failed",
            strategy_id=str(strategy_id),
            error=str(exc),
        )


async def is_block_active(strategy_id: UUID | str) -> bool:
    """True while the cooldown is in effect for this strategy."""
    if not is_enabled():
        return False
    try:
        val = await redis_client.cache_get(_block_key(strategy_id))
        return val is not None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "anomaly_shield.block_check_failed",
            strategy_id=str(strategy_id),
            error=str(exc),
        )
        return False


async def evaluate(
    strategy_id: UUID | str, indicators: dict[str, Any]
) -> AnomalyResult:
    """Compute z-scores against the rolling baseline and classify the bar.

    Caller is expected to have already called :func:`record_indicator_bar`
    so the current bar is part of the distribution. (This is intentional —
    the population is small enough that "include self" vs "exclude self"
    z-score variants make no material difference at N >= 50.)

    Returns an :class:`AnomalyResult`. Caller decides whether to act on
    ``.tripped`` (typically: call :func:`activate_block` + reject the
    signal).
    """
    settings = get_settings()
    if not settings.black_swan_shield_enabled:
        return AnomalyResult(
            tripped=False,
            composite_score=0.0,
            reason="disabled",
            bars_collected=0,
        )

    try:
        history = await redis_client.cache_get_json(_bar_key(strategy_id)) or []
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "anomaly_shield.history_read_failed",
            strategy_id=str(strategy_id),
            error=str(exc),
        )
        return AnomalyResult(
            tripped=False,
            composite_score=0.0,
            reason="error",
            bars_collected=0,
        )

    if not isinstance(history, list):
        history = []

    n = len(history)
    if n < MIN_BARS_REQUIRED:
        return AnomalyResult(
            tripped=False,
            composite_score=0.0,
            reason="warming_up",
            bars_collected=n,
        )

    # Compute mean and population std per dimension.
    means: list[float] = []
    stds: list[float] = []
    dim = len(_DNA_KEYS)
    for i in range(dim):
        col = [float(row[i]) for row in history if isinstance(row, list) and len(row) > i]
        if not col:
            means.append(0.0)
            stds.append(0.0)
            continue
        m = sum(col) / len(col)
        var = sum((x - m) ** 2 for x in col) / len(col)
        means.append(m)
        stds.append(math.sqrt(var))

    # Current vector.
    current = [_coerce_float(indicators.get(k)) for k in _DNA_KEYS]

    extreme: list[dict[str, Any]] = []
    z_threshold = settings.anomaly_z_threshold
    for i, key in enumerate(_DNA_KEYS):
        if stds[i] <= 0.0:
            continue
        z = abs(current[i] - means[i]) / stds[i]
        if z > z_threshold:
            extreme.append({
                "indicator": key,
                "z": round(z, 2),
                "value": round(current[i], 4),
            })

    extreme.sort(key=lambda e: e["z"], reverse=True)

    if not extreme:
        composite = 0.0
    else:
        avg_z = sum(e["z"] for e in extreme) / len(extreme)
        composite = min(
            100.0,
            (len(extreme) / dim) * 50.0 + (avg_z / 5.0) * 50.0,
        )

    tripped = composite > settings.anomaly_composite_threshold
    reason = "tripped" if tripped else "normal"

    return AnomalyResult(
        tripped=tripped,
        composite_score=round(composite, 2),
        reason=reason,
        bars_collected=n,
        extreme_indicators=extreme,
    )


async def activate_block(strategy_id: UUID | str) -> int:
    """Set the cooldown flag and the lazy-release marker.

    Returns the cooldown duration in seconds, for caller logging.
    """
    settings = get_settings()
    cooldown = max(1, settings.anomaly_block_bars) * _BAR_SECONDS
    try:
        await redis_client.cache_set(
            _block_key(strategy_id), str(int(time.time())),
            ttl_seconds=cooldown,
        )
        # Pending-release marker outlives the block — the next signal
        # landing after cooldown sees it, fires the release alert, and
        # clears it.
        await redis_client.cache_set(
            _release_pending_key(strategy_id), "1",
            ttl_seconds=_RELEASE_PENDING_TTL_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "anomaly_shield.activate_failed",
            strategy_id=str(strategy_id),
            error=str(exc),
        )
    return cooldown


async def check_and_consume_release(strategy_id: UUID | str) -> bool:
    """Lazy release-alert trigger.

    Returns True iff a previous trip's cooldown has just expired AND
    this is the first call to observe it. Caller fires the Telegram
    alert. Returns False (no-op) when the shield is disabled, no trip
    is pending, or the cooldown is still active.
    """
    if not is_enabled():
        return False
    try:
        pending = await redis_client.cache_get(_release_pending_key(strategy_id))
        if not pending:
            return False
        # Block still in force? Don't release yet.
        if await is_block_active(strategy_id):
            return False
        await redis_client.cache_delete(_release_pending_key(strategy_id))
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "anomaly_shield.release_check_failed",
            strategy_id=str(strategy_id),
            error=str(exc),
        )
        return False


__all__ = [
    "AnomalyResult",
    "MIN_BARS_REQUIRED",
    "MAX_BARS_KEPT",
    "is_enabled",
    "record_indicator_bar",
    "is_block_active",
    "evaluate",
    "activate_block",
    "check_and_consume_release",
]
