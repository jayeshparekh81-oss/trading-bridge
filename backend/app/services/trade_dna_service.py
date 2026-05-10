"""Trade DNA Sequencing — cosine k-NN advisory scorer.

Faithful port of the AWS bot's ``trade_brain._compute_dna_match`` logic
(``/tmp/cowork_legacy/trade_brain.py:203``), reframed to satisfy
``state_divergence_rule.md``:

* **RULE 1** — *advisory only*. The score is attached to
  ``strategy_signals.raw_payload._dna`` and surfaced in logs. It does
  **not** affect approve/reject, never calls a broker, never trips a
  kill-switch. The AI validator's decision is unchanged.
* **RULE 2** — evaluation runs only inside the inbound TradingView
  webhook handler, which fires on confirmed 15-min bar close. No
  background poller, no scheduled task.
* **Pine alignment** — purely additive. Pine still drives every entry
  and exit; we annotate the signal record so the operator (and future
  analytics) can see "matches 8/10 winners last 30d".

How it works
------------
1. **Training pool** — for the incoming ``(strategy_id, side)``, query
   closed positions from the last ``trade_dna_lookback_days``
   (``strategy_positions`` JOIN ``strategy_signals``). Limit 200 most
   recent.
2. **Cold start** — until the pool reaches ``trade_dna_min_history``,
   return ``score=None`` with note ``INSUFFICIENT_HISTORY:n/N``.
3. **Outcome label** — ``final_pnl > trade_dna_winner_threshold_inr``
   (default ₹500) is a winner; everything else is a loser. Filters
   scratch trades eaten by brokerage/STT.
4. **Vectorize + normalize** — project each historical bar's indicators
   into the 22-d DNA vector, z-score normalize using pool means/stds.
5. **Similarity** — combined ``cosine * 0.6 + (1 / (1 + euclidean)) * 0.4``
   matches the legacy weighting.
6. **Top-K weighted vote** — ``win_prob = Σ(sim of winners) / Σ(sim total)``.
7. **Score** — ``dna_match_score = (win_prob - 50) * 2`` ∈ [-100, +100].
   Positive = current setup looks like past winners.

Caching
-------
The (means, stds, normalized vectors, outcomes) tuple is cached in Redis
under ``dna:history:{strategy_id}:{side}`` with TTL
``trade_dna_cache_ttl_secs`` (default 30 min). New closes show up within
that window — the freshness/load tradeoff is intentional.

Default OFF
-----------
``settings.trade_dna_enabled`` is False by default. When False,
:func:`is_enabled` returns False and :func:`evaluate` short-circuits to
a disabled result — no DB query, no Redis write, zero cost.
"""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import redis_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.strategy_position import StrategyPosition
from app.db.models.strategy_signal import StrategySignal
from app.services._dna_vector import (
    DNA_KEYS,
    coerce_float,
    indicators_to_vector,
)

logger = get_logger("app.services.trade_dna")


#: Hard cap on the per-(strategy, side) training pool. Mirrors the legacy
#: ``LIMIT 200`` — beyond this, older closes are discarded so the cosine
#: scan stays under ~10ms.
MAX_POOL_SIZE: int = 200


# ═══════════════════════════════════════════════════════════════════════
# Redis key helper
# ═══════════════════════════════════════════════════════════════════════

def _history_cache_key(strategy_id: UUID | str, side: str) -> str:
    return f"dna:history:{strategy_id}:{side.lower()}"


# ═══════════════════════════════════════════════════════════════════════
# Result dataclass
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DNAMatch:
    """One nearest-neighbour entry, surfaced in the result for log/audit."""

    similarity: float
    is_winner: bool
    pnl: float


@dataclass(frozen=True)
class DNAResult:
    """Outcome of one DNA evaluation pass.

    Attributes:
        enabled: True iff the service is on. False short-circuits everything.
        score: Match score in [-100, +100], or None on cold start / error.
            Positive = current setup looks like past winners.
        win_prob: Weighted win probability (0-100), or None on cold start.
        confidence: Confidence in the score (0-100), based on neighbour
            similarity and outcome consistency. None on cold start.
        winners: Number of winners in the top-K nearest neighbours.
        losers: Number of losers in the top-K.
        sample_size: Total training pool size.
        top_matches: Top up-to-5 matches for log/audit.
        note: Human-readable status: e.g. ``"INSUFFICIENT_HISTORY:7/20"``,
            ``"OK"``, ``"DISABLED"``, ``"ERROR:<msg>"``.
    """

    enabled: bool
    score: float | None
    win_prob: float | None
    confidence: float | None
    winners: int
    losers: int
    sample_size: int
    note: str
    top_matches: list[DNAMatch] = field(default_factory=list)

    def to_payload_dict(self) -> dict[str, Any]:
        """JSON-safe dict for embedding in ``raw_payload._dna``."""
        return {
            "enabled": self.enabled,
            "score": self.score,
            "win_prob": self.win_prob,
            "confidence": self.confidence,
            "winners": self.winners,
            "losers": self.losers,
            "sample_size": self.sample_size,
            "note": self.note,
            "top_matches": [asdict(m) for m in self.top_matches],
        }


