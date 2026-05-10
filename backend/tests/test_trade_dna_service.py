"""Tests for :mod:`app.services.trade_dna_service`.

Six paths covering the design proposal commitments:
* default OFF short-circuits everything
* cold start (< min_history closed pos) returns INSUFFICIENT_HISTORY
* all-winners pool → score ≈ +100, high confidence
* all-losers pool → score ≈ −100, high confidence
* mixed pool → moderate score, lower confidence
* winner threshold ₹500 — pnl=200 counts as loser, pnl=600 counts as winner
* cache hit short-circuits the DB on the second call
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio

from app.core import config as app_config
from app.core import redis_client
from app.services import _dna_vector
from app.services import trade_dna_service as svc


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture(autouse=True)
async def _patch_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[fake_aioredis.FakeRedis]:
    client = fake_aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: client)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    app_config.get_settings.cache_clear()
    yield
    app_config.get_settings.cache_clear()


def _enable_dna(
    monkeypatch: pytest.MonkeyPatch,
    *,
    min_history: int = 5,
    top_k: int = 5,
    winner_threshold: float = 500.0,
    lookback_days: int = 30,
) -> None:
    monkeypatch.setenv("TRADE_DNA_ENABLED", "true")
    monkeypatch.setenv("TRADE_DNA_MIN_HISTORY", str(min_history))
    monkeypatch.setenv("TRADE_DNA_TOP_K", str(top_k))
    monkeypatch.setenv("TRADE_DNA_WINNER_THRESHOLD_INR", str(winner_threshold))
    monkeypatch.setenv("TRADE_DNA_LOOKBACK_DAYS", str(lookback_days))
    app_config.get_settings.cache_clear()


def _flat_indicators(seed: float) -> dict[str, float]:
    """Indicators that vary slightly per seed so the rolling window has
    positive std (otherwise normalization yields zeros)."""
    return {k: 1.0 + 0.01 * (seed + i) for i, k in enumerate(_dna_vector.DNA_KEYS)}


class _FakeSession:
    """Stand-in for AsyncSession that bypasses the DB.

    The trade_dna service goes Redis-first and only hits the DB on cache
    miss. We pre-seed Redis directly with the normalized pool, so this
    session must never actually be invoked. If a test does hit it, we
    fail loud — that's a regression in the cache contract.
    """

    async def execute(self, *_args: Any, **_kwargs: Any) -> Any:  # pragma: no cover
        raise AssertionError("DB query attempted — Redis pool was not pre-seeded")


async def _seed_pool(
    redis: fake_aioredis.FakeRedis,
    strategy_id: str,
    side: str,
    *,
    winners: int,
    losers: int,
    winner_pnl: float = 1000.0,
    loser_pnl: float = -500.0,
) -> None:
    """Pre-seed Redis with a synthetic normalized history pool.

    Winner vectors live in one corner of the 22-d space (1.0s), losers
    in the opposite corner (-1.0s), so cosine similarity to a probe
    vector is unambiguous.
    """
    dim = len(_dna_vector.DNA_KEYS)
    win_vec = [1.0] * dim
    loss_vec = [-1.0] * dim
    pool = {
        "means": [0.0] * dim,
        "stds": [1.0] * dim,
        "vectors": [win_vec] * winners + [loss_vec] * losers,
        "winners": [True] * winners + [False] * losers,
        "pnls": [winner_pnl] * winners + [loser_pnl] * losers,
    }
    key = svc._history_cache_key(strategy_id, side)
    await redis_client.cache_set_json(key, pool, ttl_seconds=3600)


# ═══════════════════════════════════════════════════════════════════════
# Default OFF
# ═══════════════════════════════════════════════════════════════════════


class TestDefaultOff:
    async def test_is_enabled_false_by_default(self) -> None:
        assert svc.is_enabled() is False

    async def test_evaluate_short_circuits_when_disabled(self) -> None:
        result = await svc.evaluate(_FakeSession(), uuid4(), "long", _flat_indicators(0))
        assert result.enabled is False
        assert result.score is None
        assert result.note == "DISABLED"

    async def test_no_redis_writes_when_disabled(
        self, _patch_redis: fake_aioredis.FakeRedis
    ) -> None:
        await svc.evaluate(_FakeSession(), uuid4(), "long", _flat_indicators(0))
        assert await _patch_redis.keys("*") == []


# ═══════════════════════════════════════════════════════════════════════
# Cold start
# ═══════════════════════════════════════════════════════════════════════


class TestColdStart:
    async def test_insufficient_history_note(
        self,
        _patch_redis: fake_aioredis.FakeRedis,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _enable_dna(monkeypatch, min_history=20)
        sid = str(uuid4())
        await _seed_pool(_patch_redis, sid, "long", winners=5, losers=2)

        result = await svc.evaluate(_FakeSession(), sid, "long", _flat_indicators(0))
        assert result.enabled is True
        assert result.score is None
        assert result.win_prob is None
        assert result.confidence is None
        assert result.sample_size == 7
        assert result.note.startswith("INSUFFICIENT_HISTORY:7/20")


# ═══════════════════════════════════════════════════════════════════════
# Scoring math
# ═══════════════════════════════════════════════════════════════════════


class TestScoring:
    async def test_all_winners_pool_yields_max_score(
        self,
        _patch_redis: fake_aioredis.FakeRedis,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _enable_dna(monkeypatch, min_history=5, top_k=10)
        sid = str(uuid4())
        await _seed_pool(_patch_redis, sid, "long", winners=10, losers=0)

        # Probe vector identical to winner direction.
        indicators = {k: 0.5 for k in _dna_vector.DNA_KEYS}
        result = await svc.evaluate(_FakeSession(), sid, "long", indicators)

        assert result.enabled is True
        assert result.note == "OK"
        assert result.score == 100.0
        assert result.win_prob == 100.0
        assert result.winners == 10
        assert result.losers == 0
        assert result.confidence > 50.0
        assert len(result.top_matches) == 5
        assert all(m.is_winner for m in result.top_matches)

    async def test_all_losers_pool_yields_min_score(
        self,
        _patch_redis: fake_aioredis.FakeRedis,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _enable_dna(monkeypatch, min_history=5, top_k=10)
        sid = str(uuid4())
        await _seed_pool(_patch_redis, sid, "long", winners=0, losers=10)

        indicators = {k: 0.5 for k in _dna_vector.DNA_KEYS}
        result = await svc.evaluate(_FakeSession(), sid, "long", indicators)

        assert result.score == -100.0
        assert result.win_prob == 0.0
        assert result.winners == 0
        assert result.losers == 10
        assert result.confidence > 50.0

    async def test_mixed_pool_moderate_score(
        self,
        _patch_redis: fake_aioredis.FakeRedis,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _enable_dna(monkeypatch, min_history=5, top_k=10)
        sid = str(uuid4())
        # 6 winners + 4 losers, probe biased toward winners.
        await _seed_pool(_patch_redis, sid, "long", winners=6, losers=4)
        indicators = {k: 0.5 for k in _dna_vector.DNA_KEYS}
        result = await svc.evaluate(_FakeSession(), sid, "long", indicators)

        # Win prob is the *similarity-weighted* share of winners. With
        # the probe pointing toward winners, winners get higher sim
        # weight than their head-count share, so win_prob > 60.
        assert result.win_prob is not None and result.win_prob > 60.0
        assert result.score is not None and result.score > 20.0
        # Mixed outcome → confidence below the all-winners ceiling.
        assert result.confidence is not None and result.confidence < 100.0


# ═══════════════════════════════════════════════════════════════════════
# Winner threshold
# ═══════════════════════════════════════════════════════════════════════


class TestWinnerThreshold:
    """Validates the live DB-path classification — a closed position with
    pnl=₹200 is a *loser* (eaten by brokerage), pnl=₹600 is a *winner*.

    We test this by going through the cache miss path so the threshold
    logic in ``_load_history_pool`` runs."""

    async def test_winner_threshold_filters_scratch_trades(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _enable_dna(monkeypatch, min_history=2, winner_threshold=500.0)
        sid = str(uuid4())

        # Fake out the DB query by stubbing _load_history_pool's internals.
        # Easier: stub the session's execute() to return synthetic rows.
        class _Row:
            def __init__(self, payload: dict, pnl: float) -> None:
                self._t = (payload, pnl)

            def __iter__(self):
                return iter(self._t)

        class _Result:
            def __init__(self, rows: list[_Row]) -> None:
                self._rows = rows

            def all(self) -> list[_Row]:
                return self._rows

        class _StubSession:
            async def execute(self, _stmt: Any) -> _Result:
                payload = {"indicators": {k: 1.0 for k in _dna_vector.DNA_KEYS}}
                return _Result([
                    _Row(payload, 200.0),   # below threshold → loser
                    _Row(payload, 600.0),   # above threshold → winner
                    _Row(payload, 1500.0),  # winner
                    _Row(payload, -300.0),  # loser
                ])

        result = await svc.evaluate(
            _StubSession(), sid, "long", {k: 1.0 for k in _dna_vector.DNA_KEYS}
        )

        assert result.note == "OK"
        assert result.sample_size == 4
        # 2 winners (600, 1500) + 2 losers (200, -300).
        assert result.winners + result.losers == min(4, 5)  # top_k default 5, sample 4
        assert result.winners == 2
        assert result.losers == 2


# ═══════════════════════════════════════════════════════════════════════
# Cache behaviour
# ═══════════════════════════════════════════════════════════════════════


class TestCache:
    async def test_cache_hit_skips_db(
        self,
        _patch_redis: fake_aioredis.FakeRedis,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _enable_dna(monkeypatch, min_history=5)
        sid = str(uuid4())
        await _seed_pool(_patch_redis, sid, "long", winners=10, losers=0)

        # _FakeSession.execute() asserts — if cache hit works, never invoked.
        result = await svc.evaluate(
            _FakeSession(), sid, "long", _flat_indicators(0)
        )
        assert result.note == "OK"

    async def test_cache_key_isolates_by_side(
        self,
        _patch_redis: fake_aioredis.FakeRedis,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _enable_dna(monkeypatch, min_history=5)
        sid = str(uuid4())
        # Long pool: all winners. Short pool: empty (will need DB).
        await _seed_pool(_patch_redis, sid, "long", winners=10, losers=0)

        long_key = svc._history_cache_key(sid, "long")
        short_key = svc._history_cache_key(sid, "short")
        assert long_key != short_key
        # Use the public cache helper — bypasses the internal `cache:`
        # namespace prefix that direct redis access would have to mirror.
        assert await redis_client.cache_get_json(long_key) is not None
        assert await redis_client.cache_get_json(short_key) is None


# ═══════════════════════════════════════════════════════════════════════
# Result serialization
# ═══════════════════════════════════════════════════════════════════════


class TestResultPayload:
    async def test_to_payload_dict_is_json_safe(
        self,
        _patch_redis: fake_aioredis.FakeRedis,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _enable_dna(monkeypatch, min_history=5, top_k=3)
        sid = str(uuid4())
        await _seed_pool(_patch_redis, sid, "long", winners=5, losers=2)

        result = await svc.evaluate(_FakeSession(), sid, "long", _flat_indicators(0))
        payload = result.to_payload_dict()

        # Round-trip through json without TypeError.
        import json
        round_tripped = json.loads(json.dumps(payload))
        assert round_tripped["enabled"] is True
        assert round_tripped["winners"] == 3  # top_k=3 cap
        assert isinstance(round_tripped["top_matches"], list)
        assert all("similarity" in m for m in round_tripped["top_matches"])
