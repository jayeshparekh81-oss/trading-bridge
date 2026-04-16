"""Unit tests for :mod:`app.core.performance`."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterator
from typing import Any

import pytest

from app.core import performance


@pytest.fixture
def captured_samples() -> Iterator[list[dict[str, Any]]]:
    """Replace the latency observer with a list collector."""
    samples: list[dict[str, Any]] = []

    def collector(
        operation: str, latency_ms: float, success: bool, tags: dict[str, Any]
    ) -> None:
        samples.append(
            {
                "operation": operation,
                "latency_ms": latency_ms,
                "success": success,
                "tags": tags,
            }
        )

    previous = performance.get_latency_observer()
    performance.register_latency_observer(collector)
    yield samples
    performance.register_latency_observer(previous)


class TestLatencyTimer:
    def test_records_latency_for_successful_block(
        self, captured_samples: list[dict[str, Any]]
    ) -> None:
        with performance.LatencyTimer("op", tags={"k": "v"}) as t:
            time.sleep(0.005)
        assert t.success is True
        assert t.latency_ms >= 4.5
        assert captured_samples[0]["operation"] == "op"
        assert captured_samples[0]["success"] is True
        assert captured_samples[0]["tags"] == {"k": "v"}

    def test_records_failure_on_exception(
        self, captured_samples: list[dict[str, Any]]
    ) -> None:
        with pytest.raises(RuntimeError):
            with performance.LatencyTimer("op") as t:
                raise RuntimeError("boom")
        assert t.success is False
        assert captured_samples[0]["success"] is False

    def test_no_tags_defaults_to_empty(
        self, captured_samples: list[dict[str, Any]]
    ) -> None:
        with performance.LatencyTimer("op"):
            pass
        assert captured_samples[0]["tags"] == {}


class TestTrackLatencyAsync:
    async def test_decorates_coroutine(
        self, captured_samples: list[dict[str, Any]]
    ) -> None:
        @performance.track_latency("svc.fetch", tags={"broker": "fyers"})
        async def fetch() -> str:
            await asyncio.sleep(0.001)
            return "ok"

        result = await fetch()
        assert result == "ok"
        sample = captured_samples[0]
        assert sample["operation"] == "svc.fetch"
        assert sample["success"] is True
        assert sample["tags"] == {"broker": "fyers"}
        assert sample["latency_ms"] >= 0.5

    async def test_records_failure_for_async_exception(
        self, captured_samples: list[dict[str, Any]]
    ) -> None:
        @performance.track_latency("svc.boom")
        async def boom() -> None:
            raise ValueError("nope")

        with pytest.raises(ValueError):
            await boom()
        assert captured_samples[0]["success"] is False
        assert captured_samples[0]["operation"] == "svc.boom"

    async def test_default_operation_uses_qualname(
        self, captured_samples: list[dict[str, Any]]
    ) -> None:
        @performance.track_latency()
        async def some_op() -> int:
            return 42

        assert await some_op() == 42
        assert captured_samples[0]["operation"].endswith("some_op")


class TestTrackLatencySync:
    def test_decorates_sync_function(
        self, captured_samples: list[dict[str, Any]]
    ) -> None:
        @performance.track_latency("sync.op")
        def double(x: int) -> int:
            return x * 2

        assert double(3) == 6
        assert captured_samples[0]["operation"] == "sync.op"
        assert captured_samples[0]["success"] is True

    def test_sync_failure_recorded(
        self, captured_samples: list[dict[str, Any]]
    ) -> None:
        @performance.track_latency("sync.boom")
        def boom() -> None:
            raise KeyError("bad")

        with pytest.raises(KeyError):
            boom()
        assert captured_samples[0]["success"] is False


class TestObserverHook:
    def test_observer_failure_does_not_break_caller(
        self, captured_samples: list[dict[str, Any]]
    ) -> None:
        def faulty(*_args: Any, **_kw: Any) -> None:
            raise RuntimeError("observer crashed")

        performance.register_latency_observer(faulty)
        try:
            with performance.LatencyTimer("op"):
                pass  # Must not raise even though observer raises.
        finally:
            performance.register_latency_observer(None)
        assert performance.get_latency_observer() is None

    def test_register_and_unregister(self) -> None:
        def obs(*_a: Any, **_kw: Any) -> None:
            return None

        performance.register_latency_observer(obs)
        assert performance.get_latency_observer() is obs
        performance.register_latency_observer(None)
        assert performance.get_latency_observer() is None