# ═══════════════════════════════════════════════════════════════════════
# Public API — used by strategy_webhook
# ═══════════════════════════════════════════════════════════════════════

def is_enabled() -> bool:
    """Master toggle. False unless ``TRADE_DNA_ENABLED`` is set."""
    return bool(get_settings().trade_dna_enabled)


async def evaluate(
    session: AsyncSession,
    strategy_id: UUID | str,
    side: str,
    indicators: dict[str, Any],
) -> DNAResult:
    """Score the incoming bar against the strategy's historical closed pool.

    Pure read-side: queries the DB (or the Redis cache) and returns a
    :class:`DNAResult`. The caller is responsible for attaching the
    result to the signal — this function never writes to the DB.

    No-op (returns ``DISABLED``) when the master flag is off.
    On any DB / cache error returns a non-fatal ``ERROR:<msg>`` result;
    the caller continues normally.
    """
    settings = get_settings()
    if not settings.trade_dna_enabled:
        return DNAResult(
            enabled=False, score=None, win_prob=None, confidence=None,
            winners=0, losers=0, sample_size=0, note="DISABLED",
        )

    try:
        pool = await _load_history_pool(session, strategy_id, side, settings)
    except Exception as exc:  # noqa: BLE001 — never fail the signal
        logger.warning(
            "trade_dna.history_load_failed",
            strategy_id=str(strategy_id), side=side, error=str(exc),
        )
        return DNAResult(
            enabled=True, score=None, win_prob=None, confidence=None,
            winners=0, losers=0, sample_size=0, note=f"ERROR:{exc}",
        )

    n = len(pool["vectors"])
    if n < settings.trade_dna_min_history:
        return DNAResult(
            enabled=True, score=None, win_prob=None, confidence=None,
            winners=0, losers=0, sample_size=n,
            note=f"INSUFFICIENT_HISTORY:{n}/{settings.trade_dna_min_history}",
        )

    means: list[float] = pool["means"]
    stds: list[float] = pool["stds"]

    current_vec = indicators_to_vector(indicators)
    current_norm = _normalize(current_vec, means, stds)

    similarities: list[dict[str, Any]] = []
    for hist_norm, is_winner, pnl in zip(
        pool["vectors"], pool["winners"], pool["pnls"], strict=True,
    ):
        cos = _cosine(current_norm, hist_norm)
        euc = _euclidean(current_norm, hist_norm)
        # Legacy weighting: cosine for direction, inverse-euclidean for magnitude.
        combined = cos * 0.6 + (1.0 / (1.0 + euc)) * 0.4
        similarities.append({
            "similarity": combined, "is_winner": is_winner, "pnl": pnl,
        })

    similarities.sort(key=lambda s: s["similarity"], reverse=True)
    top_k = similarities[: max(1, settings.trade_dna_top_k)]

    winners = [s for s in top_k if s["is_winner"]]
    losers = [s for s in top_k if not s["is_winner"]]

    # Voting weight = clamp(similarity, 0, ∞). A neighbour whose vector
    # is anti-aligned (combined sim < 0) is "totally dissimilar" — it
    # carries zero vote, not negative. Avoids the degenerate case where
    # negative weights in numerator + denominator produce nonsensical
    # ratios (legacy bot had this latent bug, masked by diverse pools).
    weights = [max(0.0, s["similarity"]) for s in top_k]
    total_weight = sum(weights)
    if total_weight > 0.0:
        win_weight = sum(w for s, w in zip(top_k, weights, strict=True) if s["is_winner"])
        win_prob = (win_weight / total_weight) * 100.0
    else:
        # Every top-K neighbour is anti-similar — weighted vote undefined.
        # Fall back to the head-count ratio so the score still reflects
        # the loser-heavy / winner-heavy split.
        win_prob = (len(winners) / len(top_k)) * 100.0 if top_k else 50.0

    score = (win_prob - 50.0) * 2.0

    # Confidence: outcome consistency dominates (80%), similarity magnitude
    # contributes the remaining 20%. The legacy bot's formula was
    # ``(avg_sim*60 + consistency*40) * 100`` which saturated at 100 for
    # any non-trivial input — a known bug. We rebalance so a clean
    # one-sided pool (10 losers in top-K) still reports HIGH confidence
    # ("I'm sure"), while a 6/4 split reports LOW ("toss-up").
    clamped = [max(0.0, s["similarity"]) for s in top_k]
    avg_sim = statistics.mean(clamped) if clamped else 0.0
    consistency = abs(len(winners) - len(losers)) / max(1, len(top_k))
    confidence = min(100.0, avg_sim * 20.0 + consistency * 80.0)

    top_matches = [
        DNAMatch(
            similarity=round(s["similarity"], 4),
            is_winner=bool(s["is_winner"]),
            pnl=round(s["pnl"], 2),
        )
        for s in top_k[:5]
    ]

    return DNAResult(
        enabled=True,
        score=round(score, 1),
        win_prob=round(win_prob, 1),
        confidence=round(confidence, 1),
        winners=len(winners),
        losers=len(losers),
        sample_size=n,
        note="OK",
        top_matches=top_matches,
    )


