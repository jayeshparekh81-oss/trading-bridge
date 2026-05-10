"""Phase 5B Part 2 — ``GET /api/strategies/indicators`` endpoint.

Self-contained tests: each builds a tiny FastAPI app holding only the
indicators router with an auth dependency override. No database, no
session machinery — the endpoint is metadata-only and never touches
SQLAlchemy.

Coverage:

    * shape           — response is a list and one row's keys match
                        the IndicatorMetadata wire schema (camelCase
                        aliases honoured).
    * size            — Phase 9's expansion is reflected (>= 100
                        entries) AND the response includes the 10
                        Phase 1 actives plus the 10 Phase 9 actives.
    * statuses        — both ACTIVE and COMING_SOON entries surface so
                        the frontend can grey out the latter.
    * routing safety  — `/indicators` resolves to this endpoint, NOT
                        the CRUD router's `/{strategy_id}` handler
                        (which would 422 trying to parse "indicators"
                        as a UUID).
    * auth required   — without an override the endpoint refuses with
                        401.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_active_user
from app.db.models.user import User
from app.strategy_engine.api import router as strategy_crud_router
from app.strategy_engine.api.indicators import router as indicators_router


def _stub_user() -> User:
    """A throwaway User instance used to satisfy the auth dependency.

    The endpoint reads the registry; it does not look up rows or
    permissions, so the user need not be persisted anywhere.
    """
    user = User(
        email="indicators-test@tradetri.com",
        password_hash="x",
        is_active=True,
    )
    user.id = uuid.uuid4()
    return user


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Tiny FastAPI app with the indicators + CRUD routers wired the
    same way ``main.py`` does — indicators registered FIRST so its
    literal ``/indicators`` path beats the CRUD router's
    ``/{strategy_id}`` UUID-typed catch-all."""
    app = FastAPI()
    app.include_router(indicators_router)
    app.include_router(strategy_crud_router)

    app.dependency_overrides[get_current_active_user] = _stub_user

    with TestClient(app) as c:
        yield c


# ─── Shape ────────────────────────────────────────────────────────────


def test_endpoint_returns_a_list_with_indicator_metadata_keys(
    client: TestClient,
) -> None:
    resp = client.get("/api/strategies/indicators")

    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert body, "registry must not be empty"
    first = body[0]
    # Required IndicatorMetadata fields with camelCase aliases.
    for key in (
        "id",
        "name",
        "category",
        "description",
        "inputs",
        "outputs",
        "chartType",
        "pineAliases",
        "difficulty",
        "status",
        "aiExplanation",
    ):
        assert key in first, f"missing key {key!r} in {first}"


# ─── Size + status mix ───────────────────────────────────────────────


def test_response_carries_phase_9_expanded_registry_with_active_and_coming_soon(
    client: TestClient,
) -> None:
    resp = client.get("/api/strategies/indicators")
    body = resp.json()

    # Phase 9 grew the registry past 100 entries.
    assert len(body) >= 100

    by_status: dict[str, list[dict[str, object]]] = {"active": [], "coming_soon": []}
    for row in body:
        status_val = row["status"]
        if status_val in by_status:
            by_status[status_val].append(row)

    # Both buckets non-empty so the UI's grey-out path has data.
    assert by_status["active"], "no ACTIVE indicators in response"
    assert by_status["coming_soon"], "no COMING_SOON indicators in response"

    # Phase 1's 10 actives + Phase 9's 10 actives all present.
    active_ids = {row["id"] for row in by_status["active"]}
    expected_active_subset = {
        # Phase 1
        "ema",
        "sma",
        "wma",
        "rsi",
        "macd",
        "bollinger_bands",
        "atr",
        "vwap",
        "obv",
        "volume_sma",
        # Phase 9 additions
        "adx",
        "dmi",
        "aroon",
        "trix",
        "ultimate_oscillator",
        "cmf",
        "force_index",
        "linear_regression",
        "pivot_points",
        "ichimoku",
    }
    assert expected_active_subset.issubset(active_ids)


# ─── Routing — /indicators wins over /{strategy_id} ───────────────────


def test_indicators_path_does_not_collide_with_strategy_crud_uuid_route(
    client: TestClient,
) -> None:
    """If routing order were wrong, the CRUD router's ``/{strategy_id}``
    would try to parse ``"indicators"`` as a UUID and 422.

    A clean 200 (with the right body shape) here proves the indicators
    router wins over the CRUD path-parameter route — exactly how
    ``main.py`` orders them.
    """
    resp = client.get("/api/strategies/indicators")
    assert resp.status_code == 200
    body = resp.json()
    # Sanity: the body is the indicator catalogue, not a CRUD-shaped error.
    assert isinstance(body, list)
    assert any(row.get("id") == "ema" for row in body)


# ─── Auth required ───────────────────────────────────────────────────


def test_endpoint_requires_authentication() -> None:
    """Drop the override → the dep raises 401."""
    app = FastAPI()
    app.include_router(indicators_router)
    with TestClient(app) as c:
        resp = c.get("/api/strategies/indicators")
        assert resp.status_code == 401
