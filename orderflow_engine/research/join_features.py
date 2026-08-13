"""CANDIDATE↔FEATURE JOIN (M2 tool, 2026-07-21) — reads existing analysis outputs,
writes ONE new file per day. Never modifies any source file.

Join key: ``ts_ns`` (int64 epoch-ns = the candidate's tick-bar ``end_ts_ns``).
  * P6 depth_proxies_<SYM>.json  — exact end_ts_ns match (natural 1:1).
  * P5 price_efficiency_<SYM>.json — rows are index-aligned with NO ts field; joined via
    the <SYM>_<sid>.bars.parquet ts-spine when present (tick bars, end_ts_ns order);
    no spine -> status no_ts_spine (never guessed); length mismatch -> schema_mismatch.
  * P8 bar_quality_<SYM>.json — session-level dict, BROADCAST to every candidate of that
    day+instrument (status session_level).
  * LAR lar_study_<SYM>.json — per-session-machine: (a) AS-OF state per level = the last
    transition with ts_ns <= candidate ts_ns (strictly causal; FAR before any transition);
    (b) session-level final_state per level broadcast.

Output: <analysis_root>/<day>/candidate_features.parquet — all signal columns (legacy
19-col files pass through with the 4 post-netR columns as nulls + signals_schema =
'legacy_19col'), prefixed feature columns (p5_/p6_/p8_/lar_), and per-source status
columns {p5,p6,p8,lar}_join in {ok, no_file, no_ts_spine, no_match_ts, session_level,
schema_mismatch}. Rows are NEVER dropped. Idempotent: overwrites only its own output.
One analysis root per invocation (host or clone tree) — roots are never merged.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

NEWER_COLS = ("cost_r", "realized_r_net", "lots", "risk_inr")
P6_FIELDS = ("bid_refills", "bid_refill_ratio", "bid_cancel_qty", "bid_walls",
             "ask_refills", "ask_refill_ratio", "ask_cancel_qty", "ask_walls",
             "bid_cancel_qty_w", "bid_refills_w", "bid_walls_w",
             "ask_cancel_qty_w", "ask_refills_w", "ask_walls_w")
P5_FIELDS = ("up", "dn", "up_w", "dn_w")
P8_FIELDS = ("flat_bar_rate", "dur_q50", "dur_q90_q10", "range_med", "vol_med", "trades_med")
LAR_LEVELS = ("PDH", "PDL", "ORH", "ORL")


def _load_json(path: Path):
    try:
        return json.loads(path.read_text()) if path.exists() else None
    except Exception:                                    # noqa: BLE001
        return "corrupt"


def _bars_spine(day_dir: Path, inst: str) -> list[int] | None:
    """end_ts_ns of the instrument's TICK bars, in file order (the P5 index spine)."""
    cands = sorted(day_dir.glob(f"{inst}_*.bars.parquet"))
    if not cands:
        return None
    t = pq.read_table(str(cands[0]))
    cols = t.column_names
    end = t.column("end_ts_ns").to_pylist()
    if "bar_type" in cols:
        bt = t.column("bar_type").to_pylist()
        end = [e for e, b in zip(end, bt) if b == "tick"]
    return end


def _p8_flat(quality: dict) -> dict:
    d = quality.get("duration_s") or {}
    return {"flat_bar_rate": quality.get("flat_bar_rate"),
            "dur_q50": d.get("q50"), "dur_q90_q10": d.get("q90_q10_ratio"),
            "range_med": (quality.get("range_pts") or {}).get("median"),
            "vol_med": (quality.get("volume") or {}).get("median"),
            "trades_med": (quality.get("trades_per_bar") or {}).get("median")}


def _lar_asof(transitions: list[dict], ts: int) -> str:
    state = "FAR"
    for t in transitions:                                # transitions are time-ordered
        if int(t["ts_ns"]) <= ts:
            state = t["new"]
        else:
            break
    return state


