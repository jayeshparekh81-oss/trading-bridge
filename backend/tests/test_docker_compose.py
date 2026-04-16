"""Structural validation of the project's ``docker-compose.yml``.

This doesn't spin up Docker — it parses the YAML and asserts on the
shape. Running containers is covered by the integration suite that lives
outside this module's scope.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"


@pytest.fixture(scope="module")
def compose() -> dict[str, Any]:
    """Parse the compose file once per module."""
    assert COMPOSE_FILE.is_file(), f"missing {COMPOSE_FILE}"
    with COMPOSE_FILE.open() as fh:
        data = yaml.safe_load(fh)
    assert isinstance(data, dict)
    return data


def test_required_services_present(compose: dict[str, Any]) -> None:
    expected = {"postgres", "redis", "backend", "celery_worker", "celery_beat"}
    assert expected <= set(compose["services"].keys())


def test_postgres_image_and_volume(compose: dict[str, Any]) -> None:
    pg = compose["services"]["postgres"]
    assert pg["image"].startswith("postgres:16")
    assert any(v.startswith("postgres_data:") for v in pg["volumes"])
    assert "healthcheck" in pg


def test_redis_image_and_volume(compose: dict[str, Any]) -> None:
    redis = compose["services"]["redis"]
    assert "redis" in redis["image"] and "alpine" in redis["image"]
    assert any(v.startswith("redis_data:") for v in redis["volumes"])
    assert "healthcheck" in redis


def test_backend_depends_on_postgres_redis(compose: dict[str, Any]) -> None:
    backend = compose["services"]["backend"]
    deps = backend["depends_on"]
    # Long-form condition: service_healthy
    assert deps["postgres"]["condition"] == "service_healthy"
    assert deps["redis"]["condition"] == "service_healthy"
    assert backend["env_file"].endswith(".env")
    assert "8000:8000" in backend["ports"]


def test_celery_services_share_backend_image(compose: dict[str, Any]) -> None:
    svcs = compose["services"]
    backend_image = svcs["backend"]["image"]
    assert svcs["celery_worker"]["image"] == backend_image
    assert svcs["celery_beat"]["image"] == backend_image
    # Commands distinguish worker vs beat.
    worker_cmd = " ".join(svcs["celery_worker"]["command"])
    beat_cmd = " ".join(svcs["celery_beat"]["command"])
    assert "worker" in worker_cmd
    assert "beat" in beat_cmd


def test_shared_network_and_named_volumes(compose: dict[str, Any]) -> None:
    assert "bridge_network" in compose["networks"]
    assert "postgres_data" in compose["volumes"]
    assert "redis_data" in compose["volumes"]


def test_all_services_on_bridge_network(compose: dict[str, Any]) -> None:
    for name, svc in compose["services"].items():
        assert "bridge_network" in svc.get("networks", []), (
            f"{name} is not attached to bridge_network"
        )


def test_dockerfile_present_and_multistage() -> None:
    dockerfile = REPO_ROOT / "backend" / "Dockerfile"
    assert dockerfile.is_file()
    text = dockerfile.read_text()
    assert "FROM python:3.11-slim AS builder" in text
    assert "FROM python:3.11-slim AS runtime" in text
    assert "USER appuser" in text
    assert "HEALTHCHECK" in text
    assert "uvloop" in text
