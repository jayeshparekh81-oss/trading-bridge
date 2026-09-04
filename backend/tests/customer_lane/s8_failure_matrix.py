"""S8 — nine failure injections plus a 25-customer scale sim. Prints real results."""
from __future__ import annotations

import asyncio, os, time, uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.brokers import customer_dhan as cd
from app.core.security import encrypt_credential
from app.db.models.customer_lane import (CustomerBrokerLink, CustomerLinkStatus,
                                         CustomerNotificationLog, LadderStep)
from app.domains.customer_lane import egress as eg, kill_switch as ks
from app.domains.customer_lane.connect import consume_link, issue_link
from app.domains.customer_lane.connection import is_connected
from app.domains.customer_lane.ladder import run_step
from app.domains.customer_lane.status import founder_board, board_summary

DB = os.environ["CL_SCRATCH_URL"]
NOW = datetime(2026, 9, 3, 4, 0, tzinfo=UTC)
TDAY = date(2026, 9, 3)
ORDER = {"symbol": "BSE", "side": "BUY", "quantity": 1, "productType": "CNC"}
results = []


def rec(n, name, expected, got, ok):
    results.append((n, name, expected, got, ok))


async def mk(s, tok="T", *, proxy="http://p:8080", connected=True, expires_h=8):
    cid = uuid.uuid4()
    await s.execute(text("INSERT INTO users (id,email,password_hash) VALUES (:i,:e,'x')"),
                    {"i": cid, "e": f"s8-{cid}@t.local"})
    l = CustomerBrokerLink(customer_id=cid, broker_client_id=f"C-{tok}", proxy_url=proxy,
                           assigned_static_ip="10.0.0.9")
    if connected:
        l.status = CustomerLinkStatus.CONNECTED
        l.access_token_enc = encrypt_credential(tok)
        l.token_expires_at = NOW + timedelta(hours=expires_h)
        l.last_connected_at = NOW - timedelta(hours=1)
    s.add(l)
    await s.flush()
    return cid


