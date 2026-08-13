"""M1 — restore ONE archived day (ticks + depth) from S3 into a replayer-ready layout.

SAFETY CONTRACT:
  * ADD-ONLY: an existing local file is SKIPPED and reported — never overwritten.
  * Never touches the live data dir: default destination is <root>/restore/data/<day>
    (the research clone's own tree). Restoring INTO the live dir is refused unless
    --dest-root is given explicitly AND the day is not today.
  * TODAY is always refused (live recording).
  * DISK GUARD: refuses when free space < planned-restore-size + 10 GiB margin.
  * VERIFY: every downloaded file must match the S3 ContentLength AND (when present)
    the size recorded in the day's backup.json manifest; single-part ETags are
    additionally md5-verified. Any mismatch -> the file is deleted + loud failure.
  * Depth PARTS subtrees (depth/<name>/parts/...) are EXCLUDED: the replayer reads
    only depth/*.parquet (replayer/source.py:82) — the consolidated per-instrument
    files at depth/ top level are what S3 holds there and all a replay needs.
  * --cleanup removes the restored day dir afterwards (frees disk; one-day-at-a-time).

Off by default (explicit CLI only), --dry-run prints the plan without downloading.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent      # orderflow_engine/
MARGIN = 10 * 1024 ** 3                            # 10 GiB safety margin
BUCKET = "tradetri-orderflow-data-383136686940-ap-south-1-an"
PREFIX = "orderflow/r0"


def plan_keys(objects: list[dict], day: str) -> list[dict]:
    """Filter the S3 listing to what a replay needs: day-root files + top-level
    depth/*.parquet. Parts subtrees and anything nested deeper are excluded."""
    keep = []
    root = f"{PREFIX}/{day}/"
    for o in objects:
        rel = o["Key"][len(root):]
        parts = rel.split("/")
        if len(parts) == 1 and rel:                          # ticks/manifest/report/events
            keep.append({"key": o["Key"], "rel": rel, "size": o["Size"],
                         "etag": o.get("ETag", "").strip('"')})
        elif len(parts) == 2 and parts[0] == "depth" and rel.endswith(".parquet"):
            keep.append({"key": o["Key"], "rel": rel, "size": o["Size"],
                         "etag": o.get("ETag", "").strip('"')})
    return keep


def manifest_sizes(dest_day: Path, plan: list[dict]) -> dict[str, int]:
    """Sizes from the day's backup.json (restored first when present) — the upload-time
    audit. Missing manifest -> empty dict (S3 ContentLength remains the verifier)."""
    for cand in (dest_day / "backup.json",):
        if cand.exists():
            try:
                d = json.loads(cand.read_text())
                return {f["rel"]: int(f["size"]) for f in d.get("files", [])}
            except Exception:                                # noqa: BLE001
                return {}
    return {}


def verify_file(path: Path, expect_size: int, etag: str, manifest_size: int | None) -> str | None:
    """None if OK, else the reason string."""
    actual = path.stat().st_size
    if actual != expect_size:
        return f"size {actual} != S3 ContentLength {expect_size}"
    if manifest_size is not None and actual != manifest_size:
        return f"size {actual} != backup.json {manifest_size}"
    if etag and "-" not in etag:                             # single-part -> ETag == md5
        md5 = hashlib.md5(path.read_bytes()).hexdigest()
        if md5 != etag:
            return f"md5 {md5} != etag {etag}"
    return None


def free_bytes(path: Path) -> int:
    st = shutil.disk_usage(str(path))
    return st.free


def restore_day(day: str, *, dest_root: Path, client=None, dry_run: bool = False,
                today: date | None = None, free_fn=free_bytes) -> dict:
    today = today or date.today()
    if day == today.isoformat():
        return {"refused": f"REFUSED: {day} is TODAY (live recording) — never restore today"}
    live_data = (HERE / "data").resolve()
    dest_day = (dest_root / "data" / day)
    if dest_day.resolve().parent == live_data:
        return {"refused": f"REFUSED: destination {dest_day} is the LIVE data dir"}
    if client is None:
        import boto3
        client = boto3.client("s3", "ap-south-1")
    objects = []
    tok = None
    while True:
        kw = dict(Bucket=BUCKET, Prefix=f"{PREFIX}/{day}/", MaxKeys=1000)
        if tok:
            kw["ContinuationToken"] = tok
        r = client.list_objects_v2(**kw)
        objects.extend(r.get("Contents", []))
        if not r.get("IsTruncated"):
            break
        tok = r["NextContinuationToken"]
    if not objects:
        return {"refused": f"REFUSED: no S3 objects under {PREFIX}/{day}/"}
    plan = plan_keys(objects, day)
    total = sum(p["size"] for p in plan)
    skipped_existing = [p["rel"] for p in plan if (dest_day / p["rel"]).exists()]
    todo = [p for p in plan if p["rel"] not in set(skipped_existing)]
    need = sum(p["size"] for p in todo)
    free = free_fn(dest_root if dest_root.exists() else HERE)
    if free < need + MARGIN:
        return {"refused": f"REFUSED: disk guard — free {free/1e9:.1f}GB < "
                           f"restore {need/1e9:.1f}GB + 10GB margin"}
    report = {"day": day, "dest": str(dest_day), "planned_files": len(plan),
              "planned_bytes": total, "skipped_existing": skipped_existing,
              "to_download": len(todo), "excluded_parts_objects": len(objects) - len(plan)}
    if dry_run:
        report["dry_run"] = True
        return report
    dest_day.mkdir(parents=True, exist_ok=True)
    # backup.json first so manifest verification covers the rest
    todo.sort(key=lambda p: (p["rel"] != "backup.json", p["rel"]))
    msizes: dict[str, int] = {}
    done, failed = [], []
    for p in todo:
        out = dest_day / p["rel"]
        out.parent.mkdir(parents=True, exist_ok=True)
        client.download_file(BUCKET, p["key"], str(out))
        reason = verify_file(out, p["size"], p["etag"], msizes.get(p["rel"]))
        if reason:
            out.unlink(missing_ok=True)
            failed.append({"rel": p["rel"], "reason": reason})
            break                                            # loud, immediate stop
        done.append(p["rel"])
        if p["rel"] == "backup.json":
            msizes = manifest_sizes(dest_day, plan)
    report.update({"downloaded": len(done), "verify_failed": failed,
                   "ok": not failed and len(done) == len(todo)})
    return report


def cleanup_day(day: str, *, dest_root: Path) -> str:
    dest_day = dest_root / "data" / day
    live_data = (HERE / "data").resolve()
    if dest_day.resolve().parent == live_data:
        return f"REFUSED: will not delete inside the live data dir"
    if not dest_day.exists():
        return f"nothing to clean at {dest_day}"
    shutil.rmtree(dest_day)
    return f"removed {dest_day}"


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="scripts.restore_day")
    ap.add_argument("--date", required=True)
    ap.add_argument("--dest-root", default=str(HERE / "restore"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cleanup", action="store_true",
                    help="remove the previously-restored day dir (frees disk)")
    args = ap.parse_args(argv)
    dest_root = Path(args.dest_root)
    if args.cleanup:
        print(cleanup_day(args.date, dest_root=dest_root))
        return 0
    rep = restore_day(args.date, dest_root=dest_root, dry_run=args.dry_run)
    print(json.dumps(rep, indent=1))
    return 0 if rep.get("ok") or rep.get("dry_run") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
