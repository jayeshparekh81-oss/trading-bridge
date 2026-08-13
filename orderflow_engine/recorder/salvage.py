"""Salvage a crashed/incomplete session from its part-files.

When a session dies mid-day (e.g. the 2026-07-09 disk-full crash) the normal
close/consolidate never runs, leaving each instrument as a ``parts/<name>/``
directory of atomic part-files (plus possibly a stray primary ``*.parquet.tmp``
with no footer). This rebuilds the final per-instrument parquet from every
READABLE part, and quarantines unreadable ones for forensics.

Guarantees:
  * Readable parts are consolidated into ``<name>.parquet`` (zstd), overwriting
    any partial top-level file from the crash.
  * Unreadable parts are **moved** (never deleted) to ``<day>/corrupt/`` with
    their relative path preserved.
  * Raw readable parts are left in place under ``parts/``.
  * Afterwards ``verify_session(day, partial=True)`` writes ``report.json`` with
    status PARTIAL (usable data, incomplete session).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from recorder.schema import EVENT_SCHEMA, TICK_SCHEMA
from recorder.writer import _atomic_write_table

log = logging.getLogger("recorder.salvage")


def _quarantine(day_dir: Path, part: Path, summary: dict) -> None:
    rel = part.relative_to(day_dir)
    target = day_dir / "corrupt" / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(str(part), str(target))
    summary["corrupt_parts"].append(str(rel))
    log.warning("salvage: quarantined unreadable part %s -> corrupt/%s", rel, rel)


def _consolidate_instrument(day_dir: Path, inst_dir: Path, summary: dict) -> None:
    name = inst_dir.name
    if name == "events":
        dest, schema = day_dir / "events.parquet", EVENT_SCHEMA
    else:
        dest, schema = day_dir / f"{name}.parquet", TICK_SCHEMA

    readable: list[pa.Table] = []
    corrupt: list[Path] = []
    for part in sorted(inst_dir.glob("part-*.parquet")):
        try:
            readable.append(pq.read_table(str(part)))
        except Exception:  # noqa: BLE001 - corrupt/truncated part
            corrupt.append(part)
    for part in corrupt:
        _quarantine(day_dir, part, summary)

    if readable:
        merged = pa.concat_tables(readable)
    elif corrupt:
        merged = pa.Table.from_pylist([], schema=schema)  # all parts were corrupt
    else:
        return  # nothing here

    _atomic_write_table(merged, dest)
    summary["consolidated"].append({"instrument": name, "rows": merged.num_rows,
                                    "readable_parts": len(readable),
                                    "corrupt_parts": len(corrupt)})
    log.info("salvage: %s -> %d rows from %d parts (%d corrupt)",
             name, merged.num_rows, len(readable), len(corrupt))


def salvage_day(day_dir: Path, *, run_verify: bool = True) -> dict:
    """Consolidate readable parts, quarantine corrupt ones, verify PARTIAL."""
    day_dir = Path(day_dir)
    summary: dict = {"date_dir": str(day_dir), "consolidated": [],
                     "corrupt_parts": [], "stray_tmp": []}
    if not day_dir.exists():
        summary["error"] = f"{day_dir} does not exist"
        return summary

    parts_root = day_dir / "parts"
    if parts_root.exists():
        for inst_dir in sorted(p for p in parts_root.iterdir() if p.is_dir()):
            _consolidate_instrument(day_dir, inst_dir, summary)

    # Stray primary writer temp files (crash before the parquet footer was
    # written) are unreadable — quarantine so they don't confuse verify.
    for tmp in sorted(day_dir.glob("*.parquet.tmp")):
        try:
            pq.read_table(str(tmp))  # occasionally a complete file slipped through
        except Exception:  # noqa: BLE001
            rel = tmp.relative_to(day_dir)
            target = day_dir / "corrupt" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(str(tmp), str(target))
            summary["stray_tmp"].append(str(rel))
            log.warning("salvage: quarantined stray tmp %s", rel)

    summary["instruments_consolidated"] = len(summary["consolidated"])
    summary["corrupt_count"] = len(summary["corrupt_parts"]) + len(summary["stray_tmp"])

    # 2026-07-14: rebuild a COMPLETE manifest from the consolidated file-stems +
    # recorded OPTIONS_ARMED expiries, so a day whose manifest was overwritten
    # core-only (multi-session / post-record_end empty sessions) is no longer
    # blind to its option chains. Merges over whatever manifest exists.
    from recorder.manifest import rebuild_from_disk, write_manifest
    manifest = rebuild_from_disk(day_dir)
    write_manifest(day_dir, manifest)
    summary["manifest_instruments"] = len(manifest)

    # Write a salvage audit alongside the data.
    audit = day_dir / "salvage.json"
    tmp = audit.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(summary, indent=2, default=str))
    tmp.replace(audit)

    if run_verify:
        import verify_session as V
        report = V.verify_session(day_dir, partial=True)
        out = day_dir / "report.json"
        rtmp = out.with_suffix(".json.tmp")
        rtmp.write_text(json.dumps(report, indent=2, default=str))
        rtmp.replace(out)
        summary["verify_status"] = report.get("status")
        log.info("salvage: verify status=%s coverage=%s%%", report.get("status"),
                 report.get("coverage", {}).get("coverage_pct"))
    return summary


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if len(argv) < 2:
        print("usage: python -m recorder.salvage <data/YYYY-MM-DD>")
        return 2
    summary = salvage_day(Path(argv[1]))
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
