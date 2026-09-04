"""C6 — kill switches and egress verification. BLAST RADIUS is the point."""
from __future__ import annotations

import ast
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
from app.domains.customer_lane import egress as eg
from app.domains.customer_lane import kill_switch as ks
from app.domains.customer_lane.connection import is_connected

pytestmark = [pytest.mark.postgres, pytest.mark.asyncio]

NOW = datetime(2026, 9, 3, 4, 0, tzinfo=UTC)
DB_URL = os.environ.get(
    "CL_SCRATCH_URL",
    "postgresql+asyncpg://trading_bridge_test:test_password_do_not_use_in_prod"
    "@localhost:5433/cl_scratch",
)
ORDER = {"symbol": "BSE", "side": "BUY", "quantity": 1, "productType": "CNC"}


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
    monkeypatch.setenv("CUSTOMER_LANE_ORDER_ENABLED", "1")
    monkeypatch.delenv("CUSTOMER_LANE_KILL_ALL", raising=False)


async def _customer(s, token: str) -> uuid.UUID:
    cid = uuid.uuid4()
    await s.execute(text("INSERT INTO users (id,email,password_hash) VALUES (:i,:e,'x')"),
                    {"i": cid, "e": f"c6-{cid}@test.local"})
    s.add(CustomerBrokerLink(
        customer_id=cid, status=CustomerLinkStatus.CONNECTED,
        access_token_enc=encrypt_credential(token),
        token_expires_at=NOW + timedelta(hours=8), last_connected_at=NOW - timedelta(hours=1),
        proxy_url=f"http://proxy-{token}:8080", assigned_static_ip=f"10.0.0.{len(token)}"))
    await s.flush()
    return cid


# ---------------- global kill ----------------

async def test_global_kill_stops_every_customer(session, monkeypatch):
    a, b = await _customer(session, "A"), await _customer(session, "B")
    monkeypatch.setenv("CUSTOMER_LANE_KILL_ALL", "1")
    for cid in (a, b):
        with pytest.raises(ks.LaneKilled):
            await cd.build_lane(session, cid, at=NOW)


async def test_global_kill_is_seen_without_a_restart(session, monkeypatch):
    """A worker up for hours must see the kill at the next order, not at restart."""
    a = await _customer(session, "A")
    lane = await cd.build_lane(session, a, at=NOW)
    assert (await lane.place_order(a, ORDER)).dry_run is True
    monkeypatch.setenv("CUSTOMER_LANE_KILL_ALL", "1")
    with pytest.raises(ks.LaneKilled):
        await lane.place_order(a, ORDER)


async def test_global_kill_stops_even_dry_run_preparation(session, monkeypatch):
    a = await _customer(session, "A")
    lane = await cd.build_lane(session, a, at=NOW)
    monkeypatch.setenv("CUSTOMER_LANE_KILL_ALL", "1")
    with pytest.raises(ks.LaneKilled):
        await lane.place_order(a, ORDER, dry_run=True)


# ---------------- per-customer kill: blast radius ----------------

async def test_killing_one_customer_leaves_the_others_trading(session):
    a, b = await _customer(session, "A"), await _customer(session, "B")
    await ks.kill_customer(session, a, reason="c6 test")

    with pytest.raises(cd.CustomerNotConnected):
        await cd.build_lane(session, a, at=NOW)

    lane_b = await cd.build_lane(session, b, at=NOW)
    assert (await lane_b.place_order(b, ORDER)).customer_id == b
    assert (await is_connected(session, b, at=NOW)).connected is True


async def test_killed_customer_reports_link_disabled(session):
    a = await _customer(session, "A")
    await ks.kill_customer(session, a, reason="c6 test")
    st = await is_connected(session, a, at=NOW)
    assert st.connected is False
    assert st.reason == "link_disabled"


async def test_revive_requires_a_fresh_connect(session):
    """Revival must not silently trust an old token."""
    a = await _customer(session, "A")
    await ks.kill_customer(session, a, reason="c6 test")
    await ks.revive_customer(session, a)
    st = await is_connected(session, a, at=NOW)
    assert st.connected is False
    assert st.reason == "never_connected"


# ---------------- blast radius: the founder's own money ----------------

def test_kill_switch_cannot_reach_the_live_path():
    """Killing the customer lane must never stop the founder's BSE strategy."""
    src = pathlib.Path("app/domains/customer_lane/kill_switch.py").read_text()
    tree = ast.parse(src)
    forbidden = ("brokers.dhan", "strategy_executor", "webhook", "live_loop",
                 "runner", "direct_exit")
    for n in ast.walk(tree):
        mods = []
        if isinstance(n, ast.ImportFrom) and n.module:
            mods = [n.module]
        elif isinstance(n, ast.Import):
            mods = [a.name for a in n.names]
        for m in mods:
            assert not any(f in m for f in forbidden), \
                f"kill switch reaches the live path via {m}"


def test_global_kill_env_var_is_lane_scoped():
    """The name must not collide with the estate-wide kill switch."""
    src = pathlib.Path("app/domains/customer_lane/config.py").read_text()
    assert "CUSTOMER_LANE_KILL_ALL" in src
    other = pathlib.Path("app/api/kill_switch.py")
    if other.exists():
        assert "CUSTOMER_LANE_KILL_ALL" not in other.read_text(), \
            "customer-lane kill leaked into the estate kill switch"


# ---------------- egress ----------------

async def test_egress_is_unverified_while_disarmed():
    v = await eg.verify_egress(uuid.uuid4(), "10.0.0.1", "http://p:8080")
    assert v.verified is False
    assert v.reason == "verification_disarmed"


async def test_unverified_egress_is_a_refusal_not_a_warning():
    v = await eg.verify_egress(uuid.uuid4(), "10.0.0.1", "http://p:8080")
    with pytest.raises(eg.EgressUnverified):
        eg.enforce(v)


async def test_egress_probe_is_unavailable_and_makes_no_network_call(monkeypatch):
    monkeypatch.setenv("CUSTOMER_LANE_EGRESS_VERIFY_ENABLED", "1")
    local = {"127.0.0.1", "::1", "localhost"}
    real = socket.socket.connect

    def guarded(self, address, *a, **k):
        host = address[0] if isinstance(address, tuple) else address
        if host not in local:
            raise AssertionError(f"egress probe left the box: {host!r}")
        return real(self, address, *a, **k)

    monkeypatch.setattr(socket.socket, "connect", guarded)
    v = await eg.verify_egress(uuid.uuid4(), "10.0.0.1", "http://p:8080")
    assert v.verified is False and v.reason == "probe_unavailable"


async def test_real_send_is_blocked_by_egress_before_it_can_transmit(session):
    a = await _customer(session, "A")
    lane = await cd.build_lane(session, a, at=NOW)
    with pytest.raises(eg.EgressUnverified):
        await lane.place_order(a, ORDER, dry_run=False)


async def test_dry_run_is_not_blocked_by_egress(session):
    """A dry run never leaves the box, so it has no identity to prove."""
    a = await _customer(session, "A")
    lane = await cd.build_lane(session, a, at=NOW)
    assert (await lane.place_order(a, ORDER, dry_run=True)).dry_run is True