def join_day(day: str, analysis_root: str | Path) -> dict:
    root = Path(analysis_root)
    day_dir = root / day
    sig_path = day_dir / "signals.parquet"
    if not sig_path.exists():
        return {"day": day, "refused": f"no signals.parquet under {day_dir}"}
    t = pq.read_table(str(sig_path))
    n = t.num_rows
    sig = {c: t.column(c).to_pylist() for c in t.column_names}
    legacy = any(c not in sig for c in NEWER_COLS)
    for c in NEWER_COLS:                                 # legacy 19-col -> nulls + noted
        sig.setdefault(c, [None] * n)
    out: dict[str, list] = {"day": [day] * n,
                            "signals_schema": [("legacy_19col" if legacy else "full_23col")] * n}
    for c in list(sig):
        out[c] = sig[c]
    # per-source caches per instrument
    insts = sorted(set(sig["instrument"]))
    p5 = {i: _load_json(day_dir / f"price_efficiency_{i}.json") for i in insts}
    p6 = {i: _load_json(day_dir / f"depth_proxies_{i}.json") for i in insts}
    p8 = {i: _load_json(day_dir / f"bar_quality_{i}.json") for i in insts}
    lar = {i: _load_json(day_dir / f"lar_study_{i}.json") for i in insts}
    spine = {i: _bars_spine(day_dir, i) for i in insts}
    p6_by_ts = {i: ({int(r["end_ts_ns"]): r for r in p6[i]["rows"]}
                    if isinstance(p6[i], dict) else {}) for i in insts}
    p5_by_ts: dict[str, dict[int, dict]] = {}
    p5_status: dict[str, str] = {}
    for i in insts:
        d = p5[i]
        if not isinstance(d, dict):
            p5_status[i] = "no_file"
            p5_by_ts[i] = {}
            continue
        sp = spine[i]
        if sp is None:
            p5_status[i] = "no_ts_spine"
            p5_by_ts[i] = {}
        elif len(sp) != len(d.get("rows", [])):
            p5_status[i] = "schema_mismatch"             # spine and rows disagree — refuse to guess
            p5_by_ts[i] = {}
        else:
            p5_status[i] = "ok"
            p5_by_ts[i] = {int(ts): r for ts, r in zip(sp, d["rows"])}
    # feature columns
    for f in P5_FIELDS:
        out[f"p5_{f}"] = [None] * n
    for f in P6_FIELDS:
        out[f"p6_{f}"] = [None] * n
    for f in P8_FIELDS:
        out[f"p8_{f}"] = [None] * n
    for lv in LAR_LEVELS:
        out[f"lar_state_{lv}"] = [None] * n
        out[f"lar_final_{lv}"] = [None] * n
    for s in ("p5_join", "p6_join", "p8_join", "lar_join"):
        out[s] = [None] * n
    for k in range(n):
        i = sig["instrument"][k]
        ts = int(sig["ts_ns"][k])
        # P5
        st = p5_status[i]
        if st == "ok":
            row = p5_by_ts[i].get(ts)
            if row is None:
                out["p5_join"][k] = "no_match_ts"
            else:
                out["p5_join"][k] = "ok"
                for f in P5_FIELDS:
                    out[f"p5_{f}"][k] = row.get(f)
        else:
            out["p5_join"][k] = st
        # P6
        if not isinstance(p6[i], dict):
            out["p6_join"][k] = "no_file"
        else:
            row = p6_by_ts[i].get(ts)
            if row is None:
                out["p6_join"][k] = "no_match_ts"
            else:
                out["p6_join"][k] = "ok"
                for f in P6_FIELDS:
                    out[f"p6_{f}"][k] = row.get(f)
        # P8 (session broadcast)
        if not isinstance(p8[i], dict):
            out["p8_join"][k] = "no_file"
        else:
            out["p8_join"][k] = "session_level"
            for f, v in _p8_flat(p8[i].get("quality", {})).items():
                out[f"p8_{f}"][k] = v
        # LAR (as-of + session final)
        if not isinstance(lar[i], dict):
            out["lar_join"][k] = "no_file"
        else:
            out["lar_join"][k] = "ok"
            for lv in LAR_LEVELS:
                node = lar[i].get("levels", {}).get(lv)
                if node:
                    out[f"lar_state_{lv}"][k] = _lar_asof(node.get("transitions", []), ts)
                    out[f"lar_final_{lv}"][k] = node.get("final_state")
    table = pa.table({k: pa.array(v) for k, v in out.items()})
    dest = day_dir / "candidate_features.parquet"
    pq.write_table(table, str(dest))                     # overwrites ONLY its own output
    return {"day": day, "rows": n, "out": str(dest), "legacy_schema": legacy,
            "p5": p5_status, "insts": insts}


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="research.join_features")
    ap.add_argument("--days", required=True)
    ap.add_argument("--analysis-root", default="analysis")
    args = ap.parse_args(argv)
    rc = 0
    for day in [d for d in args.days.split(",") if d.strip()]:
        rep = join_day(day, args.analysis_root)
        print(json.dumps(rep))
        if rep.get("refused"):
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
