#!/usr/bin/env python3
"""DEPTH -> S3 RECONCILIATION SWEEP. Additive: no edit to s3_backup.py, no rebuild, no restart.

WHY (measured 2026-08-16): R0's _backup() walks day_dir.rglob("*") at ~15:45 IST, right after
R0's own verify. The DEPTH recorder is still consolidating then — it closes 15:51-15:58 — so
8-11 of 18 depth finals per day are written AFTER the upload walk and are never backed up.
backup.json still says success:true because it never saw them. Those files then fail
parts_cleanup gate 5 ("S3 HEAD failed / size mismatch") and their parts/ shards are KEPT
forever, so the same race both starves S3 and blocks reclaim.

This sweep closes the loop from the other end: compare local consolidated depth FINALS against
S3 and upload only what is missing or size-mismatched. It uploads FINALS ONLY — never parts/.
Parts are proven-redundant scratch and uploading them frees nothing, because gate 5 checks S3
for the FINAL.

Verification is the same contract the 50-file rescue used:
  * put_object (single-part) so the ETag is a plain MD5, not a multipart composite
  * after upload: head_object ContentLength == local size AND ETag == local MD5
  * any mismatch -> reported as FAILED, never counted as backed up
Key convention taken verbatim from the day's own backup.json: orderflow/r0/<day>/depth/<name>.

READ-ONLY unless --apply. Default is a dry run.
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

BUCKET = "tradetri-orderflow-data-383136686940-ap-south-1-an"
PREFIX = "orderflow/r0"
REGION = "ap-south-1"
DATA = Path("/home/ubuntu/trading-bridge/orderflow_engine/data")


def md5_of(p: Path) -> str:
    h = hashlib.md5()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="depth_s3_reconcile")
    ap.add_argument("--days", required=True, help="comma-separated YYYY-MM-DD")
    ap.add_argument("--apply", action="store_true", help="actually upload (default: dry run)")
    a = ap.parse_args(argv)
    import boto3
    s3 = boto3.client("s3", region_name=REGION)

    grand = {"missing": 0, "bytes": 0, "uploaded": 0, "verified": 0, "failed": 0}
    for day in [d.strip() for d in a.days.split(",") if d.strip()]:
        ddir = DATA / day / "depth"
        if not ddir.is_dir():
            print(f"{day}: no depth dir — skipped"); continue
        finals = sorted(p for p in ddir.glob("*.parquet"))      # FINALS ONLY, never parts/
        todo = []
        for p in finals:
            key = f"{PREFIX}/{day}/depth/{p.name}"
            local = p.stat().st_size
            try:
                h = s3.head_object(Bucket=BUCKET, Key=key)
                if h["ContentLength"] != local:
                    todo.append((p, key, local, f"size {h['ContentLength']} != {local}"))
            except Exception:
                todo.append((p, key, local, "absent"))
        mb = sum(t[2] for t in todo) / 1e6
        grand["missing"] += len(todo); grand["bytes"] += sum(t[2] for t in todo)
        print(f"{day}: local finals={len(finals)}  missing/mismatched={len(todo)}  {mb:.0f} MB")
        for p, key, local, why in todo:
            print(f"    {'UPLOAD' if a.apply else 'WOULD UPLOAD'} {p.name:38} {local/1e6:8.1f} MB  ({why})")
            if not a.apply:
                continue
            digest = md5_of(p)
            with p.open("rb") as fh:
                s3.put_object(Bucket=BUCKET, Key=key, Body=fh)   # single-part -> ETag == MD5
            grand["uploaded"] += 1
            h = s3.head_object(Bucket=BUCKET, Key=key)
            etag = h["ETag"].strip('"')
            if h["ContentLength"] == local and etag == digest:
                grand["verified"] += 1
                print(f"      VERIFIED len={h['ContentLength']} etag={etag[:12]}… == md5")
            else:
                grand["failed"] += 1
                print(f"      *** FAILED len={h['ContentLength']} vs {local}, etag={etag[:12]}… vs md5 {digest[:12]}…")
    print(f"\nTOTAL missing={grand['missing']} ({grand['bytes']/1e9:.2f} GB) "
          f"uploaded={grand['uploaded']} verified={grand['verified']} failed={grand['failed']}")
    return 1 if grand["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
