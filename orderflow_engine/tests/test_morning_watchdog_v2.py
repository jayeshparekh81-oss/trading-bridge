"""Morning-watchdog-v2 tests (i)-(v) — mock docker/Telegram/clock, no real sends or waits.

(i)   golden GREEN on a fixture day-dir + healthy fake docker state
(ii)  YELLOW on BSE-file-missing but core growing
(iii) RED on core-not-growing, and RED on restarts>0
(iv)  holiday short-circuit
(v)   growth sampler on a STATIC file reports no-growth
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from scripts import morning_watchdog_v2 as w2

IST = timezone(timedelta(hours=5, minutes=30))
MKT = datetime(2026, 7, 23, 9, 20, tzinfo=IST)         # a weekday, market hours
OFF = datetime(2026, 7, 23, 18, 0, tzinfo=IST)         # after close
NO_HOL = frozenset()


# ---- fake docker ----
def _docker(status="running", restarts="0", image="sha-latest", latest="sha-latest"):
    def sh(cmd):
        if "inspect" in cmd and w2.LATEST_IMAGE in cmd:
            return latest + "\n"
        if "inspect" in cmd:
            return (f"/orderflow_recorder {status} {restarts} {image}\n"
                    f"/orderflow_depth_recorder {status} {restarts} {image}\n")
        return ""
    return sh


# ---- fixture day-dir ----
def _make_day(root, day, *, universe=500, bse_fut=True, bse_opts=40, core=("NIFTY_FUT", "BANKNIFTY_FUT")):
    d = root / "data" / day
    d.mkdir(parents=True, exist_ok=True)
    ins = []
    if bse_fut:
        ins.append({"symbol": "BSE_FUT", "security_id": w2.BSE_FUT_ID})
    for i in range(bse_opts):
        ins.append({"symbol": f"BSE_CE_{3000+i*100}_{80000+i}", "security_id": 80000 + i})
    for c in core:
        ins.append({"symbol": c, "security_id": 61088 + len(ins)})
    while len(ins) < universe:                          # pad to the target universe size
        ins.append({"symbol": f"NIFTY_CE_{20000+len(ins)}_{50000+len(ins)}", "security_id": 50000 + len(ins)})
    (d / "manifest.json").write_text(json.dumps({"instruments": ins[:universe]}))
    return d


def _size_fn(grow_map):
    """size_fn(day_dir, prefix) -> returns s1 then s2 from a per-prefix (s1, s2) map.
    None prefix -> missing file."""
    calls = {}
    def fn(day_dir, prefix):
        pair = grow_map.get(prefix)
        if pair is None:
            return None
        i = calls.get(prefix, 0)
        calls[prefix] = i + 1
        return pair[min(i, 1)]
    return fn


def _depth(root, day, *, parts=100):
    p = root / "data" / day / "depth" / "parts" / "ICICIBANK_4963"
    p.mkdir(parents=True, exist_ok=True)
    for i in range(parts):
        (p / f"part-{i:04d}.parquet").write_text("x")


# ---------- (i) GREEN ----------
def test_i_green(tmp_path):
    _make_day(tmp_path, "2026-07-23")
    _depth(tmp_path, "2026-07-23", parts=100)
    grow = {"NIFTY_FUT": (100, 200), "BANKNIFTY_FUT": (100, 200), "BSE_FUT": (100, 200)}
    # depth grows: give check_depth a sleep that adds a part between samples
    def sleep_fn(_s):
        (tmp_path / "data/2026-07-23/depth/parts/ICICIBANK_4963/part-9999.parquet").write_text("x")
    v, msg = w2.run(tmp_path, now=MKT, sh=_docker(), holidays=NO_HOL,
                    sleep_fn=sleep_fn, size_fn=_size_fn(grow))
    assert v == "GREEN", msg
    assert "core+BSE flowing" in msg and "restarts=0" in msg


# ---------- (ii) YELLOW: BSE file missing, core growing ----------
def test_ii_yellow_bse_missing(tmp_path):
    _make_day(tmp_path, "2026-07-23", bse_fut=True)     # manifest fine
    _depth(tmp_path, "2026-07-23")
    grow = {"NIFTY_FUT": (100, 200), "BANKNIFTY_FUT": (100, 200), "BSE_FUT": None}  # BSE file absent
    v, msg = w2.run(tmp_path, now=MKT, sh=_docker(), holidays=NO_HOL,
                    sleep_fn=lambda s: None, size_fn=_size_fn(grow))
    assert v == "YELLOW", msg
    assert "NOT an emergency" in msg and "no rollback" in msg


def test_ii_yellow_bse_opts_low(tmp_path):
    _make_day(tmp_path, "2026-07-23", bse_opts=10)      # < 35 BSE options
    _depth(tmp_path, "2026-07-23")
    grow = {"NIFTY_FUT": (100, 200), "BANKNIFTY_FUT": (100, 200), "BSE_FUT": (100, 200)}
    v, msg = w2.run(tmp_path, now=MKT, sh=_docker(), holidays=NO_HOL,
                    sleep_fn=lambda s: None, size_fn=_size_fn(grow))
    assert v == "YELLOW" and "BSE opts 10" in msg


# ---------- (iii) RED ----------
def test_iii_red_core_not_growing(tmp_path):
    _make_day(tmp_path, "2026-07-23")
    _depth(tmp_path, "2026-07-23")
    grow = {"NIFTY_FUT": (100, 100), "BANKNIFTY_FUT": (100, 200), "BSE_FUT": (100, 200)}  # NIFTY static
    v, msg = w2.run(tmp_path, now=MKT, sh=_docker(), holidays=NO_HOL,
                    sleep_fn=lambda s: None, size_fn=_size_fn(grow))
    assert v == "RED", msg
    assert "GENUINE ROLLBACK TRIGGER" in msg and "NIFTY_FUT" in msg and "STEP-0 log dump" in msg


def test_iii_red_restarts(tmp_path):
    _make_day(tmp_path, "2026-07-23")
    _depth(tmp_path, "2026-07-23")
    grow = {"NIFTY_FUT": (100, 200), "BANKNIFTY_FUT": (100, 200), "BSE_FUT": (100, 200)}
    v, msg = w2.run(tmp_path, now=MKT, sh=_docker(restarts="3"), holidays=NO_HOL,
                    sleep_fn=lambda s: None, size_fn=_size_fn(grow))
    assert v == "RED" and "crash-loop" in msg


def test_iii_red_container_down(tmp_path):
    _make_day(tmp_path, "2026-07-23")
    grow = {c: (100, 200) for c in ("NIFTY_FUT", "BANKNIFTY_FUT", "BSE_FUT")}
    v, msg = w2.run(tmp_path, now=MKT, sh=_docker(status="exited"), holidays=NO_HOL,
                    sleep_fn=lambda s: None, size_fn=_size_fn(grow))
    assert v == "RED" and "crash-loop/down" in msg


# ---------- (iv) holiday ----------
def test_iv_holiday_short_circuit(tmp_path):
    # a Sunday -> weekend short-circuit (no docker/growth touched)
    sunday = datetime(2026, 7, 26, 9, 20, tzinfo=IST)
    def boom(cmd):
        raise AssertionError("docker must not be called on a holiday/weekend")
    v, msg = w2.run(tmp_path, now=sunday, sh=boom, holidays=NO_HOL)
    assert v == "HOLIDAY" and "no session" in msg
    # explicit NSE holiday on a weekday
    hol = frozenset({date(2026, 7, 23)})
    v2, msg2 = w2.run(tmp_path, now=MKT, sh=boom, holidays=hol)
    assert v2 == "HOLIDAY"


# ---------- (v) growth sampler on a static file ----------
def test_v_growth_sampler_static_no_growth(tmp_path):
    d = tmp_path / "data" / "2026-07-23"
    d.mkdir(parents=True)
    f = d / "NIFTY_FUT_61093.parquet"
    f.write_text("static")                              # never changes between samples
    out = w2.sample_growth(tmp_path, "2026-07-23", ["NIFTY_FUT"], market_open=True,
                           sleep_fn=lambda s: None)     # real size_fn, real file, no wait
    assert out["NIFTY_FUT"]["grew"] is False            # identical size -> no growth
    assert out["NIFTY_FUT"]["present"] is True
    # off-hours: state only, grew is None, sampler never sleeps
    calls = []
    out2 = w2.sample_growth(tmp_path, "2026-07-23", ["NIFTY_FUT"], market_open=False,
                            sleep_fn=lambda s: calls.append(s))
    assert out2["NIFTY_FUT"]["grew"] is None and out2["NIFTY_FUT"]["present"] is True
    assert calls == []                                  # no sleep off-hours
