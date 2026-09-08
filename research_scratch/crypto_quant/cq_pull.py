"""Pull 6 months of BTCUSDT perp aggTrades. Read-only, ceiling-enforced."""
import datetime, json
from pathlib import Path
import cq_guards as G

END = datetime.date(2026, 9, 6)
DAYS = 183
BASE = "https://data.binance.vision/data/futures/um/daily/aggTrades/BTCUSDT"
recs = []
for i in range(DAYS):
    d = END - datetime.timedelta(days=DAYS - 1 - i)
    s = d.isoformat()
    dest = Path("raw") / f"BTCUSDT-aggTrades-{s}.zip"
    if dest.exists():
        recs.append({"day": s, "status": 200, "bytes": dest.stat().st_size, "cached": True})
        continue
    try:
        st, path, n = G.get(f"{BASE}/BTCUSDT-aggTrades-{s}.zip",
                            tag=f"agg:{s}", stream_to=dest)
    except G.DiskCeilingReached as e:
        print(f"  STOP at {s}: {e}", flush=True)
        recs.append({"day": s, "status": "DISK_CEILING_STOP", "error": str(e)})
        break
    recs.append({"day": s, "status": st, "bytes": n, "cached": False})
    if st != 200:
        print(f"  {s} HTTP {st}", flush=True)
    if i % 20 == 0:
        st2 = G.stats()
        print(f"  [{i+1:3d}/{DAYS}] {s} used={st2['requests_used']} "
              f"dl={st2['bytes_downloaded']/1024**3:.3f} GiB", flush=True)
ok = [r for r in recs if r.get("status") == 200]
tot = sum(r.get("bytes", 0) for r in ok)
G.STATE.mkdir(parents=True, exist_ok=True)
json.dump({"window_end": END.isoformat(), "days_requested": DAYS,
           "days_ok": len(ok), "days_missing": [r["day"] for r in recs if r.get("status") != 200],
           "bytes_total": tot, "gib_total": tot / 1024**3,
           "per_day": recs, "stats": G.stats()},
          open("receipts/cp_pull.json", "w"), indent=2)
print(f"  PULL DONE: {len(ok)}/{DAYS} days, {tot/1024**3:.3f} GiB")
