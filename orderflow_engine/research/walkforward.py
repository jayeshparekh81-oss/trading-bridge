"""Walk-forward validation harness (research, read-only, leak-proof).

WHY (2026-07-17): G2's gate is "PF >= 1.5 AFTER COSTS on OUT-OF-SAMPLE data". With
15 days landing ~31 Jul we need the validation tooling to EXIST FIRST, or every sweep
is in-sample fitting. This package is that tooling. It touches no config, wires no
component — it CONSUMES whatever the sim produces (a list of Trades with an outcome
`r`, today `realized_r`, later net-of-cost R) via an `evaluator` seam and answers:
is a sweep result real, or is it overfitting / noise / multiple-testing luck?

Four capabilities (all pure, deterministic, tested):
  1. WALK-FORWARD SPLITTER — anchored (expanding) + rolling, with López de Prado
     PURGING (drop train trades whose outcome overlaps the test window) and EMBARGO
     (drop test trades right after the boundary). Time order is SACRED — never shuffled.
  2. SWEEP RUNNER (Sweep 2.0 in code) — one knob, a PRE-REGISTERED range recorded in
     the output, the FULL curve (not just the argmax), PLATEAU detection, and a ±20%
     PERTURBATION fragility check.
  3. PERMUTATION / NULL — shuffle the outcome labels (breaking param<->return structure
     while preserving the return distribution), re-run the same sweep: the false-positive
     floor. A real result must beat it. (This killed the 'loss autocorrelation' finding.)
  4. DEFLATED SHARPE (López de Prado) — deflate the observed Sharpe for the NUMBER OF
     TRIALS + non-normality. Reported automatically on every sweep, never optional.

Determinism: no wall-clock, no unseeded RNG. Permutations use an explicit seed.
The `evaluator` (param_value, days) -> [Trade] is the ONLY seam to the strategy; the
harness never re-runs the pipeline itself. `trades_from_signals` bridges to persisted
sim output (realized_r). See tests/test_walkforward.py for the leak-proofs.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Optional, Sequence
from zoneinfo import ZoneInfo

NS = 1_000_000_000
IST = ZoneInfo("Asia/Kolkata")
_EULER_GAMMA = 0.5772156649015329


# ============================ data model =====================================
@dataclass(frozen=True)
class Trade:
    """One simulated trade. ``r`` is the outcome metric (realized_r now; net-of-cost R
    later — the harness is agnostic). ``entry_ns``/``exit_ns`` drive purge + embargo."""
    day: str            # session date "YYYY-MM-DD"
    entry_ns: int
    exit_ns: int
    r: float


# (param_value, days) -> trades produced at that param over those days. The seam.
Evaluator = Callable[[float, list[str]], list[Trade]]


@dataclass(frozen=True)
class Split:
    index: int
    train_days: tuple[str, ...]
    test_days: tuple[str, ...]
    embargo_days: tuple[str, ...]


def _day_open_ns(day: str) -> int:
    """Market-open (09:15 IST) epoch-ns for a session — the train/test boundary clock."""
    d = date.fromisoformat(day)
    return int(datetime(d.year, d.month, d.day, 9, 15, tzinfo=IST).timestamp() * NS)


# ============================ 1. walk-forward splitter =======================
def walk_forward_splits(days: Sequence[str], *, scheme: str = "anchored",
                        train_size: int, test_size: int = 1, embargo_days: int = 0,
                        step: Optional[int] = None) -> list[Split]:
    """Train/test splits with a STRICT time boundary — the test window is always LATER
    than its train window, never shuffled.

    scheme='anchored' (DEFAULT, recommended): train expands from day 0 → uses all history
    to date, mirroring how we'd actually retrain, and — critical with only ~15 days —
    never starves the train set. scheme='rolling': fixed-width train window (use only once
    N is large enough that a fixed window still has power; states its own trade-off).

    ``embargo_days`` whole sessions are dropped between train end and test start.
    """
    days = list(days)
    if days != sorted(days):
        raise ValueError("days must be ascending — time order is sacred, no shuffling")
    if len(set(days)) != len(days):
        raise ValueError("duplicate days in calendar")
    if scheme not in ("anchored", "rolling"):
        raise ValueError(f"unknown scheme {scheme!r}")
    if train_size < 1 or test_size < 1:
        raise ValueError("train_size and test_size must be >= 1")
    n = len(days)
    step = step or test_size
    out: list[Split] = []
    k = train_size                                  # train is days[..k); test starts after embargo
    idx = 0
    while k + embargo_days + test_size <= n:
        train = days[0:k] if scheme == "anchored" else days[max(0, k - train_size):k]
        emb = days[k:k + embargo_days]
        test = days[k + embargo_days:k + embargo_days + test_size]
        out.append(Split(idx, tuple(train), tuple(test), tuple(emb)))
        idx += 1
        k += step
    return out


def purge_train(train_trades: list[Trade], test_start_ns: int) -> list[Trade]:
    """PURGE (López de Prado): drop train trades still open at/after the test boundary —
    their outcome was realized using information that overlaps the test window."""
    return [t for t in train_trades if t.exit_ns < test_start_ns]


def embargo_test(test_trades: list[Trade], test_start_ns: int, embargo_ns: int) -> list[Trade]:
    """EMBARGO: drop test trades entered within ``embargo_ns`` of the boundary, where
    serial correlation with the (purged) train tail could still leak."""
    return [t for t in test_trades if t.entry_ns >= test_start_ns + embargo_ns]


# ============================ metrics ========================================
def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _var(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def _std(xs: Sequence[float]) -> float:
    return math.sqrt(_var(xs))


def profit_factor(rs: Sequence[float]) -> float:
    """Gross win / gross loss — the G2 gate metric. inf if no losers (flagged upstream)."""
    gain = sum(r for r in rs if r > 0)
    loss = -sum(r for r in rs if r < 0)
    if loss == 0:
        return float("inf") if gain > 0 else 0.0
    return gain / loss


def sharpe(rs: Sequence[float]) -> float:
    """Per-trade Sharpe (mean/sd of R). Not annualized — R-multiples are already scaled."""
    if len(rs) < 2:
        return 0.0
    s = _std(rs)
    return _mean(rs) / s if s > 0 else 0.0


def _skew(xs: Sequence[float]) -> float:
    n = len(xs)
    if n < 3:
        return 0.0
    m, sd = _mean(xs), math.sqrt(sum((x - _mean(xs)) ** 2 for x in xs) / n)
    if sd == 0:
        return 0.0
    return sum((x - m) ** 3 for x in xs) / n / sd ** 3


def _kurt(xs: Sequence[float]) -> float:
    """Full (non-excess) kurtosis: normal = 3."""
    n = len(xs)
    if n < 4:
        return 3.0
    m, sd = _mean(xs), math.sqrt(sum((x - _mean(xs)) ** 2 for x in xs) / n)
    if sd == 0:
        return 3.0
    return sum((x - m) ** 4 for x in xs) / n / sd ** 4


# normal CDF / inverse-CDF (pure; no scipy) ----------------------------------
def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """Inverse standard-normal CDF (Acklam's rational approximation, ~1e-9)."""
    if not 0.0 < p < 1.0:
        raise ValueError("p must be in (0,1)")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


# ============================ 2. sweep runner (Sweep 2.0) ====================
@dataclass(frozen=True)
class SweepSpec:
    """A PRE-REGISTERED sweep: knob name + the value range declared BEFORE the run.
    Recorded verbatim in the output so the range can't be retro-fitted."""
    knob: str
    values: tuple[float, ...]


def sweep_curve(spec: SweepSpec, score_fn: Callable[[float], float]) -> list[tuple[float, float]]:
    """The FULL curve (value, metric) in pre-registered order — plateaus stay visible."""
    return [(v, score_fn(v)) for v in spec.values]


def plateau_report(curve: list[tuple[float, float]]) -> dict:
    """Distinguish a STABLE REGION from a LONE SPIKE.

    Metrics: ``plateau_ratio`` = mean(immediate-neighbour metric) / best (→1 flat top,
    →0 spike); ``plateau_width`` = count of contiguous values within 10% of best around
    the peak; ``is_spike`` = best stands >2 SD above the rest of the curve AND its
    neighbours are weak. A spike is a fragility flag, not a result."""
    ms = [m for _, m in curve]
    best_i = max(range(len(ms)), key=lambda i: ms[i])       # TRUE argmax — inf (no losers) wins
    best_v, best_m = curve[best_i]
    finite = [m for m in ms if math.isfinite(m)]
    sd = _std(finite) if len(finite) > 1 else 0.0
    neigh = [ms[j] for j in (best_i - 1, best_i + 1) if 0 <= j < len(ms) and math.isfinite(ms[j])]
    if math.isfinite(best_m) and best_m != 0:
        neigh_mean = _mean(neigh) if neigh else best_m
        ratio = neigh_mean / best_m
        is_spike = bool(neigh and sd > 0 and (best_m - neigh_mean) > 2 * sd and ratio < 0.7)
    else:                                                   # inf or 0 peak — shape undefined
        neigh_mean, ratio, is_spike = (_mean(neigh) if neigh else best_m), 1.0, False
    # contiguous plateau width around the peak (>= 90% of best; for an inf peak, contiguous inf)
    def _near(m):
        return (math.isinf(m) and m > 0) if math.isinf(best_m) else (math.isfinite(m) and m >= 0.9 * best_m)
    width = 1
    for j in range(best_i - 1, -1, -1):
        if not _near(ms[j]):
            break
        width += 1
    for j in range(best_i + 1, len(ms)):
        if not _near(ms[j]):
            break
        width += 1
    return {"best_value": best_v, "best_metric": best_m,
            "neighbour_mean": round(neigh_mean, 4) if math.isfinite(neigh_mean) else neigh_mean,
            "plateau_ratio": round(ratio, 3), "plateau_width": width,
            "curve_sd": round(sd, 4), "is_spike": is_spike}


def perturbation_check(chosen: float, score_fn: Callable[[float], float], *,
                       jitter: float = 0.2, collapse_frac: float = 0.5) -> dict:
    """Re-run at ±10% and ±20% around the chosen value. FRAGILE if a small move COLLAPSES
    performance — the worst jittered metric drops more than ``collapse_frac`` of the base
    (a needle), vs a stable region where a ±20% move barely dents it. (A raw 2-SD test
    would false-flag any smooth peak, since a peak is always locally maximal — so we use
    relative drop, which cleanly separates a needle from a broad top.)"""
    fracs = (-jitter, -jitter / 2, jitter / 2, jitter)
    base = score_fn(chosen)
    jit = [score_fn(chosen * (1 + f)) for f in fracs]
    m, sd, worst = _mean(jit), _std(jit), min(jit)
    if math.isfinite(base) and base > 0:
        rel_drop = (base - worst) / base
        fragile = rel_drop > collapse_frac
    else:                                       # base 0 / inf: fragile iff neighbourhood differs
        rel_drop = float("inf") if worst != base else 0.0
        fragile = worst != base
    return {"chosen": chosen, "base_metric": round(base, 4), "jitter_mean": round(m, 4),
            "jitter_sd": round(sd, 4), "worst_rel_drop": round(rel_drop, 4) if math.isfinite(rel_drop) else rel_drop,
            "within_2sd": not fragile, "fragile": fragile}


# ============================ walk-forward + sweep composition ===============
@dataclass
class WalkForwardResult:
    scheme: str
    spec_knob: str
    spec_values: tuple[float, ...]
    per_split: list[dict]
    oos_r: list[float]
    wf_profit_factor: float
    wf_sharpe: float
    trial_sharpes: list[float]      # one per pre-registered value (for DSR n_trials)


def pass_days(days: Sequence[str], root: str | Path, *, require_pass: bool = True) -> list[str]:
    """Filter to PASS days BEFORE splitting. A DEGRADED day (report ``status`` != PASS — disk
    crash, low coverage, multi-session) would SILENTLY poison every train window (with
    chronological data, degraded days often lead → they land in TRAIN). So a degraded day is
    EXCLUDED by default. Reads ``data/<day>/report.json``. ``require_pass=False`` is the
    explicit override that keeps every day (to study degraded data deliberately). A missing/
    unreadable report is treated as NOT a PASS day."""
    if not require_pass:
        return list(days)
    rootp = Path(root)
    keep: list[str] = []
    for d in days:
        try:
            rep = json.loads((rootp / "data" / d / "report.json").read_text())
        except Exception:  # noqa: BLE001 - missing/unreadable -> not a clean session
            rep = None
        if rep is not None and rep.get("status") == "PASS":
            keep.append(d)
    return keep


def walk_forward_sweep(days: Sequence[str], evaluator: Evaluator, spec: SweepSpec, *,
                       scheme: str = "anchored", train_size: int, test_size: int = 1,
                       embargo_days: int = 0, embargo_ns: int = 0,
                       select_metric: Callable[[Sequence[float]], float] = profit_factor,
                       root: Optional[str | Path] = None, require_pass: bool = True
                       ) -> WalkForwardResult:
    """For each split: CHOOSE the best pre-registered value on the (purged) TRAIN window,
    then EVALUATE that single value on the UNSEEN (embargoed) TEST window. OOS returns are
    pooled across splits. Test data NEVER influences the choice — the argmax is computed
    strictly on train trades.

    When ``root`` is given, DEGRADED days (report status != PASS) are REFUSED before splitting
    (``require_pass=True`` default) — the splitter never trains on a disk-crash / low-coverage
    day. ``root=None`` (synthetic trades, no reports) skips the filter."""
    if root is not None:
        days = pass_days(days, root, require_pass=require_pass)
    splits = walk_forward_splits(days, scheme=scheme, train_size=train_size,
                                 test_size=test_size, embargo_days=embargo_days)
    per_split: list[dict] = []
    oos_r: list[float] = []
    for sp in splits:
        test_start = _day_open_ns(sp.test_days[0])
        # --- TRAIN: full curve on purged train trades, choose argmax IN-SAMPLE ---
        curve = []
        for v in spec.values:
            tr = purge_train([t for t in evaluator(v, list(sp.train_days))], test_start)
            curve.append((v, select_metric([t.r for t in tr])))
        pr = plateau_report(curve)
        best_v = pr["best_value"]
        # --- TEST: the train-chosen value on the embargoed, unseen test window ---
        test_tr = embargo_test([t for t in evaluator(best_v, list(sp.test_days))],
                               test_start, embargo_ns)
        test_r = [t.r for t in test_tr]
        oos_r.extend(test_r)
        per_split.append({
            "split": sp.index, "train_days": list(sp.train_days), "test_days": list(sp.test_days),
            "curve": [(v, round(m, 4)) for v, m in curve], "plateau": pr,
            "chosen_value": best_v, "n_test_trades": len(test_r),
            "test_profit_factor": round(profit_factor(test_r), 4),
            "test_sharpe": round(sharpe(test_r), 4),
        })
    # trial sharpes over the WHOLE calendar (the N configurations we actually tried) — DSR input
    trial_sharpes = [sharpe([t.r for t in evaluator(v, list(days))]) for v in spec.values]
    return WalkForwardResult(
        scheme=scheme, spec_knob=spec.knob, spec_values=spec.values, per_split=per_split,
        oos_r=oos_r, wf_profit_factor=profit_factor(oos_r), wf_sharpe=sharpe(oos_r),
        trial_sharpes=trial_sharpes)


# ============================ 3. permutation / null test =====================
def _trade_universe(evaluator: Evaluator, spec: SweepSpec,
                    days: Sequence[str]) -> dict[tuple[str, int], Trade]:
    """Every distinct trade (keyed by day+entry) the sweep can produce over ``days``."""
    seen: dict[tuple[str, int], Trade] = {}
    for v in spec.values:
        for t in evaluator(v, list(days)):
            seen.setdefault((t.day, t.entry_ns), t)
    return seen


def permutation_null(days: Sequence[str], evaluator: Evaluator, spec: SweepSpec, *,
                     n_perm: int = 200, seed: int = 0,
                     wf_kwargs: Optional[dict] = None,
                     metric: str = "profit_factor") -> dict:
    """NULL = 'the parameter has no relationship to outcomes'. We PERMUTE the outcome
    ``r`` across the trade universe — preserving the exact return DISTRIBUTION (so metric
    scale/variance are realistic) while destroying any param<->return / time<->return
    structure — then re-run the IDENTICAL walk-forward sweep. The distribution of the
    null walk-forward metric is our FALSE-POSITIVE FLOOR; a real result must beat it.

    Why permute r (not the fire-decisions): the sweep maximises a RETURN metric, so the
    only thing that could manufacture PF>1 under 'no edge' is a lucky assignment of
    returns to trades — which is exactly what this destroys."""
    wf_kwargs = dict(wf_kwargs or {})
    universe = _trade_universe(evaluator, spec, days)
    keys = sorted(universe)
    pool = [universe[k].r for k in keys]

    def _metric_of(res: WalkForwardResult) -> float:
        return res.wf_profit_factor if metric == "profit_factor" else res.wf_sharpe

    real = _metric_of(walk_forward_sweep(days, evaluator, spec, **wf_kwargs))
    null_vals: list[float] = []
    for i in range(n_perm):
        rng = random.Random(seed + i)
        perm = pool[:]
        rng.shuffle(perm)
        rmap = {k: perm[j] for j, k in enumerate(keys)}

        def null_eval(v: float, ds: list[str], _rmap=rmap) -> list[Trade]:
            return [Trade(t.day, t.entry_ns, t.exit_ns, _rmap[(t.day, t.entry_ns)])
                    for t in evaluator(v, ds)]

        null_vals.append(_metric_of(walk_forward_sweep(days, null_eval, spec, **wf_kwargs)))
    finite = sorted(x for x in null_vals if math.isfinite(x))
    beat = sum(1 for x in null_vals if x >= real)
    p_value = (beat + 1) / (n_perm + 1)                     # +1: real counts as one draw
    floor_95 = finite[int(0.95 * (len(finite) - 1))] if finite else float("nan")
    return {"metric": metric, "real": real, "n_perm": n_perm, "seed": seed,
            "null_mean": round(_mean(finite), 4) if finite else float("nan"),
            "null_p95_floor": round(floor_95, 4), "p_value": round(p_value, 4),
            "beats_floor": bool(math.isfinite(floor_95) and real > floor_95)}


# ============================ 3b. FIXED-STRATEGY nulls =======================
# WHY these are SEPARATE from permutation_null (2026-07-17, exposed by the first real-trade
# run): permutation_null shuffles the return-to-trade ASSIGNMENT, which PRESERVES THE SUM —
# so it answers "did my SWEEP pick luck?" (selection significance), NOT "is this RESULT luck?"
# for a FIXED strategy. A fixed strategy's net result is invariant under permutation, so it
# needs a null that changes the result: sign-flip (no directional edge) or bootstrap (sampling
# uncertainty). This gap survived EVERY synthetic test because they always had a sweep — the
# lesson: synthetic tests only probe the shapes you imagined.
def sign_flip_null(returns: Sequence[float], *,
                   statistic: Callable[[Sequence[float]], float] = _mean,
                   n_perm: int = 10000, seed: int = 0) -> dict:
    """FIXED-STRATEGY null — answers **'is this RESULT luck?'** (contrast permutation_null's
    'did my SWEEP pick luck?'). The null is "no directional edge": each trade's SIGN is a coin
    toss, magnitudes fixed. Flips each return's sign at random and recomputes ``statistic``
    (mean R by default; pass ``sum``/``sharpe`` for others). ``p_value`` = fraction of the
    sign-flip null >= observed. Seeded → deterministic."""
    xs = list(returns)
    if not xs:
        return {"observed": 0.0, "p_value": 1.0, "significant_0p05": False, "n_perm": n_perm}
    observed = statistic(xs)
    rng = random.Random(seed)
    null = [statistic([r if rng.random() < 0.5 else -r for r in xs]) for _ in range(n_perm)]
    p = (sum(1 for x in null if x >= observed) + 1) / (n_perm + 1)
    return {"observed": round(observed, 4), "n_perm": n_perm,
            "null_mean": round(_mean(null), 4), "null_sd": round(_std(null), 4),
            "p_value": round(p, 4), "significant_0p05": p < 0.05}


def bootstrap_null(returns: Sequence[float], *,
                   statistic: Callable[[Sequence[float]], float] = _mean,
                   n_boot: int = 10000, seed: int = 0, ci: float = 0.95) -> dict:
    """FIXED-STRATEGY null via RESAMPLING — the sampling uncertainty of ``statistic`` (mean R
    by default). Resamples the return series WITH replacement, recomputes the statistic, and
    reports the ``ci`` confidence interval + the fraction of resamples <= 0. If the CI straddles
    0 (or ``frac_le_0`` is large) the result is not distinguishable from zero at this N.
    Complements sign_flip_null — both answer 'is this RESULT real?', not 'did my sweep pick luck?'."""
    xs = list(returns)
    if len(xs) < 2:
        return {"observed": statistic(xs) if xs else 0.0, "ci_low": None, "ci_high": None,
                "significant": False, "reason": "need >=2 returns"}
    observed = statistic(xs)
    rng = random.Random(seed)
    n = len(xs)
    boot = sorted(statistic([xs[rng.randrange(n)] for _ in range(n)]) for _ in range(n_boot))
    lo = boot[int((1 - ci) / 2 * (n_boot - 1))]
    hi = boot[int((1 - (1 - ci) / 2) * (n_boot - 1))]
    frac_le0 = sum(1 for x in boot if x <= 0) / n_boot
    return {"observed": round(observed, 4), "ci_pct": ci, "ci_low": round(lo, 4),
            "ci_high": round(hi, 4), "frac_le_0": round(frac_le0, 4),
            "significant": lo > 0}


# ============================ 4. deflated Sharpe (LdP) =======================
def expected_max_sharpe(n_trials: int, sr_variance: float) -> float:
    """E[max SR] under the null across ``n_trials`` independent trials (López de Prado):
    sqrt(V)·[(1-γ)·Φ⁻¹(1-1/N) + γ·Φ⁻¹(1-1/(N·e))]. The benchmark the observed SR must clear."""
    if n_trials <= 1 or sr_variance <= 0:
        return 0.0
    a = _norm_ppf(1 - 1.0 / n_trials)
    b = _norm_ppf(1 - 1.0 / (n_trials * math.e))
    return math.sqrt(sr_variance) * ((1 - _EULER_GAMMA) * a + _EULER_GAMMA * b)


def deflated_sharpe(returns: Sequence[float], n_trials: int, *,
                    trial_sharpes: Optional[Sequence[float]] = None,
                    sr_variance: Optional[float] = None) -> dict:
    """DSR (López de Prado 2014): probability the TRUE Sharpe > 0 after deflating for
    (a) the number of trials tried and (b) return non-normality (skew/kurtosis).

    DSR = Φ[ (SR - SR0)·√(T-1) / √(1 - skew·SR + (kurt-1)/4·SR²) ], SR0 = expected_max_sharpe.
    Reported on EVERY sweep — the direct answer to 'try 100 things and pick the best'."""
    T = len(returns)
    if T < 2:
        return {"dsr": None, "reason": "need >=2 returns", "T": T}
    sr = sharpe(returns)
    sk, ku = _skew(returns), _kurt(returns)
    if sr_variance is None:
        sr_variance = _var(list(trial_sharpes)) if trial_sharpes and len(trial_sharpes) > 1 else 0.0
    sr0 = expected_max_sharpe(n_trials, sr_variance)
    denom = math.sqrt(max(1e-12, 1 - sk * sr + ((ku - 1) / 4.0) * sr * sr))
    dsr = _norm_cdf((sr - sr0) * math.sqrt(T - 1) / denom)
    return {"sharpe": round(sr, 4), "sr0_expected_max": round(sr0, 4), "n_trials": n_trials,
            "skew": round(sk, 4), "kurtosis": round(ku, 4), "T": T, "dsr": round(dsr, 4),
            "passes_0p95": bool(dsr >= 0.95)}


# ============================ sim-output bridge ==============================
def trades_from_signals(analysis_root: str | Path, days: Sequence[str]) -> list[Trade]:
    """Consume the sim's persisted glass box: fired rows with a realized_r become Trades.
    Works TODAY with realized_r and unchanged when net-of-cost R replaces it. (No exit
    timestamp is persisted; entry ts is used — sim positions are intraday, force-closed
    at session end, so day-level splitting is exact and purge is a no-op in practice.)"""
    import pyarrow.parquet as pq
    root = Path(analysis_root)
    out: list[Trade] = []
    for d in days:
        p = root / d / "signals.parquet"
        if not p.exists():
            continue
        t = pq.read_table(str(p))
        cols = {c: t.column(c).to_pylist() for c in t.column_names}
        for i in range(t.num_rows):
            if cols.get("fired", [False] * t.num_rows)[i] and cols.get("realized_r", [None])[i] is not None:
                ts = int(cols["ts_ns"][i])
                out.append(Trade(d, ts, ts, float(cols["realized_r"][i])))
    return out


# ============================ demo (synthetic evaluator) =====================
def _det_noise(day: str, i: int, salt: int = 0) -> float:
    """Deterministic pseudo-noise in [-1, 1] from (day, i) — stable across runs (no RNG),
    so the demo is reproducible."""
    import hashlib
    h = hashlib.sha1(f"{day}|{i}|{salt}".encode()).hexdigest()
    return (int(h[:8], 16) / 0xFFFFFFFF) * 2 - 1


def synthetic_evaluator(*, center: float = 0.5, edge: float = 0.5, noise: float = 1.0,
                        n_per_day: int = 12, plateau_halfwidth: float = 0.25) -> Evaluator:
    """A KNOWN-answer evaluator for the harness smoke test: expected R has a PLATEAU in the
    knob around ``center`` (inverted-parabola, half-width ``plateau_halfwidth``) plus
    deterministic noise. So the sweep SHOULD find ~center, perturbation SHOULD be stable,
    and the permutation null (which destroys the knob<->R link) SHOULD collapse to ~PF 1."""
    def ev(param: float, days: list[str]) -> list[Trade]:
        out: list[Trade] = []
        for d in days:
            open_ns = _day_open_ns(d)
            dist = abs(param - center) / plateau_halfwidth
            mu = edge * max(0.0, 1 - dist * dist)          # plateau top near center
            for i in range(n_per_day):
                entry = open_ns + i * 300 * NS
                out.append(Trade(d, entry, entry + 120 * NS, mu + noise * _det_noise(d, i)))
        return out
    return ev


def run_demo(days: list[str], *, train_size: int = 2, test_size: int = 1,
             n_perm: int = 200, seed: int = 0) -> dict:
    spec = SweepSpec(knob="demo_threshold",
                     values=(0.0, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9))   # PRE-REGISTERED
    ev = synthetic_evaluator()
    wf_kwargs = dict(scheme="anchored", train_size=train_size, test_size=test_size,
                     embargo_days=0, select_metric=profit_factor)
    wf = walk_forward_sweep(days, ev, spec, **wf_kwargs)
    overall = plateau_report(sweep_curve(spec, lambda v: profit_factor([t.r for t in ev(v, days)])))
    pert = perturbation_check(overall["best_value"],
                              lambda v: profit_factor([t.r for t in ev(v, days)]))
    perm = permutation_null(days, ev, spec, n_perm=n_perm, seed=seed, wf_kwargs=wf_kwargs)
    dsr = deflated_sharpe(wf.oos_r, n_trials=len(spec.values), trial_sharpes=wf.trial_sharpes)
    return {"days": days, "spec": {"knob": spec.knob, "values": list(spec.values)},
            "walk_forward": {"scheme": wf.scheme, "wf_profit_factor": round(wf.wf_profit_factor, 4),
                             "wf_sharpe": round(wf.wf_sharpe, 4), "n_oos_trades": len(wf.oos_r),
                             "per_split": wf.per_split},
            "overall_plateau": overall, "perturbation": pert, "permutation_null": perm,
            "deflated_sharpe": dsr}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="research.walkforward")
    ap.add_argument("--days", default="2026-07-13,2026-07-14,2026-07-15,2026-07-16")
    ap.add_argument("--n-perm", type=int, default=200)
    args = ap.parse_args(argv[1:])
    days = [d for d in args.days.split(",") if d.strip()]
    rep = run_demo(days, n_perm=args.n_perm)

    print("=" * 78)
    print("WALK-FORWARD HARNESS — DEMO (SYNTHETIC evaluator; N={} days is a HARNESS SMOKE "
          "TEST, not a result)".format(len(days)))
    print("=" * 78)
    wf = rep["walk_forward"]
    print(f"pre-registered sweep: {rep['spec']['knob']} over {rep['spec']['values']}")
    print(f"scheme={wf['scheme']}  OOS trades={wf['n_oos_trades']}  "
          f"walk-forward PF={wf['wf_profit_factor']}  Sharpe={wf['wf_sharpe']}")
    for s in wf["per_split"]:
        print(f"  split {s['split']}: train={s['train_days']} test={s['test_days']}  "
              f"chose {s['chosen_value']}  test_PF={s['test_profit_factor']} "
              f"(plateau_width={s['plateau']['plateau_width']}, spike={s['plateau']['is_spike']})")
    ov = rep["overall_plateau"]
    print(f"\nplateau: best={ov['best_value']} metric={round(ov['best_metric'],3)} "
          f"width={ov['plateau_width']} ratio={ov['plateau_ratio']} spike={ov['is_spike']}")
    pt = rep["perturbation"]
    print(f"perturbation(±20%): base={pt['base_metric']} jitter_mean={pt['jitter_mean']} "
          f"sd={pt['jitter_sd']} within_2sd={pt['within_2sd']} fragile={pt['fragile']}")
    pm = rep["permutation_null"]
    print(f"permutation null: real_PF={round(pm['real'],3)}  null_mean={pm['null_mean']} "
          f"p95_floor={pm['null_p95_floor']}  p={pm['p_value']}  beats_floor={pm['beats_floor']} "
          f"(n_perm={pm['n_perm']})")
    ds = rep["deflated_sharpe"]
    print(f"deflated Sharpe: SR={ds['sharpe']}  SR0(expected max over "
          f"{ds['n_trials']} trials)={ds['sr0_expected_max']}  skew={ds['skew']} kurt={ds['kurtosis']}"
          f"  DSR={ds['dsr']}  passes_0.95={ds['passes_0p95']}")
    print("\nN={} is a SMOKE TEST OF THE HARNESS on real day-boundaries with a synthetic "
          "evaluator.\nNOT a strategy result. Real evaluator (pipeline sweep over the 15-day "
          "set) plugs into\nthe same seam; nothing here touches config or wires a component.".format(len(days)))
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
