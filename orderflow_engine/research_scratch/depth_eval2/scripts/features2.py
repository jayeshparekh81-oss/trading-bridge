"""CP4 driver — compute deep-book features for every CP0-USABLE date (both instruments USABLE), streamed from S3.
Usage: python3 features2.py [features|features_recheck]"""
import json, sys, time
from pathlib import Path
D2 = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(D2)); from deep_book import compute_session
OUT = D2 / (sys.argv[1] if len(sys.argv) > 1 else "features"); OUT.mkdir(exist_ok=True)
cp0 = json.loads((D2 / "cp0_integrity.json").read_text())
usable_dates = sorted({r["date"] for r in cp0 if r.get("status") == "USABLE"} - {r["date"] for r in cp0 if r.get("status") != "USABLE"})
todo = [r for r in cp0 if r.get("status") == "USABLE" and r["date"] in usable_dates]
print(f"  usable dates (both instruments USABLE): {len(usable_dates)} -> {len(todo)} sessions", flush=True); summaries = []; t0 = time.time()
for r in todo:
    t1 = time.time(); out, s = compute_session(r["date"], r["inst"], r["key"], OUT / f"{r['date']}_{r['inst']}.parquet"); summaries.append(s)
    e = s["events"]; print(f"  {s['date']} {s['inst']:<13} rows={s['rows_in']:>7} bars_mid={s['bars_with_valid_mid']} crossed={s['crossed_at_bar_end']} walls app b/a={e['wall_appear_bid']}/{e['wall_appear_ask']} dis b/a={e['wall_disappear_bid']}/{e['wall_disappear_ask']} deep_refill b/a={e['deep_refill_bid']}/{e['deep_refill_ask']} {time.time()-t1:.0f}s", flush=True)
(OUT / "_summary.json").write_text(json.dumps(summaries, indent=1)); print(f"  {len(summaries)} sessions in {time.time()-t0:.0f}s -> {OUT}", flush=True)
