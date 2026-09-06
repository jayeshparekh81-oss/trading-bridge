"""qguard.py — THE quarantine guard. The ONLY S3 read path for depth_eval3 after the split (cp0_split.py runs before the
split and is the sole exception). Every request is logged to access_log.jsonl; a request for a CONFIRMATION date from any
stage other than the allow-list in QUARANTINE.json raises QuarantineError BEFORE any byte is read."""
from __future__ import annotations
import json, datetime as dt
from pathlib import Path
import pyarrow.parquet as pq
from pyarrow import fs
D3 = Path(__file__).resolve().parent; QUAR = D3 / "QUARANTINE.json"; LOG = D3 / "access_log.jsonl"; INV = D3 / "cp0_split.json"
class QuarantineError(RuntimeError): pass
def _quar():
    if not QUAR.exists(): raise QuarantineError("QUARANTINE.json missing — refusing to read anything")
    return json.loads(QUAR.read_text())
def _log(rec): 
    with LOG.open("a") as f: f.write(json.dumps(rec) + "\n")
def check(date: str, stage: str) -> None:
    q = _quar(); allowed = q["allowed_stages_for_confirmation"]
    if date in q["confirmation"] and stage not in allowed:
        _log({"ts": dt.datetime.now().isoformat(), "date": date, "stage": stage, "allowed": False}); raise QuarantineError(f"{date} is a CONFIRMATION date; stage {stage} may not read it (allowed: {allowed})")
def key_for(date: str, inst: str) -> str:
    inv = json.loads(INV.read_text())["inventory"]
    r = next(x for x in inv if x["date"] == date and x["inst"] == inst and "key" in x); return r["key"]
def load_session(date: str, inst: str, stage: str, columns: list[str]):
    """Guarded, logged S3 read. Raises QuarantineError before touching S3 if the date is quarantined for this stage."""
    check(date, stage); key = key_for(date, inst)
    _log({"ts": dt.datetime.now().isoformat(), "date": date, "inst": inst, "stage": stage, "allowed": True, "key": key})
    s3 = fs.S3FileSystem(region="ap-south-1")
    return pq.read_table(s3.open_input_file(key), columns=columns).to_pandas().sort_values(["ts_recv_ns", "seq_local"], kind="mergesort").reset_index(drop=True)
def access_log():
    return [json.loads(l) for l in LOG.read_text().splitlines()] if LOG.exists() else []
