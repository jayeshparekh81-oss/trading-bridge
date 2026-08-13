"""Parts cleanup — delete a day's rotation/journal parts ONLY once they are provably
redundant (Module R0 ops, 2026-07-16).

Parts (parts/<inst>/, depth/parts/<inst>/) are intermediate scratch that consolidation
folds into the finals. They pile up (~7-9GB/day, never deleted) → the 13-Jul disk crisis.
They may be deleted the moment they stop being useful — when the final is proven good AND
durable — and NOT a moment before.

An instrument's parts are eligible ONLY when EVERY gate passes (independent checks, this
DELETES real data):
  1. backup.json  success == true            (day-level — the whole day reached S3)
  2. the report covering it says status PASS  (R0 report.json / depth/report.json; a
     PARTIAL/FAIL report keeps ALL its parts)
  3. the final file exists on disk
  4. that instrument's verify entry is CLEAN  (problems == [], rows > 0, not named in the
     day-level problems)
  5. the final is in S3, HEAD-VERIFIED        (head_object succeeds AND ContentLength ==
     local size — not just "marked" backed up)
Any failure → KEEP + log the reason loudly.

DRY-RUN IS THE DEFAULT: it prints exactly what WOULD be deleted (paths + GB) and deletes
nothing. Actual deletion needs BOTH the explicit --apply flag AND config
``parts_cleanup.enabled: true`` (default OFF) — two deliberate acts, no accident possible.
It never auto-runs; it is a manual CLI.

    python -m recorder.parts_cleanup data/YYYY-MM-DD            # dry-run (default)
    python -m recorder.parts_cleanup data/YYYY-MM-DD --apply    # delete (needs knob ON)
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Optional

log = logging.getLogger("recorder.parts_cleanup")
HERE = Path(__file__).resolve().parent.parent


def _load(p: Path) -> Optional[dict]:
    try:
        return json.loads(p.read_text()) if p.exists() else None
    except Exception:  # noqa: BLE001
        return None


def _dir_bytes(d: Path) -> int:
    return sum(f.stat().st_size for f in d.rglob("*") if f.is_file())


class PartsCleanup:
    def __init__(self, s3_cfg: dict, *, client=None):
        self.bucket = s3_cfg.get("bucket")
        self.prefix = s3_cfg.get("prefix", "")
        self.region = s3_cfg.get("region")
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("s3", region_name=self.region)
        return self._client

    def _key(self, date_name: str, rel: str) -> str:
        return "/".join(p for p in (self.prefix, date_name, rel) if p)

    def _head_ok(self, key: str, size: int) -> bool:
        """True iff the object is in S3 AND its size matches the local final exactly."""
        try:
            h = self.client.head_object(Bucket=self.bucket, Key=key)
            return int(h.get("ContentLength", -1)) == int(size)
        except Exception:  # noqa: BLE001 - any HEAD failure => not verified => keep
            return False

    def _owners(self, day_dir: Path) -> list[dict]:
        """Every instrument that has a parts dir, with where its final/report/s3-key live."""
        out = []
        pr = day_dir / "parts"
        if pr.is_dir():
            for d in sorted(pr.iterdir()):
                if d.is_dir():
                    out.append({"base": d.name, "kind": "r0", "parts_dir": d,
                                "final": day_dir / f"{d.name}.parquet",
                                "report": day_dir / "report.json",
                                "rel": f"{d.name}.parquet"})
        dpr = day_dir / "depth" / "parts"
        if dpr.is_dir():
            for d in sorted(dpr.iterdir()):
                if d.is_dir():
                    out.append({"base": d.name, "kind": "depth", "parts_dir": d,
                                "final": day_dir / "depth" / f"{d.name}.parquet",
                                "report": day_dir / "depth" / "report.json",
                                "rel": f"depth/{d.name}.parquet"})
        return out

    def _decide(self, date_name: str, o: dict, backup_ok: bool) -> Optional[str]:
        """Return None if eligible for deletion, else a KEEP reason."""
        if not backup_ok:
            return "backup.json not success:true"
        rep = _load(o["report"])
        if rep is None:
            return f"no {o['kind']} report ({o['report'].name})"
        if rep.get("status") != "PASS":
            return f"{o['kind']} verify status={rep.get('status')} (not PASS)"
        if not o["final"].exists():
            return "final missing on disk"
        entry = next((e for e in rep.get("instruments", [])
                      if e.get("file") == f"{o['base']}.parquet"), None)
        if entry is None:
            return "no verify entry for the final"
        if entry.get("problems"):
            return f"instrument has problems {entry['problems']}"
        if not (entry.get("rows", 0) > 0):
            return "final has 0 rows"
        if any(o["base"] in str(p) for p in rep.get("problems", [])):
            return "instrument named in day-level problems"
        if not self._head_ok(self._key(date_name, o["rel"]), o["final"].stat().st_size):
            return "S3 HEAD failed / size mismatch (not verified in S3)"
        return None

    def plan(self, day_dir: Path) -> dict:
        day_dir = Path(day_dir)
        date_name = day_dir.name
        backup_ok = bool((_load(day_dir / "backup.json") or {}).get("success") is True)
        eligible, kept = [], []
        for o in self._owners(day_dir):
            reason = self._decide(date_name, o, backup_ok)
            rec = {"base": o["base"], "kind": o["kind"],
                   "parts_dir": str(o["parts_dir"]), "bytes": _dir_bytes(o["parts_dir"])}
            if reason is None:
                eligible.append(rec)
            else:
                kept.append({**rec, "reason": reason})
        return {"date": date_name, "backup_ok": backup_ok,
                "eligible": eligible, "kept": kept,
                "free_bytes": sum(r["bytes"] for r in eligible),
                "kept_bytes": sum(r["bytes"] for r in kept)}

    def run(self, day_dir: Path, *, apply: bool = False) -> dict:
        p = self.plan(day_dir)
        p["applied"] = False
        if apply:
            for r in p["eligible"]:
                d = Path(r["parts_dir"])
                if d.is_dir():
                    shutil.rmtree(d)
                    log.warning("parts_cleanup DELETED %s (%.2f GB)", d, r["bytes"] / 1e9)
            # remove now-empty parts/ and depth/parts/ parents
            for rel in ("parts", "depth/parts"):
                par = Path(day_dir) / rel
                if par.is_dir() and not any(par.iterdir()):
                    par.rmdir()
            p["applied"] = True
        return p


def _gb(n: int) -> float:
    return round(n / 1e9, 3)


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    ap = argparse.ArgumentParser(prog="recorder.parts_cleanup")
    ap.add_argument("day_dir", help="data/YYYY-MM-DD")
    ap.add_argument("--apply", action="store_true",
                    help="ACTUALLY delete (needs parts_cleanup.enabled=true); default = dry-run")
    ap.add_argument("--config", default=str(HERE / "config.yaml"))
    args = ap.parse_args(argv[1:])
    import yaml
    cfg = yaml.safe_load(Path(args.config).read_text()) or {}
    enabled = bool((cfg.get("parts_cleanup", {}) or {}).get("enabled", False))
    pc = PartsCleanup(cfg.get("s3_backup", {}))

    apply = args.apply
    if apply and not enabled:
        print("REFUSING to delete: parts_cleanup.enabled=false. Set it true to arm, "
              "then re-run with --apply. (dry-run below instead)")
        apply = False

    res = pc.run(Path(args.day_dir), apply=apply)
    mode = "APPLIED (deleted)" if res["applied"] else "DRY-RUN (nothing deleted)"
    print(f"\nPARTS CLEANUP — {res['date']} — {mode}")
    print(f"backup success: {res['backup_ok']}")
    print(f"\nWOULD FREE {_gb(res['free_bytes'])} GB — {len(res['eligible'])} instrument(s):")
    for r in sorted(res["eligible"], key=lambda x: -x["bytes"]):
        print(f"  [{r['kind']:5}] {r['base']:28} {_gb(r['bytes']):7} GB  {r['parts_dir']}")
    print(f"\nKEPT {_gb(res['kept_bytes'])} GB — {len(res['kept'])} instrument(s):")
    for r in sorted(res["kept"], key=lambda x: -x["bytes"])[:40]:
        print(f"  [{r['kind']:5}] {r['base']:28} {_gb(r['bytes']):7} GB  — {r['reason']}")
    if len(res["kept"]) > 40:
        print(f"  ... and {len(res['kept']) - 40} more kept")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
