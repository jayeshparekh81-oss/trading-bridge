"""ReplaySource — read-only access to a recorded day's parquet + coverage meta.

Tolerant by design: a PARTIAL/crashed day (missing instruments, empty files,
unreadable parquet) must replay whatever exists and never crash. Coverage is read
from the recorder's own ``report.json`` (status/coverage_pct) + ``manifest.json``
(instrument kinds) when present, else derived from the files themselves.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pyarrow.parquet as pq

log = logging.getLogger("replayer.source")
IST = ZoneInfo("Asia/Kolkata")


@dataclass
class Coverage:
    date: str
    status: str | None = None            # PASS | PARTIAL | FAIL (from report.json)
    coverage_pct: float | None = None
    tick_instruments: int = 0            # instrument files with >0 rows
    empty_instruments: int = 0
    unreadable_files: list[str] = field(default_factory=list)
    total_tick_rows: int = 0
    total_event_rows: int = 0
    first_ts_ns: int | None = None
    last_ts_ns: int | None = None
    per_instrument: dict[str, int] = field(default_factory=dict)

    @property
    def total_events(self) -> int:
        return self.total_tick_rows + self.total_event_rows

    @property
    def span_s(self) -> float | None:
        if self.first_ts_ns is None or self.last_ts_ns is None:
            return None
        return (self.last_ts_ns - self.first_ts_ns) / 1e9


class ReplaySource:
    def __init__(self, day_dir: Path, instruments: list[str] | None = None):
        self.day_dir = Path(day_dir)
        # Case-insensitive substring filters on the instrument file stem.
        self._filters = [s.strip().upper() for s in (instruments or []) if s.strip()]

    def exists(self) -> bool:
        return self.day_dir.is_dir()

    def _matches(self, path: Path) -> bool:
        if not self._filters:
            return True
        stem = path.stem.upper()
        return any(f in stem for f in self._filters)

    def instrument_files(self) -> list[Path]:
        """Tick instrument parquet files (events.parquet excluded), filtered,
        deterministically sorted by name."""
        if not self.exists():
            return []
        return sorted(p for p in self.day_dir.glob("*.parquet")
                      if p.name != "events.parquet" and self._matches(p))

    def event_file(self) -> Path | None:
        p = self.day_dir / "events.parquet"
        return p if p.exists() else None

    def read_table(self, path: Path):
        """Read a parquet file; return None (logged) if unreadable — never raise."""
        try:
            return pq.read_table(str(path))
        except Exception as exc:  # noqa: BLE001 - corrupt/truncated file
            log.warning("replay: skipping unreadable file %s (%s)", path.name, exc)
            return None

    def coverage(self) -> Coverage:
        date = self.day_dir.name
        cov = Coverage(date=date)
        # Recorder's own verdict, if present.
        rp = self.day_dir / "report.json"
        if rp.exists():
            try:
                r = json.loads(rp.read_text())
                cov.status = r.get("status") or r.get("overall")
                cov.coverage_pct = (r.get("coverage") or {}).get("coverage_pct")
            except Exception:  # noqa: BLE001
                pass
        for f in self.instrument_files():
            try:
                n = pq.ParquetFile(str(f)).metadata.num_rows
            except Exception:  # noqa: BLE001
                cov.unreadable_files.append(f.name)
                continue
            cov.per_instrument[f.name] = n
            cov.total_tick_rows += n
            if n > 0:
                cov.tick_instruments += 1
            else:
                cov.empty_instruments += 1
        ev = self.event_file()
        if ev is not None:
            try:
                cov.total_event_rows = pq.ParquetFile(str(ev)).metadata.num_rows
            except Exception:  # noqa: BLE001
                cov.unreadable_files.append(ev.name)
        return cov


def default_day_dir(data_dir: Path, date_str: str | None) -> Path:
    d = date_str or datetime.now(IST).date().isoformat()
    return Path(data_dir) / d
