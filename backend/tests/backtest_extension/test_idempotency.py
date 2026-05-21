"""Idempotency hash unit tests."""

from __future__ import annotations

import uuid

from app.backtest_extension import idempotency


def test_engine_version_matches_version_module() -> None:
    """``ENGINE_VERSION`` is re-exported from ``_version.__engine_version__``
    (Day 7). The constant + accessor must both return that single source
    of truth."""
    from app.strategy_engine.backtest._version import __engine_version__

    assert idempotency.engine_version() == __engine_version__
    assert idempotency.ENGINE_VERSION == __engine_version__


def test_compute_hash_returns_64_hex_chars() -> None:
    h = idempotency.compute_hash(
        strategy_config={"id": "x"},
        symbols="NIFTY",
        date_range=("2026-01-01", "2026-02-01"),
    )
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_compute_hash_deterministic_for_same_input() -> None:
    args = {
        "strategy_config": {"id": "x", "indicators": [{"id": "ema_20"}]},
        "symbols": "NIFTY",
        "date_range": ("2026-01-01", "2026-02-01"),
    }
    h1 = idempotency.compute_hash(**args)
    h2 = idempotency.compute_hash(**args)
    assert h1 == h2


def test_compute_hash_invariant_under_dict_key_order() -> None:
    """Same data, different key order → same hash."""
    a = {"id": "x", "indicators": [{"id": "e1", "type": "ema"}]}
    b = {"indicators": [{"type": "ema", "id": "e1"}], "id": "x"}
    h1 = idempotency.compute_hash(
        strategy_config=a, symbols="NIFTY", date_range=("d1", "d2")
    )
    h2 = idempotency.compute_hash(
        strategy_config=b, symbols="NIFTY", date_range=("d1", "d2")
    )
    assert h1 == h2


def test_compute_hash_symbols_string_vs_single_list_equivalent() -> None:
    h_str = idempotency.compute_hash(
        strategy_config={"x": 1}, symbols="NIFTY", date_range=("d1", "d2")
    )
    h_list = idempotency.compute_hash(
        strategy_config={"x": 1}, symbols=["NIFTY"], date_range=("d1", "d2")
    )
    assert h_str == h_list


def test_compute_hash_symbols_list_order_invariant() -> None:
    h_a = idempotency.compute_hash(
        strategy_config={"x": 1},
        symbols=["NIFTY", "BANKNIFTY"],
        date_range=("d1", "d2"),
    )
    h_b = idempotency.compute_hash(
        strategy_config={"x": 1},
        symbols=["BANKNIFTY", "NIFTY"],
        date_range=("d1", "d2"),
    )
    assert h_a == h_b


def test_compute_hash_different_strategy_config_produces_different_hash() -> None:
    h_a = idempotency.compute_hash(
        strategy_config={"id": "a"}, symbols="NIFTY", date_range=("d1", "d2")
    )
    h_b = idempotency.compute_hash(
        strategy_config={"id": "b"}, symbols="NIFTY", date_range=("d1", "d2")
    )
    assert h_a != h_b


def test_compute_hash_different_date_range_produces_different_hash() -> None:
    h_a = idempotency.compute_hash(
        strategy_config={"x": 1}, symbols="NIFTY", date_range=("2026-01-01", "2026-02-01")
    )
    h_b = idempotency.compute_hash(
        strategy_config={"x": 1}, symbols="NIFTY", date_range=("2026-01-02", "2026-02-01")
    )
    assert h_a != h_b


def test_compute_hash_engine_version_bump_breaks_cache() -> None:
    h_v1 = idempotency.compute_hash(
        strategy_config={"x": 1}, symbols="NIFTY", date_range=("d1", "d2"),
        engine_version="v1",
    )
    h_v2 = idempotency.compute_hash(
        strategy_config={"x": 1}, symbols="NIFTY", date_range=("d1", "d2"),
        engine_version="v2",
    )
    assert h_v1 != h_v2


def test_compute_hash_extra_field_affects_hash() -> None:
    h_a = idempotency.compute_hash(
        strategy_config={"x": 1}, symbols="NIFTY", date_range=("d1", "d2")
    )
    h_b = idempotency.compute_hash(
        strategy_config={"x": 1},
        symbols="NIFTY",
        date_range=("d1", "d2"),
        extra={"cost": 0.5},
    )
    assert h_a != h_b


