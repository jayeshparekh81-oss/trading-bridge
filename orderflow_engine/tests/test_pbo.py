"""PBO (CSCV) module tests — t1..t6 per the P1 spec, deterministic throughout.

t1 genuinely-superior system  -> LOW PBO (< 0.2)
t2 deliberately overfit (IS-tuned noise inverts OOS) -> HIGH PBO
t3 identical systems -> PBO == 0.5 (tie handling, no crash)
t4 pure random noise -> PBO ~ 0.5
t5 guardrail refusal on insufficient blocks / configs (incl. current-recorded-days case)
t6 --pbo off -> byte-identical CLI output, no PBO artifacts; --pbo on writes NEW file only
"""

from __future__ import annotations

import io
import json
import random
from contextlib import redirect_stdout

from research.pbo import (REFUSAL, build_matrix, chronological_blocks, cscv,
                          pbo_from_trades, summary)
from research.walkforward import Trade, _day_open_ns, main as wf_main

NS = 1_000_000_000
DAYS12 = [f"2026-06-{d:02d}" for d in range(1, 13)]     # 12 synthetic days >= 10 blocks


def _trades(day: str, rs: list[float], cross_block: bool = False) -> list[Trade]:
    o = _day_open_ns(day)
    exit_off = (30 * 3600 * NS) if cross_block else (3600 * NS)   # 30h crosses the day
    return [Trade(day, o + i * 60 * NS, o + i * 60 * NS + exit_off, r)
            for i, r in enumerate(rs)]


# ---------------------------------------------------------------- t1: superior
def test_t1_genuinely_superior_system_low_pbo():
    rng = random.Random(11)
    cfgs: dict = {"hero": [], **{f"noise{k}": [] for k in range(5)}}
    for d in DAYS12:
        cfgs["hero"] += _trades(d, [0.5 + rng.uniform(-0.05, 0.05) for _ in range(4)])
        for k in range(5):
            cfgs[f"noise{k}"] += _trades(d, [rng.uniform(-0.4, 0.4) for _ in range(4)])
    res = pbo_from_trades(cfgs, DAYS12, s=10)
    assert not res.refused and res.n_splits == 252            # C(10,5)
    assert res.pbo < 0.2                                      # skillful selection survives OOS


# ---------------------------------------------------------------- t2: overfit
def test_t2_overfit_is_tuned_noise_high_pbo():
    # antisymmetric configs: +1 on a random half of the blocks, -1 on the rest (zero-sum).
    # The IS-best is the config whose +1s concentrate IN-SAMPLE -> its OOS blocks are the
    # -1s -> the IS winner systematically INVERTS out-of-sample. Classic overfit shape.
    rng = random.Random(7)
    M = []
    for _ in range(12):
        cols = list(range(10))
        rng.shuffle(cols)
        row = [0.0] * 10
        for j in cols[:5]:
            row[j] = 1.0
        for j in cols[5:]:
            row[j] = -1.0
        M.append(row)
    res = cscv(M)
    assert not res.refused
    assert res.pbo > 0.6                                      # IS winner inverts OOS
    s = summary(res)
    assert s["oos_mean_of_chosen"] < s["is_mean_of_chosen"]   # degradation visible


# ---------------------------------------------------------------- t3: identical
def test_t3_identical_systems_pbo_half_no_crash():
    M = [[0.1, -0.2, 0.3, 0.0, 0.05, -0.1, 0.2, 0.15, -0.05, 0.1]] * 6
    res = cscv(M)
    assert not res.refused
    assert res.pbo == 0.5                                     # ties -> lambda 0 counted half
    assert all(l == 0.0 for l in res.lambdas)


# ---------------------------------------------------------------- t4: noise
def test_t4_random_noise_pbo_near_half():
    rng = random.Random(42)
    M = [[rng.gauss(0, 1) for _ in range(10)] for _ in range(8)]
    res = cscv(M)
    assert not res.refused
    assert 0.3 <= res.pbo <= 0.7                              # selection is uninformative


# ---------------------------------------------------------------- t5: guardrail
def test_t5_guardrail_refusals():
    rng = random.Random(3)
    # (a) too few days for 10 blocks — the CURRENT-recorded-days case: MUST refuse
    few_days = DAYS12[:6]
    cfgs = {f"c{k}": sum((_trades(d, [rng.uniform(-1, 1)]) for d in few_days), [])
            for k in range(5)}
    res = pbo_from_trades(cfgs, few_days, s=10)
    assert res.refused and REFUSAL in res.reason
    # (b) too few configs
    cfgs3 = {f"c{k}": sum((_trades(d, [0.1]) for d in DAYS12), []) for k in range(3)}
    assert pbo_from_trades(cfgs3, DAYS12, s=10).refused
    # (c) matrix-level: short/odd block grids refuse
    assert cscv([[0.0] * 8] * 6).refused
    assert cscv([[0.0] * 9] * 6, s_required=9).refused        # odd S refuses too


# ---------------------------------------------------------------- purge machinery
def test_purge_drops_cross_block_trades_and_flag_disables():
    cfgs = {f"c{k}": [] for k in range(4)}
    for d in DAYS12:
        for k in range(4):
            leak = (d == DAYS12[3] and k == 0)
            cfgs[f"c{k}"] += _trades(d, [0.9] if leak else [0.2], cross_block=leak)
    m_purged, dropped = build_matrix(cfgs, DAYS12, 10, purge=True)
    m_kept, dropped_off = build_matrix(cfgs, DAYS12, 10, purge=False)
    assert dropped == 1 and dropped_off == 0
    assert m_purged != m_kept                                  # the leaker changed a cell
    # blocks are chronological + cover all days exactly once
    blocks = chronological_blocks(DAYS12, 10)
    assert [d for b in blocks for d in b] == sorted(DAYS12)


# ---------------------------------------------------------------- t6: flag off
def test_t6_pbo_flag_off_byte_identical_and_on_writes_new_file(tmp_path):
    argv_base = ["prog", "--days", ",".join(DAYS12[:4]), "--n-perm", "3"]
    buf1, buf2 = io.StringIO(), io.StringIO()
    with redirect_stdout(buf1):
        wf_main(argv_base)
    with redirect_stdout(buf2):
        wf_main(argv_base)
    assert buf1.getvalue() == buf2.getvalue()                  # deterministic
    assert "PBO" not in buf1.getvalue()                        # flag off -> zero PBO output
    # flag ON with too few days -> the guardrail REFUSES loudly (no silent numbers)
    buf3 = io.StringIO()
    with redirect_stdout(buf3):
        wf_main(argv_base + ["--pbo"])
    out3 = buf3.getvalue()
    assert out3.startswith(buf1.getvalue()[:200])              # base output unchanged
    assert REFUSAL in out3
    # flag ON with enough days -> runs, and --pbo-out writes a NEW file only
    out_file = tmp_path / "pbo_demo.json"
    buf4 = io.StringIO()
    with redirect_stdout(buf4):
        wf_main(["prog", "--days", ",".join(DAYS12), "--n-perm", "3",
                 "--pbo", "--pbo-out", str(out_file)])
    assert "PBO = " in buf4.getvalue()
    rep = json.loads(out_file.read_text())
    assert rep["refused"] is False and rep["n_splits"] == 252