# ═══════════════════════════════════════════════════════════════════════
# Internals
# ═══════════════════════════════════════════════════════════════════════

async def _load_history_pool(
    session: AsyncSession,
    strategy_id: UUID | str,
    side: str,
    settings: Any,
) -> dict[str, Any]:
    """Return ``{means, stds, vectors, winners, pnls}`` for the (strategy, side).

    Cache-first: hits Redis with TTL = ``trade_dna_cache_ttl_secs``. On
    miss, queries strategy_positions JOIN strategy_signals for the last
    ``trade_dna_lookback_days`` of closed positions, vectorizes the
    entry-bar indicators, normalizes, caches, returns.

    Vectors in the returned pool are already z-score normalized — saves
    re-normalizing on every signal.
    """
    cache_key = _history_cache_key(strategy_id, side)
    cached = await redis_client.cache_get_json(cache_key)
    if isinstance(cached, dict) and "vectors" in cached:
        return cached

    # Cache miss — query DB.
    from datetime import UTC, datetime, timedelta
    cutoff = datetime.now(UTC) - timedelta(days=settings.trade_dna_lookback_days)

    stmt = (
        select(
            StrategySignal.raw_payload,
            StrategyPosition.final_pnl,
        )
        .join(StrategyPosition, StrategyPosition.signal_id == StrategySignal.id)
        .where(
            StrategyPosition.strategy_id == strategy_id,
            StrategyPosition.side == side,
            StrategyPosition.closed_at.is_not(None),
            StrategyPosition.closed_at >= cutoff,
            StrategyPosition.final_pnl.is_not(None),
        )
        .order_by(StrategyPosition.closed_at.desc())
        .limit(MAX_POOL_SIZE)
    )

    rows = (await session.execute(stmt)).all()

    raw_vectors: list[list[float]] = []
    winners: list[bool] = []
    pnls: list[float] = []
    threshold = float(settings.trade_dna_winner_threshold_inr)

    for raw_payload, final_pnl in rows:
        if not isinstance(raw_payload, dict):
            continue
        indicators = raw_payload.get("indicators") or {}
        if not isinstance(indicators, dict):
            continue
        pnl_f = coerce_float(final_pnl)
        raw_vectors.append(indicators_to_vector(indicators))
        winners.append(pnl_f > threshold)
        pnls.append(pnl_f)

    n = len(raw_vectors)
    if n == 0:
        # Cache an empty pool too — saves DB hits on a brand-new strategy.
        empty = {
            "means": [0.0] * len(DNA_KEYS),
            "stds": [0.0] * len(DNA_KEYS),
            "vectors": [], "winners": [], "pnls": [],
        }
        await redis_client.cache_set_json(
            cache_key, empty, ttl_seconds=settings.trade_dna_cache_ttl_secs,
        )
        return empty

    means: list[float] = []
    stds: list[float] = []
    dim = len(DNA_KEYS)
    for i in range(dim):
        col = [v[i] for v in raw_vectors]
        m = sum(col) / n
        var = sum((x - m) ** 2 for x in col) / n
        means.append(m)
        stds.append(math.sqrt(var))

    normalized = [_normalize(v, means, stds) for v in raw_vectors]

    pool = {
        "means": means,
        "stds": stds,
        "vectors": normalized,
        "winners": winners,
        "pnls": pnls,
    }
    try:
        await redis_client.cache_set_json(
            cache_key, pool, ttl_seconds=settings.trade_dna_cache_ttl_secs,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "trade_dna.cache_write_failed",
            strategy_id=str(strategy_id), side=side, error=str(exc),
        )
    return pool


def _normalize(vec: list[float], means: list[float], stds: list[float]) -> list[float]:
    out: list[float] = []
    for v, m, s in zip(vec, means, stds, strict=True):
        out.append((v - m) / s if s > 0 else 0.0)
    return out


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


def _euclidean(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


# JSON helpers exposed for callers that want to log the result inline.
def result_to_json(result: DNAResult) -> str:
    return json.dumps(result.to_payload_dict(), separators=(",", ":"))


__all__ = [
    "DNAMatch",
    "DNAResult",
    "MAX_POOL_SIZE",
    "evaluate",
    "is_enabled",
    "result_to_json",
]
