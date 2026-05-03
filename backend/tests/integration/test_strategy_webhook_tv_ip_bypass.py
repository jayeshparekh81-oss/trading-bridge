"""TradingView IP-allowlist HMAC bypass tests.

TradingView's free tier cannot HMAC-sign webhook payloads. Solution: a
fixed allowlist of TV's published egress IPs is granted bypass on the
HMAC verification step ONLY. Every other safety gate (rate limit,
idempotency, kill switch, user-active, max-trades, time-of-day) still
runs.

The IP source is :func:`app.api.strategy_webhook._resolve_client_ip`,
which prefers the middleware-resolved ``request.state.client_ip`` (set
after honouring ``X-Forwarded-For`` from a trusted proxy) and falls
back to the peer. Tests monkeypatch the resolver directly — middleware
XFF resolution is covered by :mod:`tests.test_security_middleware`.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from tests.integration.conftest import HMAC_HEADER, _sign


def _payload(*, action: str = "EXIT", signal_id: str | None = None) -> bytes:
    """EXIT skips the entry executor — keeps the bypass tests fast and
    deterministic. The bypass logic is in step 4 (HMAC); the executor
    isn't relevant to what we're verifying.

    Post direct-exit refactor (Sun 2026-05-03), EXIT requires a `side`.
    No open position exists in this test seed, so the handler will
    short-circuit with `ignored: no_open_position` after the bypass
    check — that's fine for what these tests assert (HMAC bypass only).
    """
    body: dict[str, Any] = {
        "action": action,
        "side": "long",
        "symbol": "NIFTY",
        "order_type": "market",
    }
    if signal_id is not None:
        body["signal_id"] = signal_id
    return json.dumps(body).encode("utf-8")


def _url(token: str) -> str:
    return f"/api/webhook/strategy/{token}"


# ═══════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════


class TestTvIpBypassesHmac:
    def test_tv_ip_without_hmac_returns_202(
        self,
        client: TestClient,
        seed: dict[str, Any],
        monkeypatch: Any,
    ) -> None:
        """Request from TradingView's published egress IP — no HMAC
        header, no in-body signature — is accepted with 202."""
        monkeypatch.setattr(
            "app.api.strategy_webhook._resolve_client_ip",
            lambda _request: "52.89.214.238",
        )

        body = _payload(action="EXIT", signal_id="tv-bypass-1")
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={"Content-Type": "application/json"},
        )

        assert resp.status_code == 202, resp.text
        data = resp.json()
        assert data["status"] == "accepted"
        assert "signal_id" in data


class TestNonTvIpStillRequiresHmac:
    def test_random_ip_without_hmac_returns_401(
        self,
        client: TestClient,
        seed: dict[str, Any],
        monkeypatch: Any,
    ) -> None:
        """An IP that is NOT in the TV allowlist gets the legacy
        missing-HMAC response — bypass is allowlist-only, not open."""
        monkeypatch.setattr(
            "app.api.strategy_webhook._resolve_client_ip",
            lambda _request: "1.2.3.4",
        )

        body = _payload(action="EXIT", signal_id="non-tv-1")
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={"Content-Type": "application/json"},
        )

        assert resp.status_code == 401, resp.text
        assert "Missing HMAC signature" in resp.json()["detail"]


class TestTvIpWithValidHmacAlsoWorks:
    def test_tv_ip_with_valid_hmac_returns_202(
        self,
        client: TestClient,
        seed: dict[str, Any],
        monkeypatch: Any,
    ) -> None:
        """A request that BOTH comes from a TV IP AND carries a valid
        HMAC is admitted. Bypass takes precedence (HMAC is skipped) but
        valid signatures don't trigger any false-failure path.

        Pinning this case so a future contributor can't accidentally
        invert the bypass and reject TV requests that happen to include
        a signature (e.g. once TV adds HMAC support and operators dual-
        send during a transition window).
        """
        monkeypatch.setattr(
            "app.api.strategy_webhook._resolve_client_ip",
            lambda _request: "34.212.75.30",
        )

        body = _payload(action="EXIT", signal_id="tv-with-hmac-1")
        resp = client.post(
            _url(seed["token_plain"]),
            content=body,
            headers={
                HMAC_HEADER: _sign(body),
                "Content-Type": "application/json",
            },
        )

        assert resp.status_code == 202, resp.text
        assert resp.json()["status"] == "accepted"
