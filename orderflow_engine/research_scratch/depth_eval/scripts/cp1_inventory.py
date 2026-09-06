"""CP1 — data inventory from S3 (read-only, streamed; nothing stored locally except this JSON)."""
import json, re, sys, time, datetime as dt
from pathlib import Path
from pyarrow import fs
import pyarrow.parquet as pq
import pyarrow.compute as pc

BUCKET = "tradetri-orderflow-data-383136686940-ap-south-1-an"; PREFIX = "orderflow/r0"
LO, HI = "2026-07-13", "2026-08-17"; INSTS = ("NIFTY_FUT", "BANKNIFTY_FUT")
DE = Path(__file__).resolve().parent.parent
s3 = fs.S3FileSystem(region="ap-south-1")
t0 = time.time()
top = s3.get_file_info(fs.FileSelector(f"{BUCKET}/{PREFIX}", recursive=False))
all_dates = sorted(i.path.rsplit("/", 1)[-1] for i in top if i.type == fs.FileType.Directory)
dates = [d for d in all_dates if LO <= d <= HI]
print(f"  date prefixes in bucket: {len(all_dates)} ({all_dates[0]} .. {all_dates[-1]}); in window {LO}..{HI}: {len(dates)}")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
def ist(ns): return dt.datetime.fromtimestamp(ns / 1e9, IST).strftime("%H:%M:%S.%f")[:-3]
inv, manifest = [], []
for d in dates:
    objs = s3.get_file_info(fs.FileSelector(f"{BUCKET}/{PREFIX}/{d}/depth", recursive=True, allow_not_found=True))
    files = [o for o in objs if o.type == fs.FileType.File]
    for inst in INSTS:
        cons = [o for o in files if re.search(rf"/depth/{inst}_\d+\.parquet$", o.path)]
        parts = [o for o in files if f"/depth/parts/{inst}_" in o.path]
        if not cons:
            inv.append({"date": d, "inst": inst, "status": "NO CONSOLIDATED OBJECT", "parts": len(parts)}); continue
        for o in cons:
            pf = pq.ParquetFile(s3.open_input_file(o.path))
            names = pf.schema_arrow.names
            tbl = pf.read(columns=["ts_recv_ns", "side", "security_id"])
            sides = {}
            for sv in sorted(set(tbl.column("side").to_pylist())):
                m = pc.equal(tbl.column("side"), sv); sub = tbl.filter(m).column("ts_recv_ns")
                lo, hi = pc.min(sub).as_py(), pc.max(sub).as_py()
                sides[str(sv)] = {"rows": sub.length(), "first_ns": lo, "last_ns": hi, "first_ist": ist(lo), "last_ist": ist(hi), "span_h": round((hi - lo) / 3.6e12, 3)}
            sids = sorted(set(tbl.column("security_id").to_pylist()))
            rec = {"date": d, "inst": inst, "key": o.path, "bytes": o.size, "rows": pf.metadata.num_rows, "cols": len(names),
                   "deepest_level": max(int(x.split("_")[1]) for x in names if x.startswith("price_")), "sid_in_name": int(re.search(rf"{inst}_(\d+)\.parquet$", o.path).group(1)),
                   "sid_in_column": sids, "sides": sides, "parts_objects": len(parts)}
            inv.append(rec); manifest.append({"key": o.path, "bytes": o.size, "rows": pf.metadata.num_rows})
            b, a = list(sides.values())[0], (list(sides.values())[1] if len(sides) > 1 else None)
            print(f"  {d} {inst:<13} rows={rec['rows']:>7} cols={rec['cols']} L{rec['deepest_level']} sid(name/col)={rec['sid_in_name']}/{sids} "
                  f"side{list(sides)[0]}: {b['rows']} {b['first_ist']}-{b['last_ist']} | side{list(sides)[1] if a else '-'}: {a['rows'] if a else '-'} {a['first_ist'] if a else ''}-{a['last_ist'] if a else ''} | parts={len(parts)} | {o.size/1e6:.1f} MB")
tot_bytes = sum(m["bytes"] for m in manifest); tot_rows = sum(m["rows"] for m in manifest)
print(f"  objects read: {len(manifest)} | total S3 bytes of those objects: {tot_bytes:,} ({tot_bytes/2**30:.3f} GiB) | rows: {tot_rows:,} | {time.time()-t0:.0f}s")
(DE / "cp1_inventory.json").write_text(json.dumps(inv, indent=1)); (DE / "cp1_manifest.json").write_text(json.dumps(manifest, indent=1))
