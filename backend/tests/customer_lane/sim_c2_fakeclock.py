"""C2 receipt — fake-clock full-day simulation, 5 synthetic customers.

Prints the ACTUAL customer_notification_log table at the end. Rolls everything back.
"""
from __future__ import annotations

import asyncio, os, uuid
from datetime import UTC, date, datetime, timedelta

os.environ.setdefault("CUSTOMER_LANE_LADDER_ENABLED", "1")

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import encrypt_credential
from app.db.models.customer_lane import (CustomerBrokerLink, CustomerLinkStatus,
                                         CustomerNotificationLog, LadderStep)
from app.domains.customer_lane.ladder import run_step

DB = os.environ["CL_SCRATCH_URL"]
TDAY = date(2026, 9, 3)
IST = timedelta(hours=5, minutes=30)

def ist(h, m):
    return datetime(2026, 9, 3, h, m, tzinfo=UTC) - IST

STEPS = [(LadderStep.R1, ist(7, 45)), (LadderStep.R2, ist(8, 30)),
         (LadderStep.CALL, ist(8, 55)), (LadderStep.RED, ist(9, 5))]

PLAN = [("C1 connects 07:30 (before R1)", ist(7, 30)),
        ("C2 connects 07:50 (after R1)",  ist(7, 50)),
        ("C3 connects 08:52 (after R2)",  ist(8, 52)),
        ("C4 connects 09:02 (after CALL)", ist(9, 2)),
        ("C5 never connects", None)]


async def main():
    engine = create_async_engine(DB, future=True)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        ids = []
        for label, _ in PLAN:
            cid = uuid.uuid4()
            await s.execute(text("INSERT INTO users (id,email,password_hash) VALUES (:i,:e,'x')"),
                            {"i": cid, "e": f"sim-{cid}@test.local"})
            s.add(CustomerBrokerLink(customer_id=cid,
                                     status=CustomerLinkStatus.NEVER_CONNECTED))
            ids.append((label, cid))
        await s.flush()
        mine = {cid for _, cid in ids}

        for step, when in STEPS:
            for (label, connect_at), (_, cid) in zip(PLAN, ids):
                if connect_at is not None and connect_at <= when:
                    link = (await s.execute(select(CustomerBrokerLink).where(
                        CustomerBrokerLink.customer_id == cid))).scalar_one()
                    if link.status != CustomerLinkStatus.CONNECTED:
                        link.status = CustomerLinkStatus.CONNECTED
                        link.access_token_enc = encrypt_credential("tok")
                        link.token_expires_at = connect_at + timedelta(hours=8)
                        link.last_connected_at = connect_at
            await s.flush()
            await run_step(s, step, trading_date=TDAY, now=when)

        rows = (await s.execute(
            select(CustomerNotificationLog)
            .where(CustomerNotificationLog.customer_id.in_(mine))
            .order_by(CustomerNotificationLog.sent_at,
                      CustomerNotificationLog.customer_id))).scalars().all()

        label_of = {cid: lab.split()[0] for lab, cid in ids}
        print("\n=== ACTUAL customer_notification_log (5 synthetic customers) ===")
        print(f"{'cust':<6} {'sent_at (UTC)':<20} {'channel':<9} {'step':<7} {'trading_date':<13} {'outcome'}")
        print("-" * 86)
        for r in rows:
            print(f"{label_of[r.customer_id].split()[0]:<6} {str(r.sent_at)[:19]:<20} {r.channel:<9} {r.step.value:<7} "
                  f"{str(r.trading_date):<13} {r.outcome}")
        print("-" * 86)
        print(f"total rows: {len(rows)}\n")
        print("=== per-customer summary vs expectation ===")
        exp = {"C1 connects 07:30 (before R1)": [],
               "C2 connects 07:50 (after R1)": ["R1"],
               "C3 connects 08:52 (after R2)": ["R1", "R2"],
               "C4 connects 09:02 (after CALL)": ["R1", "R2", "CALL"],
               "C5 never connects": ["R1", "R2", "CALL", "RED"]}
        ok = True
        for lab, cid in ids:
            got = [r.step.value for r in rows if r.customer_id == cid]
            good = got == exp[lab]
            ok &= good
            print(f"  {lab:<34} got={got!s:<34} expected={exp[lab]!s:<30} {'OK' if good else 'MISMATCH'}")
        print(f"\nSIMULATION {'PASS' if ok else 'FAIL'}")
        await s.rollback()
    await engine.dispose()

asyncio.run(main())
