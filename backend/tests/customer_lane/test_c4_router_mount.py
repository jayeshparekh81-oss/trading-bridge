"""The status API must be INVISIBLE unless explicitly armed."""
from __future__ import annotations

import importlib

import pytest


def _routes(monkeypatch, enabled: bool):
    monkeypatch.setenv("CUSTOMER_LANE_STATUS_API_ENABLED", "1" if enabled else "0")
    import app.main as main
    importlib.reload(main)
    return {getattr(r, "path", None) for r in main.create_app().routes}


def test_status_api_absent_when_disarmed(monkeypatch):
    paths = _routes(monkeypatch, False)
    assert not any(p and p.startswith("/api/customer-lane") for p in paths), \
        "customer-lane route mounted while the flag is off"


def test_status_api_present_when_armed(monkeypatch):
    paths = _routes(monkeypatch, True)
    assert "/api/customer-lane/me/status" in paths
    assert "/api/customer-lane/board" in paths


def test_arming_adds_only_customer_lane_routes(monkeypatch):
    off = _routes(monkeypatch, False)
    on = _routes(monkeypatch, True)
    added = on - off
    assert added and all(p.startswith("/api/customer-lane") for p in added), \
        f"arming changed unrelated routes: {added}"
    assert off - on == set(), "arming removed an existing route"
