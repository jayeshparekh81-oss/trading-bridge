"""PBO — Probability of Backtest Overfitting via CSCV (Bailey/Borwein/López de Prado/Zhu).

The question this answers: "when we pick the IS-best configuration, how often is it
BELOW-MEDIAN out-of-sample?" PBO ≈ 0 → selection carries real skill; PBO ≈ 0.5 → selection
is noise; PBO → 1 → the IS winner systematically INVERTS OOS (classic overfit).

Mechanics (CSCV):
  * Input: performance matrix M (N_configs × S blocks), S=10 CHRONOLOGICAL blocks built
    from per-day results. Block metric = MEAN R of the config's trades in that block; a
    config with NO trades in a block contributes 0.0 for that block (documented choice:
    "didn't trade" is a flat outcome, not missing data — configs must be comparable on a
    common block grid).
  * All C(S, S/2) combinatorially symmetric splits: each combination of S/2 blocks is IS,
    the complement is OOS. Combining blocks = mean of block metrics.
  * Per split: pick the IS-best config n*; find its RELATIVE RANK w among all configs'
    OOS performance (average-rank for ties, scaled to (0,1) by /(N+1));
    λ = logit(w) = ln(w/(1−w)).
  * PBO = share of splits with λ < 0. Exact ties at the OOS median give λ = 0 and are
    counted HALF (so N identical configs → PBO = 0.5, the honest "selection is
    uninformative" answer, not 0).
  * Purge (default ON, flag to disable): consistent with the pre-registered purge rule —
    a trade whose exit crosses its entry-block's boundary is DROPPED from the matrix
    build (it would leak between IS and OOS blocks). On the real pipeline this is a
    structural NO-OP (sim positions are intraday and force-closed at session end, so no
    trade spans a day boundary — see trades_from_signals in walkforward.py), but the
    machinery exists and is tested for any future multi-day holding.

HONESTY GUARDRAIL: PBO is only meaningful with a full block grid and a real config set.
With fewer than S usable blocks (needs ≥ S days) or N_configs < 4 the answer is
degenerate — the module REFUSES ("INSUFFICIENT DATA — PBO degenerate on this sample").
On the currently recorded days it MUST refuse; its real use is the completed 15-day set.

R basis: mean R per block uses net-of-cost R (realized_r_net) when the cost wiring has
populated it for EVERY fired trade in scope, else gross (realized_r) with a printed note
— see r_basis().

Research-lane only: nothing here reads or writes live config, and the walk-forward CLI
runs identically unless --pbo is passed (new output only).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Optional, Sequence

from research.walkforward import Trade, _day_open_ns

NS_PER_DAY = 24 * 3600 * 1_000_000_000
REFUSAL = "INSUFFICIENT DATA — PBO degenerate on this sample"


# ============================ result container ==============================
@dataclass(frozen=True)
class PBOResult:
    refused: bool
    reason: str = ""
    n_configs: int = 0
    n_blocks: int = 0
    n_splits: int = 0
    pbo: float = float("nan")
    lambdas: tuple[float, ...] = field(default_factory=tuple)
    # per-split (IS_perf, OOS_perf) of the IS-chosen config — the degradation cloud
    degradation: tuple[tuple[float, float], ...] = field(default_factory=tuple)
    metric_basis: str = "gross_r"          # 'net_r' | 'gross_r'
    purge_dropped: int = 0                 # trades dropped by the boundary purge


# ============================ block construction ============================
def chronological_blocks(days: Sequence[str], s: int) -> list[list[str]]:
    """S contiguous chronological blocks of near-equal size (first blocks take the
    remainder). Requires len(days) >= s (else the caller's guardrail refuses)."""
    ds = sorted(days)
    n = len(ds)
    base, rem = divmod(n, s)
    blocks, i = [], 0
    for j in range(s):
        size = base + (1 if j < rem else 0)
        blocks.append(ds[i:i + size])
        i += size
    return blocks


def build_matrix(trades_by_config: dict, days: Sequence[str], s: int,
                 *, purge: bool = True) -> tuple[list[list[float]], int]:
    """M[i][j] = mean R of config i's trades in block j (0.0 when the config has no
    trades there). ``purge`` drops trades whose exit_ns crosses their entry-block's last
    day (cross-block leakers) — the pre-registered purge rule at block granularity."""
    blocks = chronological_blocks(days, s)
    block_of = {d: j for j, blk in enumerate(blocks) for d in blk}
    block_end_ns = {j: _day_open_ns(blk[-1]) + NS_PER_DAY for j, blk in enumerate(blocks)}
    names = sorted(trades_by_config)
    M: list[list[float]] = []
    dropped = 0
    for name in names:
        sums = [0.0] * s
        counts = [0] * s
        for t in trades_by_config[name]:
            j = block_of.get(t.day)
            if j is None:
                continue
            if purge and t.exit_ns > block_end_ns[j]:
                dropped += 1                      # would leak into the next block
                continue
            sums[j] += t.r
            counts[j] += 1
        M.append([(sums[j] / counts[j]) if counts[j] else 0.0 for j in range(s)])
    return M, dropped


# ============================ CSCV core =====================================
def _avg_rank(values: Sequence[float], idx: int) -> float:
    """Average rank (1 = worst … N = best) of values[idx], ties → mean rank."""
    v = values[idx]
    below = sum(1 for x in values if x < v)
    ties = sum(1 for x in values if x == v)
    return below + (ties + 1) / 2.0


def cscv(M: Sequence[Sequence[float]], *, s_required: int = 10,
         min_configs: int = 4, metric_basis: str = "gross_r",
         purge_dropped: int = 0) -> PBOResult:
    """CSCV over an N×S matrix. Refuses (never guesses) below the honesty guardrail."""
    n = len(M)
    s = len(M[0]) if n else 0
    if n < min_configs or s < s_required or s % 2:
        return PBOResult(refused=True,
                         reason=f"{REFUSAL} (configs={n} < {min_configs} or "
                                f"blocks={s} < {s_required} or odd)",
                         n_configs=n, n_blocks=s, metric_basis=metric_basis)
    half = s // 2
    lambdas: list[float] = []
    degradation: list[tuple[float, float]] = []
    for is_blocks in combinations(range(s), half):
        oos_blocks = tuple(j for j in range(s) if j not in is_blocks)
        is_perf = [sum(row[j] for j in is_blocks) / half for row in M]
        oos_perf = [sum(row[j] for j in oos_blocks) / half for row in M]
        star = max(range(n), key=lambda i: is_perf[i])          # IS-best (ties → lowest idx)
        w = _avg_rank(oos_perf, star) / (n + 1)                 # relative OOS rank in (0,1)
        lambdas.append(math.log(w / (1.0 - w)))
        degradation.append((round(is_perf[star], 6), round(oos_perf[star], 6)))
    neg = sum(1 for l in lambdas if l < 0)
    zero = sum(1 for l in lambdas if l == 0)
    pbo = (neg + 0.5 * zero) / len(lambdas)                     # ties count half (see doc)
    return PBOResult(refused=False, n_configs=n, n_blocks=s, n_splits=len(lambdas),
                     pbo=round(pbo, 4), lambdas=tuple(round(l, 6) for l in lambdas),
                     degradation=tuple(degradation), metric_basis=metric_basis,
                     purge_dropped=purge_dropped)


def pbo_from_trades(trades_by_config: dict, days: Sequence[str], *, s: int = 10,
                    purge: bool = True, min_configs: int = 4,
                    metric_basis: str = "gross_r") -> PBOResult:
    """Guardrailed entry point: days → S chronological blocks → matrix → CSCV."""
    usable = sorted(set(days))
    if len(usable) < s or len(trades_by_config) < min_configs:
        return PBOResult(refused=True,
                         reason=f"{REFUSAL} (days={len(usable)} < blocks={s} or "
                                f"configs={len(trades_by_config)} < {min_configs})",
                         n_configs=len(trades_by_config), n_blocks=min(len(usable), s),
                         metric_basis=metric_basis)
    M, dropped = build_matrix(trades_by_config, usable, s, purge=purge)
    return cscv(M, s_required=s, min_configs=min_configs, metric_basis=metric_basis,
                purge_dropped=dropped)


# ============================ R basis (net when wired) ======================
def r_basis(analysis_root: str | Path, days: Sequence[str]) -> str:
    """'net_r' when the cost wiring has populated realized_r_net for EVERY fired trade in
    scope, else 'gross_r' (the caller prints the note). Reading only — never estimates."""
    import pyarrow.parquet as pq
    rootp = Path(analysis_root)
    saw_any = False
    for d in days:
        p = rootp / d / "signals.parquet"
        if not p.exists():
            continue
        t = pq.read_table(str(p))
        cols = {c: t.column(c).to_pylist() for c in t.column_names}
        for i in range(t.num_rows):
            if cols.get("fired", [False] * t.num_rows)[i] \
                    and cols.get("realized_r", [None])[i] is not None:
                saw_any = True
                if "realized_r_net" not in cols or cols["realized_r_net"][i] is None:
                    return "gross_r"
    return "net_r" if saw_any else "gross_r"


# ============================ report formatting =============================
def summary(res: PBOResult) -> dict:
    if res.refused:
        return {"refused": True, "reason": res.reason,
                "n_configs": res.n_configs, "n_blocks": res.n_blocks}
    ls = sorted(res.lambdas)
    med = ls[len(ls) // 2]
    deg_is = [a for a, _ in res.degradation]
    deg_oos = [b for _, b in res.degradation]
    return {"refused": False, "pbo": res.pbo, "n_configs": res.n_configs,
            "n_blocks": res.n_blocks, "n_splits": res.n_splits,
            "metric_basis": res.metric_basis, "purge_dropped": res.purge_dropped,
            "lambda_median": round(med, 4),
            "lambda_share_neg": round(sum(1 for l in res.lambdas if l < 0) / len(ls), 4),
            "is_mean_of_chosen": round(sum(deg_is) / len(deg_is), 4),
            "oos_mean_of_chosen": round(sum(deg_oos) / len(deg_oos), 4)}


def print_report(res: PBOResult) -> None:
    print("-" * 78)
    print("PBO (CSCV) — probability the IS-chosen config is BELOW-MEDIAN out-of-sample")
    if res.refused:
        print(f"  {res.reason}")
        print("-" * 78)
        return
    s = summary(res)
    print(f"  configs={s['n_configs']}  blocks={s['n_blocks']}  splits={s['n_splits']}  "
          f"basis={s['metric_basis']}  purge_dropped={s['purge_dropped']}")
    print(f"  PBO = {s['pbo']:.3f}   (0≈skill · 0.5≈noise · →1 inverts OOS)")
    print(f"  lambda: median={s['lambda_median']}  share<0={s['lambda_share_neg']}")
    print(f"  degradation (IS-chosen): IS mean={s['is_mean_of_chosen']}  "
          f"OOS mean={s['oos_mean_of_chosen']}")
    print("-" * 78)
