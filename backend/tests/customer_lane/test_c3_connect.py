"""C3 — one-tap connect. The invariants that must never regress."""
from __future__ import annotations

import ast
import asyncio
import logging
import os
import pathlib
import socket
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models.customer_lane import (ConnectLinkStatus, CustomerBrokerLink,
                                         CustomerConnectLink, CustomerLinkStatus)
from app.domains.customer_lane import auth as lane_auth
from app.domains.customer_lane.connect import (complete_connection, consume_link,
                                               hash_token, issue_link)
from app.domains.customer_lane.connection import is_connected

pytestmark = [pytest.mark.postgres, pytest.mark.asyncio]

DB_URL = os.environ.get(
    "CL_SCRATCH_URL",
    "postgresql+asyncpg://trading_bridge_test:test_password_do_not_use_in_prod"
    "@localhost:5433/cl_scratch",
)


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine(DB_URL, future=True)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
        await s.rollback()
    await engine.dispose()

TDAY = date(2026, 9, 3)
NOW = datetime(2026, 9, 3, 2, 0, tzinfo=UTC)


async def _customer(session) -> uuid.UUID:
    cid = uuid.uuid4()
    await session.execute(
        text("INSERT INTO users (id,email,password_hash) VALUES (:i,:e,'x')"),
        {"i": cid, "e": f"c3-{cid}@test.local"})
    session.add(CustomerBrokerLink(customer_id=cid,
                                   status=CustomerLinkStatus.NEVER_CONNECTED))
    await session.flush()
    return cid


async def test_raw_token_is_never_persisted(db_session):
    cid = await _customer(db_session)
    link = await issue_link(db_session, cid, trading_date=TDAY, now=NOW)

    row = (await db_session.execute(select(CustomerConnectLink).where(
        CustomerConnectLink.customer_id == cid))).scalar_one()
    assert row.token_hash == hash_token(link.raw_token)
    assert link.raw_token not in row.token_hash

    # The raw token must not appear ANYWHERE in the table, in any column.
    hit = (await db_session.execute(
        text("SELECT count(*) FROM customer_connect_link "
             "WHERE token_hash LIKE :p"), {"p": f"%{link.raw_token}%"})).scalar()
    assert hit == 0, "raw token found in the database"


async def test_repr_redacts_the_token(db_session):
    cid = await _customer(db_session)
    link = await issue_link(db_session, cid, trading_date=TDAY, now=NOW)
    assert link.raw_token not in repr(link)
    assert "<redacted>" in repr(link)
    tok = lane_auth.BrokerToken("SECRET-TOKEN-VALUE", NOW)
    assert "SECRET-TOKEN-VALUE" not in repr(tok)


async def test_token_never_reaches_the_log(db_session, caplog):
    cid = await _customer(db_session)
    with caplog.at_level(logging.DEBUG, logger="customer_lane"):
        link = await issue_link(db_session, cid, trading_date=TDAY, now=NOW)
        await consume_link(db_session, link.raw_token, trading_date=TDAY, now=NOW)
        await consume_link(db_session, link.raw_token, trading_date=TDAY, now=NOW)
    blob = "\n".join(r.getMessage() for r in caplog.records)
    assert link.raw_token not in blob
    assert hash_token(link.raw_token) not in blob


async def test_single_use(db_session):
    cid = await _customer(db_session)
    link = await issue_link(db_session, cid, trading_date=TDAY, now=NOW)

    first = await consume_link(db_session, link.raw_token, trading_date=TDAY, now=NOW)
    assert first.ok and first.customer_id == cid

    second = await consume_link(db_session, link.raw_token, trading_date=TDAY, now=NOW)
    assert not second.ok
    assert second.reason == "already_consumed"
    assert second.customer_id is None


async def test_same_day_only(db_session):
    cid = await _customer(db_session)
    link = await issue_link(db_session, cid, trading_date=TDAY, now=NOW)
    res = await consume_link(db_session, link.raw_token,
                             trading_date=TDAY + timedelta(days=1),
                             now=NOW + timedelta(days=1))
    assert not res.ok and res.reason == "wrong_trading_date"


async def test_expired_link_refused(db_session):
    cid = await _customer(db_session)
    link = await issue_link(db_session, cid, trading_date=TDAY, now=NOW)
    res = await consume_link(db_session, link.raw_token, trading_date=TDAY,
                             now=link.expires_at + timedelta(seconds=1))
    assert not res.ok and res.reason == "expired"


async def test_link_issued_after_the_open_is_still_usable(db_session):
    """A customer connecting mid-day MUST be able to. The 09:15 cutoff governs the
    ladder and the join rule, not link validity: clamping here would make a mid-day
    link dead on arrival and contradict status.MID_DAY_JOIN_RULE."""
    cid = await _customer(db_session)
    late = datetime(2026, 9, 3, 6, 0, tzinfo=UTC)  # 11:30 IST, well after the open
    link = await issue_link(db_session, cid, trading_date=TDAY, now=late)
    assert link.expires_at == late + timedelta(minutes=30)
    res = await consume_link(db_session, link.raw_token, trading_date=TDAY, now=late)
    assert res.ok and res.customer_id == cid