def test_compute_hash_strategy_id_route_produces_stable_hash() -> None:
    """strategy_id-by-reference path yields a stable hash."""
    sid = uuid.uuid4()
    h1 = idempotency.compute_hash_from_request(
        strategy_id=sid,
        strategy_config=None,
        symbol="NIFTY",
        timeframe="5m",
        start="2026-01-01",
        end="2026-02-01",
        initial_capital=100000.0,
        quantity=1.0,
        cost_settings={},
        ambiguity_mode="conservative",
    )
    h2 = idempotency.compute_hash_from_request(
        strategy_id=sid,
        strategy_config=None,
        symbol="NIFTY",
        timeframe="5m",
        start="2026-01-01",
        end="2026-02-01",
        initial_capital=100000.0,
        quantity=1.0,
        cost_settings={},
        ambiguity_mode="conservative",
    )
    assert h1 == h2


def test_compute_hash_different_strategy_ids_produce_different_hashes() -> None:
    sid1 = uuid.UUID("00000000-0000-0000-0000-000000000001")
    sid2 = uuid.UUID("00000000-0000-0000-0000-000000000002")
    h1 = idempotency.compute_hash_from_request(
        strategy_id=sid1,
        strategy_config=None,
        symbol="NIFTY",
        timeframe="5m",
        start="2026-01-01",
        end="2026-02-01",
        initial_capital=100000.0,
        quantity=1.0,
        cost_settings={},
        ambiguity_mode="conservative",
    )
    h2 = idempotency.compute_hash_from_request(
        strategy_id=sid2,
        strategy_config=None,
        symbol="NIFTY",
        timeframe="5m",
        start="2026-01-01",
        end="2026-02-01",
        initial_capital=100000.0,
        quantity=1.0,
        cost_settings={},
        ambiguity_mode="conservative",
    )
    assert h1 != h2


def test_compute_hash_invariant_to_quantity_float_vs_int() -> None:
    """1.0 and 1 hash identically because both pass through float()."""
    h_float = idempotency.compute_hash_from_request(
        strategy_id=uuid.UUID(int=1),
        strategy_config=None,
        symbol="NIFTY",
        timeframe="5m",
        start="2026-01-01",
        end="2026-02-01",
        initial_capital=100000.0,
        quantity=1.0,
        cost_settings={},
        ambiguity_mode="conservative",
    )
    h_int = idempotency.compute_hash_from_request(
        strategy_id=uuid.UUID(int=1),
        strategy_config=None,
        symbol="NIFTY",
        timeframe="5m",
        start="2026-01-01",
        end="2026-02-01",
        initial_capital=100000.0,
        quantity=1,  # type: ignore[arg-type]
        cost_settings={},
        ambiguity_mode="conservative",
    )
    assert h_float == h_int


def test_compute_hash_handles_pydantic_cost_settings() -> None:
    """Pydantic model_dump works alongside raw dict input."""
    from app.strategy_engine.backtest import CostSettings

    cs_model = CostSettings(fixed_cost=0.0, percent_cost=0.0)
    cs_dict = {
        "fixed_cost": 0.0,
        "percent_cost": 0.0,
        "slippage_percent": 0.0,
        "spread_percent": 0.0,
    }
    h_model = idempotency.compute_hash_from_request(
        strategy_id=uuid.UUID(int=1),
        strategy_config=None,
        symbol="NIFTY",
        timeframe="5m",
        start="2026-01-01",
        end="2026-02-01",
        initial_capital=100000.0,
        quantity=1.0,
        cost_settings=cs_model,
        ambiguity_mode="conservative",
    )
    h_dict = idempotency.compute_hash_from_request(
        strategy_id=uuid.UUID(int=1),
        strategy_config=None,
        symbol="NIFTY",
        timeframe="5m",
        start="2026-01-01",
        end="2026-02-01",
        initial_capital=100000.0,
        quantity=1.0,
        cost_settings=cs_dict,
        ambiguity_mode="conservative",
    )
    assert h_model == h_dict
