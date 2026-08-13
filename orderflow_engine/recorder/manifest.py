"""Manifest helpers — merge across sessions, rebuild from disk (offline repair).

2026-07-14 pipeline bug: on a multi-session day (and in the post-record_end
empty-session window) ``manifest.json`` was OVERWRITTEN with a core-only
snapshot, blinding the chain reader (every instrument fell to ``SID<n>``, 0
indices). The recorder now MERGES manifest writes (union by security_id, keep
expiries) instead of overwriting, and a day whose manifest is already thin can
be rebuilt OFFLINE from the consolidated parquet file-stems plus the recorded
``OPTIONS_ARMED`` expiries — no re-recording needed.

Pure data-lane logic: no feed, no writers, no recording. Used by the manifest
write path (recorder/main.py), the offline salvage/consolidate path
(recorder/salvage.py), and the analysis readers (chain/run.py).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_EXP = re.compile(r"\bexp=(\S+)")


def load_manifest(path: Path) -> list[dict]:
    """Instrument list from a manifest.json (``[]`` if missing/unreadable)."""
    try:
        return json.loads(Path(path).read_text()).get("instruments", [])
    except Exception:  # noqa: BLE001 - missing/corrupt manifest -> empty
        return []


def merge_entries(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """Union two instrument lists by security_id (never shrink).

    ``incoming`` wins field-by-field, but a non-empty ``expiry`` is preserved
    from whichever side has it (an option expiry is never lost by a later
    core-only write), and any field only ``existing`` carries is kept.
    """
    by_id: dict[int, dict] = {}
    for e in existing:
        try:
            by_id[int(e["security_id"])] = dict(e)
        except (KeyError, ValueError, TypeError):
            continue
    for e in incoming:
        try:
            sid = int(e["security_id"])
        except (KeyError, ValueError, TypeError):
            continue
        merged = dict(e)
        old = by_id.get(sid)
        if old:
            if not merged.get("expiry") and old.get("expiry"):
                merged["expiry"] = old["expiry"]
            for k, v in old.items():
                merged.setdefault(k, v)
        by_id[sid] = merged
    return list(by_id.values())


def write_manifest(day_dir: Path, instruments: list[dict]) -> None:
    """Atomically write the instrument list to ``<day>/manifest.json``."""
    out = Path(day_dir) / "manifest.json"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"date": Path(day_dir).name,
                               "instruments": instruments}, indent=2, default=str))
    tmp.replace(out)


def expiries_from_events(day_dir: Path) -> dict[str, str]:
    """``{index -> expiry}`` recovered from recorded ``OPTIONS_ARMED`` events.

    The recorder logs e.g. ``NIFTY exp=2026-07-14 spot=... strikes=[...]`` when a
    chain arms — the authoritative expiry for every strike of that index, kept in
    events.parquet even when the manifest was overwritten.
    """
    import pyarrow.parquet as pq

    f = Path(day_dir) / "events.parquet"
    out: dict[str, str] = {}
    if not f.exists():
        return out
    try:
        rows = pq.read_table(str(f)).to_pylist()
    except Exception:  # noqa: BLE001
        return out
    for r in rows:
        if r.get("kind") != "OPTIONS_ARMED":
            continue
        detail = r.get("detail") or ""
        toks = detail.split()
        m = _EXP.search(detail)
        if toks and m:
            out[toks[0]] = m.group(1)
    return out


def _split_stem(stem: str) -> tuple[str | None, int | None]:
    """``NIFTY_CE_23500_51347`` -> (``NIFTY_CE_23500``, 51347)."""
    try:
        sym, sid = stem.rsplit("_", 1)
        return sym, int(sid)
    except (ValueError, IndexError):
        return None, None


def _option_index(symbol: str) -> str | None:
    parts = symbol.split("_")
    if len(parts) >= 3 and parts[-2] in ("CE", "PE"):
        return "_".join(parts[:-2])
    return None


def rebuild_from_disk(day_dir: Path) -> list[dict]:
    """Reconstruct a COMPLETE manifest from the consolidated parquet file-stems.

    Every ``<SYMBOL>_<secid>.parquet`` in the day dir becomes an entry; option
    expiries are recovered from OPTIONS_ARMED events; then the existing on-disk
    manifest is overlaid so the core instruments keep their richer recorded
    fields (exchange_segment / kind / gap_check / real future expiry).
    """
    day_dir = Path(day_dir)
    exp_by_index = expiries_from_events(day_dir)
    entries: list[dict] = []
    for f in sorted(day_dir.glob("*.parquet")):
        if f.name == "events.parquet":
            continue
        sym, sid = _split_stem(f.stem)
        if sym is None:
            continue
        oi = _option_index(sym)
        expiry = exp_by_index.get(oi, "") if oi is not None else ""
        entries.append({"symbol": sym, "security_id": sid, "expiry": expiry})
    # overlay the on-disk manifest last so recorded core fields/expiries win
    return merge_entries(entries, load_manifest(day_dir / "manifest.json"))