async def main():
    os.environ["CUSTOMER_LANE_ORDER_ENABLED"] = "1"
    os.environ["CUSTOMER_LANE_LADDER_ENABLED"] = "1"
    os.environ.pop("CUSTOMER_LANE_KILL_ALL", None)
    engine = create_async_engine(DB, future=True)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as s:
        # 1 token expires mid-session
        c = await mk(s, "EXP", expires_h=1)
        later = NOW + timedelta(hours=2)
        try:
            await cd.build_lane(s, c, at=later); got, ok = "built a lane", False
        except cd.CustomerNotConnected as e:
            got, ok = f"refused ({(await is_connected(s,c,at=later)).reason})", True
        rec(1, "token expires mid-session", "refuse", got, ok)

        # 2 customer revokes -> FAILED
        c = await mk(s, "REV")
        (await s.execute(select(CustomerBrokerLink).where(
            CustomerBrokerLink.customer_id == c))).scalar_one().status = CustomerLinkStatus.FAILED
        await s.flush()
        try:
            await cd.build_lane(s, c, at=NOW); got, ok = "built a lane", False
        except cd.CustomerNotConnected:
            got, ok = "refused (last_attempt_failed)", True
        rec(2, "customer revokes consent", "refuse", got, ok)

        # 3 no broker link row at all
        cid = uuid.uuid4()
        await s.execute(text("INSERT INTO users (id,email,password_hash) VALUES (:i,:e,'x')"),
                        {"i": cid, "e": f"s8-{cid}@t.local"})
        await s.flush()
        try:
            await cd.build_lane(s, cid, at=NOW); got, ok = "built a lane", False
        except cd.CustomerNotConnected:
            got, ok = "refused (no_broker_link)", True
        rec(3, "broker link row missing", "refuse", got, ok)

        # 4 token ciphertext corrupted
        c = await mk(s, "CORRUPT")
        (await s.execute(select(CustomerBrokerLink).where(
            CustomerBrokerLink.customer_id == c))).scalar_one().access_token_enc = "not-fernet"
        await s.flush()
        st = await is_connected(s, c, at=NOW)
        try:
            await cd.build_lane(s, c, at=NOW); got, ok = "built a lane", False
        except cd.CustomerNotConnected:
            got, ok = f"refused ({st.reason}), no crash", st.reason == "token_undecryptable"
        rec(4, "token ciphertext corrupted", "refuse, no crash", got, ok)

        # 5 proxy removed mid-session
        c = await mk(s, "NOPROXY")
        (await s.execute(select(CustomerBrokerLink).where(
            CustomerBrokerLink.customer_id == c))).scalar_one().proxy_url = None
        await s.flush()
        try:
            await cd.build_lane(s, c, at=NOW); got, ok = "built a lane", False
        except cd.EgressNotConfigured:
            got, ok = "refused (no fallback to shared IP)", True
        rec(5, "dedicated egress removed", "refuse, never fall back", got, ok)

        # 6 global kill mid-session
        c = await mk(s, "KILL")
        lane = await cd.build_lane(s, c, at=NOW)
        await lane.place_order(c, ORDER)
        os.environ["CUSTOMER_LANE_KILL_ALL"] = "1"
        try:
            await lane.place_order(c, ORDER); got, ok = "order still prepared", False
        except ks.LaneKilled:
            got, ok = "refused without restart", True
        os.environ.pop("CUSTOMER_LANE_KILL_ALL", None)
        rec(6, "global kill mid-session", "refuse immediately", got, ok)

        # 7 concurrent taps on one connect link
        c = await mk(s, "TAP", connected=False)
        link = await issue_link(s, c, trading_date=TDAY, now=NOW)
        r1 = await consume_link(s, link.raw_token, trading_date=TDAY, now=NOW)
        r2 = await consume_link(s, link.raw_token, trading_date=TDAY, now=NOW)
        wins = sum(1 for r in (r1, r2) if r.ok)
        rec(7, "same link tapped twice", "exactly 1 wins", f"{wins} won ({r2.reason})", wins == 1)

        # 8 duplicate ladder fire (beat fires twice)
        c = await mk(s, "DUP", connected=False)
        await run_step(s, LadderStep.R1, trading_date=TDAY, now=NOW)
        await run_step(s, LadderStep.R1, trading_date=TDAY, now=NOW)
        n = (await s.execute(select(CustomerNotificationLog).where(
            CustomerNotificationLog.customer_id == c,
            CustomerNotificationLog.step == LadderStep.R1))).scalars().all()
        rec(8, "beat fires the same rung twice", "1 row", f"{len(n)} row(s)", len(n) == 1)

        # 9 naive (tz-less) datetime
        c = await mk(s, "NAIVE")
        try:
            st = await is_connected(s, c, at=datetime(2026, 9, 3, 4, 0))
            got, ok = f"handled (connected={st.connected})", st.connected is True
        except TypeError as e:
            got, ok = f"CRASH: {e}", False
        rec(9, "naive datetime passed in", "handled, no crash", got, ok)

        await s.rollback()

    # ---- 25-customer scale sim ----
    async with maker() as s:
        ids, toks = [], {}
        for i in range(25):
            tok = f"TOKEN-{i:02d}"
            cid = await mk(s, tok, proxy=f"http://proxy-{i:02d}:8080",
                           connected=(i % 5 != 0))
            ids.append(cid); toks[cid] = tok
        t0 = time.perf_counter()
        for step in (LadderStep.R1, LadderStep.R2, LadderStep.CALL, LadderStep.RED):
            await run_step(s, step, trading_date=TDAY, now=NOW)
        board = await founder_board(s, ids, trading_date=TDAY, now=NOW)
        leaks = 0
        for cid in ids:
            st = await is_connected(s, cid, at=NOW)
            if not st.connected:
                continue
            lane = await cd.build_lane(s, cid, at=NOW)
            if lane._auth_headers()["access-token"] != toks[cid]:
                leaks += 1
            p = await lane.place_order(cid, ORDER)
            for other, ot in toks.items():
                if other != cid and (ot in repr(p) or ot in str(p.egress)):
                    leaks += 1
        dt = time.perf_counter() - t0
        rows = (await s.execute(select(CustomerNotificationLog).where(
            CustomerNotificationLog.customer_id.in_(ids)))).scalars().all()
        await s.rollback()

    print("\n=== S8 FAILURE INJECTION MATRIX ===")
    print(f"{'#':<3}{'scenario':<34}{'expected':<28}{'observed':<40}{'verdict'}")
    print("-" * 122)
    for n, name, exp, got, ok in results:
        print(f"{n:<3}{name:<34}{exp:<28}{got:<40}{'PASS' if ok else 'FAIL'}")
    print("-" * 122)
    print(f"{sum(1 for r in results if r[4])}/{len(results)} passed\n")

    print("=== S8 SCALE SIM: 25 CUSTOMERS ===")
    print(f"  customers                : 25 (20 connected, 5 never connected)")
    print(f"  ladder rungs run         : R1, R2, CALL, RED")
    print(f"  notification rows written: {len(rows)}  (expect 20 = 5 disconnected x 4 rungs)")
    print(f"  board summary            : {board_summary(board)}")
    print(f"  cross-customer leaks     : {leaks}")
    print(f"  wall clock               : {dt:.2f}s")
    print(f"  VERDICT                  : "
          f"{'PASS' if leaks == 0 and len(rows) == 20 else 'FAIL'}")
    await engine.dispose()

asyncio.run(main())
