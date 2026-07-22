"""PASS-DAY WINDOW BUILDER (2026-07-22) — assemble a FROZEN day-list eval-ready for the
delta+vwap evaluator (raw-ticks consumer; depth NOT needed), one restored day at a time.

CONTRACT (from the planning audit):
  * Takes a FROZEN day-list as INPUT and NEVER enumerates or guesses days. An empty /
    missing list is a hard refusal — the builder does not pick the window.
  * Per-day decision ladder:
      local raw data present + complete  -> assess candidates -> ok | empty-ok
      local present but partial/stale    -> degraded (excluded, reason kept)
      not local, S3-restorable           -> restore -> assess -> INLINE cleanup
      restore refused / data absent       -> failed (excluded, reason kept)
  * NEVER silently drops a day: every input day gets a manifest entry with a status.
  * empty-ok (data fine, 0 candidates — e.g. 07-14) and failed (restore/data problem)
    are DISTINCT statuses and must not be conflated.
  * Disk safety: a restored day is assessed then cleaned up INLINE before the next
    restore (the M1 disk guard forbids two restored depth-days coexisting).

Every side effect is an injectable seam (probe / restore / cleanup / assess / process),
so the whole ladder is unit-testable without S3, disk, or a real replay. Research-lane
only: reads recorded days, restores into the clone's own restore/ tree, writes nothing
into live data and touches no config/live path.

Day-dir convention (shared with capture_day + restore_day): <root>/data/<day>.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Optional, Sequence

HERE = Path(__file__).resolve().parent.parent          # orderflow_engine/

# --- statuses -----------------------------------------------------------------
OK = "ok"                    # data present, replay yields > 0 candidates
EMPTY_OK = "empty-ok"        # data present + replay ran, but 0 candidates (kept, flagged)
DEGRADED = "degraded"        # present but partial/stale, or candidates un-assessable
FAILED = "failed"           # restore refused / checksum fail / data absent
READY_STATUSES = {OK, EMPTY_OK}    # what the harness may consume


@dataclass
class AssessResult:
    candidates: Optional[int]                  # total across the instrument filter; None = unknown
    per_instrument: dict = field(default_factory=dict)
    note: str = ""


@dataclass
class LocalProbe:
    present: bool
    complete: bool
    reason: str = ""


@dataclass
class DayEntry:
    day: str
    source: str                                # local | restored | none
    root: Optional[str]                        # <root> whose <root>/data/<day> holds the raw ticks
    status: str
    candidates: Optional[int]
    note: str = ""

    def as_dict(self) -> dict:
        return {"day": self.day, "source": self.source, "root": self.root,
                "status": self.status, "candidates": self.candidates, "note": self.note}


# ============================ default seams ==================================
def _default_probe(day: str, data_root: Path, *, today: date,
                   min_coverage_frac: float) -> LocalProbe:
    """Present = the day dir exists with a manifest. Complete = a finalized session whose
    observed span covers >= ``min_coverage_frac`` of the expected session (from report.json)
    AND the day is not TODAY (today is still recording -> partial). This is an OPERATIONAL
    sanity floor, NOT a value fitted to any eval result; override via ``min_coverage_frac``."""
    day_dir = data_root / "data" / day
    if not (day_dir / "manifest.json").exists():
        return LocalProbe(present=False, complete=False, reason="no local day dir/manifest")
    if day == today.isoformat():
        return LocalProbe(present=True, complete=False, reason="TODAY — session still recording")
    rep = day_dir / "report.json"
    if not rep.exists():
        return LocalProbe(present=True, complete=False,
                          reason="no report.json — session not finalized")
    try:
        cov = (json.loads(rep.read_text()).get("coverage") or {})
        exp = float(cov.get("expected_session_s") or 0.0)
        obs = float(cov.get("observed_span_s") or 0.0)
    except Exception:                                    # noqa: BLE001
        return LocalProbe(present=True, complete=False, reason="report.json unreadable")
    if exp <= 0:
        return LocalProbe(present=True, complete=False, reason="report.json missing coverage")
    frac = obs / exp
    if frac < min_coverage_frac:
        return LocalProbe(present=True, complete=False,
                          reason=f"partial session: span {frac:.0%} < {min_coverage_frac:.0%} floor")
    return LocalProbe(present=True, complete=True, reason=f"span {frac:.0%}")


def _default_assess(day: str, root: Path, instruments: Sequence[str], *,
                    analysis_root: Path) -> AssessResult:
    """Cheap candidate count from a persisted signals.parquet (candidate rows == what the
    evaluator regenerates by replay, verify_against_disk-proven 1:1). Restored raw-only days
    have no signals.parquet -> candidates None (un-assessable) unless a replay-based assessor
    is injected. NEVER guesses a count."""
    import pyarrow.parquet as pq
    p = Path(analysis_root) / day / "signals.parquet"
    if not p.exists():
        return AssessResult(candidates=None, note=f"no signals.parquet under {p.parent}")
    t = pq.read_table(str(p), columns=["instrument"])
    keep = set(instruments)
    per: dict = {i: 0 for i in keep}
    for inst in t.column("instrument").to_pylist():
        if inst in keep:
            per[inst] += 1
    return AssessResult(candidates=sum(per.values()), per_instrument=per)


def _default_restore(day: str, restore_root: Path) -> dict:
    from scripts.restore_day import restore_day
    return restore_day(day, dest_root=restore_root)


def _cleanup_via_m1(day: str, restore_root: Path) -> str:
    from scripts.restore_day import cleanup_day
    return cleanup_day(day, dest_root=restore_root)


# ============================ the builder ====================================
def _classify(a: AssessResult) -> tuple[str, Optional[int], str]:
    if a.candidates is None:
        return DEGRADED, None, a.note or "candidates un-assessable"
    if a.candidates == 0:
        return EMPTY_OK, 0, a.note or "replay ran, 0 candidates"
    return OK, a.candidates, a.note


def build_window(days: Sequence[str], *, data_root: Path | str = HERE,
                 analysis_root: Path | str = HERE / "analysis",
                 instruments: Sequence[str] = ("NIFTY_FUT", "BANKNIFTY_FUT"),
                 restore_root: Path | str = HERE / "restore",
                 today: Optional[date] = None,
                 min_coverage_frac: float = 0.5,
                 probe_fn: Optional[Callable] = None,
                 restore_fn: Optional[Callable] = None,
                 cleanup_fn: Optional[Callable] = None,
                 assess_fn: Optional[Callable] = None,
                 process_fn: Optional[Callable] = None) -> dict:
    """Assemble ``days`` (a FROZEN, explicit list) eval-ready. Returns a manifest dict:
    {days:[DayEntry...], ready:[day...], excluded:[{day,status,note}...], instruments, counts}.

    ``process_fn(day, root, instruments)`` — optional real-work hook run WHILE a restored
    day is on disk (e.g. the evaluator), between assess and the inline cleanup; None = the
    builder only assesses+cleans. Every I/O seam is injectable for testing."""
    if not days or not all(isinstance(d, str) and d.strip() for d in days):
        raise ValueError("window_builder REFUSES to run without an explicit frozen day-list "
                         "(it never enumerates or guesses days)")
    data_root, analysis_root, restore_root = Path(data_root), Path(analysis_root), Path(restore_root)
    today = today or date.today()
    probe_fn = probe_fn or (lambda d, r: _default_probe(d, r, today=today,
                                                        min_coverage_frac=min_coverage_frac))
    restore_fn = restore_fn or _default_restore
    cleanup_fn = cleanup_fn or _cleanup_via_m1
    assess_fn = assess_fn or (lambda d, r, i: _default_assess(d, r, i, analysis_root=analysis_root))

    entries: list[DayEntry] = []
    for day in days:
        entries.append(_build_one(day, instruments=instruments, data_root=data_root,
                                  restore_root=restore_root, probe_fn=probe_fn,
                                  restore_fn=restore_fn, cleanup_fn=cleanup_fn,
                                  assess_fn=assess_fn, process_fn=process_fn))

    ready = [e.day for e in entries if e.status in READY_STATUSES]
    excluded = [{"day": e.day, "status": e.status, "note": e.note}
                for e in entries if e.status not in READY_STATUSES]
    counts = {s: sum(1 for e in entries if e.status == s)
              for s in (OK, EMPTY_OK, DEGRADED, FAILED)}
    return {"days": [e.as_dict() for e in entries], "ready": ready, "excluded": excluded,
            "instruments": list(instruments), "counts": counts, "n_input": len(days)}


def _build_one(day, *, instruments, data_root, restore_root,
               probe_fn, restore_fn, cleanup_fn, assess_fn, process_fn) -> DayEntry:
    p = probe_fn(day, data_root)
    # 1) local + complete -> assess in place, never cleaned (it's the host's data)
    if p.present and p.complete:
        a = assess_fn(day, data_root, instruments)
        if process_fn is not None:
            process_fn(day, data_root, instruments)
        status, cand, note = _classify(a)
        return DayEntry(day, "local", str(data_root), status, cand, note or p.reason)
    # 2) local but partial/stale -> degraded, never silently used
    if p.present and not p.complete:
        return DayEntry(day, "local", str(data_root), DEGRADED, None, p.reason)
    # 3) not local -> restore, assess, INLINE cleanup
    try:
        r = restore_fn(day, restore_root)
    except Exception as exc:                              # noqa: BLE001 - one day never crashes the run
        return DayEntry(day, "restored", None, FAILED, None, f"restore raised: {type(exc).__name__}: {exc}")
    if not r.get("ok"):
        reason = r.get("refused") or r.get("reason") or "restore did not complete"
        return DayEntry(day, "restored", None, FAILED, None, reason)
    restored_dir = str(restore_root)
    try:
        a = assess_fn(day, restore_root, instruments)
        if process_fn is not None:                       # real eval WHILE data is on disk
            process_fn(day, restore_root, instruments)
        status, cand, note = _classify(a)
        note = (note + "; " if note else "") + "restored+assessed then cleaned (re-restore to evaluate)"
        return DayEntry(day, "restored", restored_dir, status, cand, note)
    finally:
        try:
            cleanup_fn(day, restore_root)                # INLINE — free before the next restore
        except Exception:                                # noqa: BLE001 - cleanup best-effort
            pass


# ============================ CLI (explicit list only) =======================
def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="research.window_builder")
    ap.add_argument("--days", required=True,
                    help="FROZEN comma-separated day-list (required; the tool never guesses)")
    ap.add_argument("--instruments", default="NIFTY_FUT,BANKNIFTY_FUT")
    ap.add_argument("--data-root", default=str(HERE))
    ap.add_argument("--analysis-root", default=str(HERE / "analysis"))
    ap.add_argument("--restore-root", default=str(HERE / "restore"))
    ap.add_argument("--min-coverage-frac", type=float, default=0.5)
    ap.add_argument("--out", default=None, help="write the manifest JSON to this NEW file")
    args = ap.parse_args(argv)
    days = [d for d in args.days.split(",") if d.strip()]
    insts = [s for s in args.instruments.split(",") if s.strip()]
    man = build_window(days, data_root=args.data_root, analysis_root=args.analysis_root,
                       restore_root=args.restore_root, instruments=insts,
                       min_coverage_frac=args.min_coverage_frac)
    out = json.dumps(man, indent=1)
    if args.out:
        Path(args.out).write_text(out)
    print(out)
    return 0 if not man["excluded"] else 2


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
