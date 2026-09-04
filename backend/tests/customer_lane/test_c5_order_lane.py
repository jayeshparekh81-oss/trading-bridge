"""C5 — per-customer order lane isolation. The tests that must never be deleted."""
from __future__ import annotations

import ast
import inspect
import os
import pathlib
import socket
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.brokers import customer_dhan as cd
from app.core.security import encrypt_credential
from app.db.models.customer_lane import CustomerBrokerLink, CustomerLinkStatus

pytestmark = [pytest.mark.postgres, pytest.mark.asyncio]

NOW = datetime(2026, 9, 3, 4, 0, tzinfo=UTC)
DB_URL = os.environ.get(
    "CL_SCRATCH_URL",
    "postgresql+asyncpg://trading_bridge_test:test_password_do_not_use_in_prod"
    "@localhost:5433/cl_scratch",
)


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine(DB_URL, future=True)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
        await s.rollback()
    await engine.dispose()


@pytest.fixture(autouse=True)
def _armed(monkeypatch):
    """Arm the lane INSIDE the tests only. The default stays off."""
    monkeypatch.setenv("CUSTOMER_LANE_ORDER_ENABLED", "1")


async def _customer(s, *, token: str, proxy: str | None, ip: str | None = None,
                    connected: bool = True) -> uuid.UUID:
    cid = uuid.uuid4()
    await s.execute(text("INSERT INTO users (id,email,password_hash) VALUES (:i,:e,'x')"),
                    {"i": cid, "e": f"c5-{cid}@test.local"})
    link = CustomerBrokerLink(customer_id=cid, broker_client_id=f"CL-{token}")
    if connected:
        link.status = CustomerLinkStatus.CONNECTED
        link.access_token_enc = encrypt_credential(token)
        link.token_expires_at = NOW + timedelta(hours=8)
        link.last_connected_at = NOW - timedelta(hours=1)
    else:
        link.status = CustomerLinkStatus.NEVER_CONNECTED
    link.proxy_url = proxy
    link.assigned_static_ip = ip
    s.add(link)
    await s.flush()
    return cid


ORDER = {"symbol": "BSE", "side": "BUY", "quantity": 1, "productType": "CNC"}


async def test_lane_carries_only_its_own_token_and_ip(session):
    a = await _customer(session, token="TOKEN-A", proxy="http://proxy-a:8080", ip="1.1.1.1")
    b = await _customer(session, token="TOKEN-B", proxy="http://proxy-b:8080", ip="2.2.2.2")

    lane_a = await cd.build_lane(session, a, at=NOW)
    lane_b = await cd.build_lane(session, b, at=NOW)

    ha, hb = lane_a._auth_headers(), lane_b._auth_headers()
    assert ha["access-token"] == "TOKEN-A"
    assert hb["access-token"] == "TOKEN-B"
    assert ha["access-token"] != hb["access-token"]

    assert lane_a.egress.proxy_url == "http://proxy-a:8080"
    assert lane_b.egress.proxy_url == "http://proxy-b:8080"
    assert lane_a.egress.static_ip != lane_b.egress.static_ip

    # B's identity must appear NOWHERE in A's prepared order.
    prepared = await lane_a.place_order(a, ORDER)
    blob = repr(prepared) + repr(prepared.egress) + str(prepared.payload)
    for leak in ("TOKEN-B", "proxy-b", "2.2.2.2"):
        assert leak not in blob, f"{leak} leaked into customer A's order"
    assert prepared.egress.proxy_url == "http://proxy-a:8080"


async def test_order_for_another_customer_is_refused(session):
    a = await _customer(session, token="TOKEN-A", proxy="http://proxy-a:8080")
    b = await _customer(session, token="TOKEN-B", proxy="http://proxy-b:8080")
    lane_a = await cd.build_lane(session, a, at=NOW)
    with pytest.raises(cd.CustomerMismatch):
        await lane_a.place_order(b, ORDER)


async def test_missing_egress_fails_closed_never_falls_back(session):
    """The dangerous default would be the shared IP. It must refuse instead."""
    c = await _customer(session, token="TOKEN-C", proxy=None)
    with pytest.raises(cd.EgressNotConfigured):
        await cd.build_lane(session, c, at=NOW)


