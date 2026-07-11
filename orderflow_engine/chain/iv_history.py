"""Daily ATM-IV history + IV-percentile scaffolding (Module R5).

The ONE cross-day-accumulating derived artifact: one ATM-IV value per index per
session, appended to ``{history_dir}/{index}.parquet``. IV-percentile needs
history, so it builds day by day and is reported INSUFFICIENT (UNCALIBRATED) until
``min_days`` sessions have accrued. See OPS_NOTES — persist this durably post-Monday
(it is rebuildable only while the raw days still exist under retention).
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from recorder.writer import _atomic_write_table

IV_HISTORY_SCHEMA = pa.schema([
    pa.field("date", pa.string()),
    pa.field("atm_iv", pa.float64()),
])


def _path(history_dir: Path, index: str) -> Path:
    return Path(history_dir) / f"{index}.parquet"


def load_history(history_dir: Path, index: str) -> list[tuple[str, float]]:
    p = _path(history_dir, index)
    if not p.exists():
        return []
    t = pq.read_table(str(p))
    return list(zip(t.column("date").to_pylist(), t.column("atm_iv").to_pylist()))


def append_daily(history_dir: Path, index: str, date: str, atm_iv: float) -> Path:
    """Append (or replace) this date's ATM-IV; idempotent per date."""
    hist = {d: v for d, v in load_history(history_dir, index)}
    hist[date] = float(atm_iv)
    rows = [{"date": d, "atm_iv": hist[d]} for d in sorted(hist)]
    p = _path(history_dir, index)
    p.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_table(pa.Table.from_pylist(rows, schema=IV_HISTORY_SCHEMA), p)
    return p


def iv_percentile(history_dir: Path, index: str, current_iv: float,
                  min_days: int = 20) -> dict:
    """Percentile rank of current_iv among historical ATM-IV. Insufficient until
    min_days sessions exist."""
    vals = [v for _, v in load_history(history_dir, index) if v is not None]
    n = len(vals)
    if current_iv is None or n < min_days:
        return {"percentile": None, "insufficient": True, "days": n,
                "min_days": min_days}
    below = sum(1 for v in vals if v <= current_iv)
    return {"percentile": round(100.0 * below / n, 2), "insufficient": False,
            "days": n, "min_days": min_days}