async def test_link_never_outlives_its_own_trading_day(db_session):
    """The TTL is the limiter, but a link can never cross into the next day."""
    cid = await _customer(db_session)
    late = datetime(2026, 9, 3, 18, 40, tzinfo=UTC)  # 00:10 IST on 4 Sep
    link = await issue_link(db_session, cid, trading_date=TDAY, now=late)
    assert link.expires_at == datetime(2026, 9, 3, 18, 29, 59, tzinfo=UTC)


async def test_unknown_token_refused(db_session):
    res = await consume_link(db_session, "not-a-real-token", trading_date=TDAY, now=NOW)
    assert not res.ok and res.reason == "unknown_token"


async def test_one_customers_link_never_connects_another(db_session):
    a = await _customer(db_session)
    b = await _customer(db_session)
    link_a = await issue_link(db_session, a, trading_date=TDAY, now=NOW)
    res = await consume_link(db_session, link_a.raw_token, trading_date=TDAY, now=NOW)
    assert res.customer_id == a and res.customer_id != b

    await complete_connection(db_session, res.customer_id,
                              await lane_auth.get_provider().exchange(a, {}), now=NOW)
    assert (await is_connected(db_session, a, at=NOW)).connected is True
    assert (await is_connected(db_session, b, at=NOW)).connected is False


async def test_connect_makes_no_network_call(db_session, monkeypatch):
    """Nothing may LEAVE THE BOX. The scratch Postgres on loopback is not egress;
    any other destination is, and must never be reached during connect."""
    local = {"127.0.0.1", "::1", "localhost"}
    real_connect = socket.socket.connect

    def guarded(self, address, *a, **k):
        host = address[0] if isinstance(address, tuple) else address
        if host not in local:
            raise AssertionError(f"egress attempted during connect: {host!r}")
        return real_connect(self, address, *a, **k)

    monkeypatch.setattr(socket.socket, "connect", guarded)

    cid = await _customer(db_session)
    link = await issue_link(db_session, cid, trading_date=TDAY, now=NOW)
    res = await consume_link(db_session, link.raw_token, trading_date=TDAY, now=NOW)
    token = await lane_auth.get_provider().exchange(cid, {})
    await complete_connection(db_session, res.customer_id, token, now=NOW)
    assert (await is_connected(db_session, cid, at=NOW)).connected is True


async def test_stored_token_is_encrypted_not_plaintext(db_session):
    cid = await _customer(db_session)
    token = lane_auth.BrokerToken("PLAINTEXT-TOKEN-123", NOW + timedelta(hours=8))
    await complete_connection(db_session, cid, token, now=NOW)
    raw = (await db_session.execute(
        text("SELECT access_token_enc FROM customer_broker_link "
             "WHERE customer_id = :c"), {"c": cid})).scalar()
    assert raw is not None
    assert "PLAINTEXT-TOKEN-123" not in raw


async def test_dhan_partner_provider_fails_closed():
    p = lane_auth.DhanPartnerAuthProvider()
    assert p.credentials_available is False
    with pytest.raises(lane_auth.PartnerCredentialsMissing):
        p.consent_url(uuid.uuid4(), "tok")
    with pytest.raises(lane_auth.PartnerCredentialsMissing):
        await p.exchange(uuid.uuid4(), {})


async def test_partner_refuses_even_with_credentials_while_egress_disarmed(monkeypatch):
    monkeypatch.setenv("DHAN_PARTNER_ID", "pid")
    monkeypatch.setenv("DHAN_PARTNER_SECRET", "psecret")
    monkeypatch.delenv("CUSTOMER_LANE_ALLOW_PARTNER_NETWORK", raising=False)
    p = lane_auth.DhanPartnerAuthProvider()
    assert p.credentials_available is True
    with pytest.raises(lane_auth.PartnerNetworkDisabled):
        p.consent_url(uuid.uuid4(), "tok")


async def test_default_provider_is_the_stub():
    assert lane_auth.get_provider().name == "stub"


async def test_unknown_provider_fails_closed(monkeypatch):
    monkeypatch.setenv("CUSTOMER_LANE_AUTH_PROVIDER", "definitely-not-real")
    with pytest.raises(lane_auth.PartnerCredentialsMissing):
        lane_auth.get_provider()


async def test_ast_no_credential_fields_anywhere_in_the_lane():
    """We never hold a customer password, PIN or TOTP seed. Prove it structurally."""
    banned = {"password", "pin", "totp", "totp_seed", "mpin", "secret_answer"}
    root = pathlib.Path("app/domains/customer_lane")
    offenders = []
    for f in sorted(root.glob("*.py")):
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.arg):
                names = [node.arg]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names = [node.target.id]
            for n in names:
                low = n.lower()
                if any(b == low or low.startswith(b + "_") for b in banned):
                    offenders.append(f"{f.name}:{n}")
    assert offenders == [], f"customer credential field found: {offenders}"