async def test_disconnected_customer_gets_no_lane(session):
    c = await _customer(session, token="T", proxy="http://p:8080", connected=False)
    with pytest.raises(cd.CustomerNotConnected):
        await cd.build_lane(session, c, at=NOW)


async def test_lane_refuses_while_disarmed(session, monkeypatch):
    a = await _customer(session, token="TOKEN-A", proxy="http://proxy-a:8080")
    lane = await cd.build_lane(session, a, at=NOW)
    monkeypatch.setenv("CUSTOMER_LANE_ORDER_ENABLED", "0")
    with pytest.raises(cd.LaneDisarmed):
        await lane.place_order(a, ORDER)


async def test_fno_mis_is_refused(session):
    a = await _customer(session, token="TOKEN-A", proxy="http://proxy-a:8080")
    lane = await cd.build_lane(session, a, at=NOW)
    with pytest.raises(cd.ProductNotAllowed):
        await lane.place_order(a, {"instrument": "FUTIDX", "productType": "MIS"})
    ok = await lane.place_order(a, {"instrument": "FUTIDX", "productType": "NRML"})
    assert ok.dry_run is True


async def test_no_order_can_actually_be_sent_in_this_run(session):
    """TWO barriers stand in front of a real send, and both must hold. The OUTER one
    is egress (it refuses an unproven identity); the INNER one is _transmit, which is
    unimplemented. Assert the outer refuses, then that the inner still raises even if
    the outer were ever satisfied."""
    from app.domains.customer_lane.egress import EgressUnverified

    a = await _customer(session, token="TOKEN-A", proxy="http://proxy-a:8080")
    lane = await cd.build_lane(session, a, at=NOW)

    with pytest.raises(EgressUnverified):
        await lane.place_order(a, ORDER, dry_run=False)

    prepared = await lane.place_order(a, ORDER, dry_run=True)
    with pytest.raises(NotImplementedError):
        await lane._transmit(prepared)


async def test_lane_makes_no_network_call(session, monkeypatch):
    local = {"127.0.0.1", "::1", "localhost"}
    real = socket.socket.connect

    def guarded(self, address, *a, **k):
        host = address[0] if isinstance(address, tuple) else address
        if host not in local:
            raise AssertionError(f"egress attempted: {host!r}")
        return real(self, address, *a, **k)

    monkeypatch.setattr(socket.socket, "connect", guarded)
    a = await _customer(session, token="TOKEN-A", proxy="http://proxy-a:8080")
    lane = await cd.build_lane(session, a, at=NOW)
    await lane.place_order(a, ORDER)


async def test_token_is_not_reachable_as_a_public_attribute(session):
    a = await _customer(session, token="TOKEN-A", proxy="http://proxy-a:8080")
    lane = await cd.build_lane(session, a, at=NOW)
    assert "TOKEN-A" not in repr(lane)
    public = [v for k, v in vars(lane).items() if not k.startswith("_")]
    assert "TOKEN-A" not in str(public)


def test_ast_factory_requires_customer_id_with_no_default():
    src = pathlib.Path("app/brokers/customer_dhan.py").read_text()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.AsyncFunctionDef) and n.name == "build_lane")
    args = [a.arg for a in fn.args.args]
    assert args == ["session", "customer_id"], args
    assert fn.args.defaults == [], "build_lane must not default customer_id"

    place = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.AsyncFunctionDef) and n.name == "place_order")
    assert "customer_id" in [a.arg for a in place.args.args], \
        "place_order must name the customer it is acting for"
    assert place.args.defaults == [], "place_order's customer_id must not default"


def test_ast_customer_lane_does_not_touch_the_live_broker_module():
    src = pathlib.Path("app/brokers/customer_dhan.py").read_text()
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            assert not n.module.endswith("brokers.dhan"), "must not import the live adapter"
        if isinstance(n, ast.Import):
            for al in n.names:
                assert not al.name.endswith("brokers.dhan")


def test_transmit_is_the_only_send_seam_and_it_raises():
    src = inspect.getsource(cd.CustomerOrderLane._transmit)
    assert "NotImplementedError" in src
    body = pathlib.Path("app/brokers/customer_dhan.py").read_text()
    for verb in ("requests.post", "httpx.post", "aiohttp", "urlopen"):
        assert verb not in body, f"a real send path ({verb}) exists in the lane"
