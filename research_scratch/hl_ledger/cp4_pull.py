"""CP4 — bulk pull for every cohort wallet. Read-only, first-party only.

Pagination: userFillsByTime caps at 2000 rows and returns fills ASCENDING
from startTime (oldest-first) -- measured empirically in the CP4 self-check,
not assumed. We therefore walk FORWARD: fix endTime at now and step startTime
up to (newest time seen + 1) each round, until a page comes back short, empty,
or we hit the per-wallet page budget.

An earlier version of this file walked BACKWARDS on the assumption that the
endpoint returned newest-first. That was wrong and silently capped 39 of 50
active wallets at exactly 2000 fills with truncated=False. The self-check
caught it; this is the corrected run.

Budget: the declared run cap is 2000 requests and is enforced in hl_client.
MAX_FILL_PAGES bounds each wallet so one hyperactive wallet cannot eat the cap.
A wallet stopped by the budget is marked truncated=True and its fill-derived
metrics are LOWER BOUNDS. That is recorded, never hidden.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import hl_client as hl

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
DAY_MS = 86_400_000
WINDOW_DAYS = 30
MAX_FILL_PAGES = 20
MAX_FUNDING_PAGES = 2
PAGE_FULL = 2000
FUNDING_FULL = 500


def pull_fills(addr: str, start_ms: int, end_ms: int) -> tuple[list, dict]:
    seen: dict[int, dict] = {}
    dup = 0
    pages = 0
    calls = 0
    cursor = start_ms
    truncated = False
    while pages < MAX_FILL_PAGES:
        st, resp, _ = hl.post({"type": "userFillsByTime", "user": addr,
                               "startTime": cursor, "endTime": end_ms},
                              tag=f"fills:{addr[:10]}:p{pages}")
        calls += 1
        pages += 1
        if st != 200 or not isinstance(resp, list) or not resp:
            break
        for f in resp:
            k = f.get("tid")
            if k is None:
                k = hash((f.get("hash"), f.get("oid"), f.get("time"), f.get("sz")))
            if k in seen:
                dup += 1
            else:
                seen[k] = f
        newest = max(int(f["time"]) for f in resp)
        if len(resp) < PAGE_FULL or newest >= end_ms:
            break
        cursor = newest + 1
        if pages >= MAX_FILL_PAGES:
            truncated = True
    fills = sorted(seen.values(), key=lambda f: int(f["time"]))
    return fills, {"pages": pages, "calls": calls, "duplicates_removed": dup,
                   "truncated": truncated}


def pull_funding(addr: str, start_ms: int, end_ms: int) -> tuple[list, dict]:
    seen: dict[tuple, dict] = {}
    dup = 0
    calls = 0
    cursor = end_ms
    truncated = False
    for p in range(MAX_FUNDING_PAGES):
        st, resp, _ = hl.post({"type": "userFunding", "user": addr,
                               "startTime": start_ms, "endTime": cursor},
                              tag=f"funding:{addr[:10]}:p{p}")
        calls += 1
        if st != 200 or not isinstance(resp, list) or not resp:
            break
        for r in resp:
            d = r.get("delta", {})
            k = (r.get("time"), d.get("coin"), d.get("usdc"))
            if k in seen:
                dup += 1
            else:
                seen[k] = r
        oldest = min(int(r["time"]) for r in resp)
        if len(resp) < FUNDING_FULL or oldest <= start_ms:
            break
        cursor = oldest - 1
        if p == MAX_FUNDING_PAGES - 1:
            truncated = True
    rows = sorted(seen.values(), key=lambda r: int(r["time"]))
    return rows, {"calls": calls, "duplicates_removed": dup, "truncated": truncated}


def main() -> int:
    cohort = json.load(open(HERE / "COHORT.json"))
    wallets = [w["wallet"] for w in cohort["wallets"]]
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - WINDOW_DAYS * DAY_MS
    receipts = []
    for i, addr in enumerate(wallets, 1):
        d = RAW / addr
        d.mkdir(parents=True, exist_ok=True)
        fills, fmeta = pull_fills(addr, start_ms, end_ms)
        (d / "fills.json").write_text(json.dumps(fills))
        fund, gmeta = pull_funding(addr, start_ms, end_ms)
        (d / "funding.json").write_text(json.dumps(fund))
        st, state, _ = hl.post({"type": "clearinghouseState", "user": addr},
                               tag=f"state:{addr[:10]}")
        (d / "clearinghouse.json").write_text(json.dumps(state))
        times = [int(f["time"]) for f in fills]
        rec = {
            "wallet": addr,
            "fills": len(fills),
            "earliest_time": min(times) if times else None,
            "latest_time": max(times) if times else None,
            "fill_pages": fmeta["pages"],
            "fill_duplicates_removed": fmeta["duplicates_removed"],
            "fills_truncated": fmeta["truncated"],
            "funding_rows": len(fund),
            "funding_duplicates_removed": gmeta["duplicates_removed"],
            "funding_truncated": gmeta["truncated"],
            "clearinghouse_status": st,
            "api_calls": fmeta["calls"] + gmeta["calls"] + 1,
            "bytes_on_disk": sum((d / f).stat().st_size
                                 for f in ("fills.json", "funding.json", "clearinghouse.json")),
            "zero_fills": len(fills) == 0,
        }
        receipts.append(rec)
        print(f"  [{i:3d}/{len(wallets)}] {addr[:12]} fills={len(fills):5d} "
              f"pages={fmeta['pages']:2d} dup={fmeta['duplicates_removed']:4d} "
              f"trunc={fmeta['truncated']!s:5s} fund={len(fund):4d} "
              f"used={hl.stats()['requests_used']}", flush=True)
        if hl.stats()["remaining"] < 40:
            print("  STOPPING: approaching the declared request cap", flush=True)
            break
    hl.save({"checkpoint": "CP4", "window_days": WINDOW_DAYS,
             "start_ms": start_ms, "end_ms": end_ms,
             "max_fill_pages_per_wallet": MAX_FILL_PAGES,
             "wallets_attempted": len(receipts), "wallets_in_cohort": len(wallets),
             "per_wallet": receipts,
             "requests_used": hl.stats()["requests_used"],
             "requests_cap": hl.stats()["hard_cap"]},
            "receipts/cp4.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
