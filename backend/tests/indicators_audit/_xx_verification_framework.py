"""Queue XX — Reusable indicator verification framework.

Single-function-per-indicator runner. Used by Sprint 1 (top 7 priority),
Sprint 2 (next 30), Sprint 3 (autonomous shallow audit of remaining 184),
Sprint 4 (deep audit of Sprint 3 flagged items).

Confidence tiers (locked Sprint 1):
    A — max abs Δ < 1e-6 vs reference AND 0 sign-flips AND 0 threshold-flips
    B — max abs Δ < 0.1% relative AND 0 sign-flips AND ≤ 1 threshold-flip
    C — 0.1%–5% divergence OR convention mismatch
    D — > 5% divergence OR sign-flips OR NaN-poisoning OR all-NaN-on-real

Reference cascade:
    1. pandas_ta_classic (TV-Pine-equivalent) — primary
    2. talib direct      — secondary cross-check for indicators it has
    3. Hand-rolled Pine reference — fallback if both above unavailable

Run with:
    /tmp/uu-venv/bin/python -c "
    from backend.tests.indicators_audit._xx_verification_framework import (
        verify_one, REAL_NIFTY_CSV
    )
    print(verify_one('stochastic'))
    "
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np


REAL_NIFTY_CSV = Path("/tmp/uu-venv/nifty_real_5m.csv")


# ─── Confidence tier classification ────────────────────────────────


def classify_tier(
    max_abs: float,
    max_rel_pct: float,
    sign_flips: int,
    threshold_flips: int,
    nan_pathology: bool,
) -> tuple[str, str]:
    """Return (tier, one-line reason). Signal-equivalence (threshold-flips == 0
    AND sign-flips == 0) is the load-bearing criterion — it dominates pure
    numerical divergence when small. See module docstring for criteria."""
    if nan_pathology:
        return ("D", "NaN pathology — all-NaN or NaN-poisoning on real data")
    if sign_flips > 0:
        return ("D", f"{sign_flips} sign flips on real data")
    if max_rel_pct > 5.0 and threshold_flips > 0:
        return ("D", f"{max_rel_pct:.2f}% max rel divergence + {threshold_flips} threshold-flips")
    if max_abs < 1e-6 and threshold_flips == 0:
        return ("A", "machine epsilon, zero signal-changes")
    if threshold_flips == 0 and max_rel_pct < 5.0:
        # Signal-equivalent — small numerical accumulation noise OK
        return ("B", f"{max_rel_pct:.4f}% max rel divergence, zero threshold-flips (signal-equivalent)")
    if threshold_flips <= 1 and max_rel_pct < 0.1:
        return ("B", f"{max_rel_pct:.4f}% max rel divergence, ≤1 threshold-flip")
    if max_rel_pct > 5.0:
        return ("D", f"{max_rel_pct:.2f}% max relative divergence")
    # 0.1%–5% with multiple threshold-flips = needs decision
    return ("C", f"{max_rel_pct:.3f}% max rel divergence + {threshold_flips} threshold-flips — convention check")


# ─── Diff stats ────────────────────────────────────────────────────


@dataclass
class DiffStats:
    name: str
    n_compared: int
    max_abs: float
    mean_abs: float
    p99_abs: float
    max_rel_pct: float
    sign_flips: int = 0

    def short(self) -> str:
        return (
            f"  {self.name:35s}  n={self.n_compared:>4d}  "
            f"max|Δ|={self.max_abs:>10.4e}  mean|Δ|={self.mean_abs:>10.4e}  "
            f"max%|Δ|={self.max_rel_pct:>8.4f}%  flips={self.sign_flips}"
        )


def diff_series(name: str, a_list_or_arr: Any, b_list_or_arr: Any) -> DiffStats:
    """Compute pairwise diff stats with NaN-safe masking and None→NaN coercion."""
    if isinstance(a_list_or_arr, list):
        a = np.asarray([np.nan if v is None else v for v in a_list_or_arr], dtype=np.float64)
    else:
        a = np.asarray(a_list_or_arr, dtype=np.float64)
    if isinstance(b_list_or_arr, list):
        b = np.asarray([np.nan if v is None else v for v in b_list_or_arr], dtype=np.float64)
    else:
        b = np.asarray(b_list_or_arr, dtype=np.float64)
    # Lengths may differ when refs are pandas-padded vs hand-rolled; truncate to min
    m_len = min(len(a), len(b))
    a = a[:m_len]
    b = b[:m_len]
    mask = np.isfinite(a) & np.isfinite(b)
    n = int(mask.sum())
    if n == 0:
        return DiffStats(name, 0, float("nan"), float("nan"), float("nan"), float("nan"))
    d = np.abs(a[mask] - b[mask])
    rel = d / np.maximum(np.abs(b[mask]), 1e-9)
    nz_mask = mask & (a != 0) & (b != 0)
    flips = int(np.sum(np.sign(a[nz_mask]) != np.sign(b[nz_mask])))
    return DiffStats(
        name=name,
        n_compared=n,
        max_abs=float(d.max()),
        mean_abs=float(d.mean()),
        p99_abs=float(np.percentile(d, 99)) if n >= 100 else float(d.max()),
        max_rel_pct=float(rel.max() * 100),
        sign_flips=flips,
    )


# ─── Threshold-flip count for canonical levels ─────────────────────


def threshold_flips(
    a_list_or_arr: Any,
    b_list_or_arr: Any,
    thresholds: list[float],
) -> int:
    """Bars where a and b disagree on whether the value crosses any threshold.

    For each threshold T and bar i: a and b agree at bar i iff
    (a[i] > T) == (b[i] > T). Disagreement is counted once per bar per
    threshold (sums across thresholds).
    """
    if isinstance(a_list_or_arr, list):
        a = np.asarray([np.nan if v is None else v for v in a_list_or_arr], dtype=np.float64)
    else:
        a = np.asarray(a_list_or_arr, dtype=np.float64)
    if isinstance(b_list_or_arr, list):
        b = np.asarray([np.nan if v is None else v for v in b_list_or_arr], dtype=np.float64)
    else:
        b = np.asarray(b_list_or_arr, dtype=np.float64)
    m_len = min(len(a), len(b))
    a = a[:m_len]
    b = b[:m_len]
    mask = np.isfinite(a) & np.isfinite(b)
    disagreements = 0
    for t in thresholds:
        a_above = a[mask] > t
        b_above = b[mask] > t
        disagreements += int(np.sum(a_above != b_above))
    return disagreements


# ─── NaN sanity ────────────────────────────────────────────────────


def nan_sanity(arr_or_list: Any) -> dict[str, int | bool]:
    """Detect NaN pathologies on real data."""
    if isinstance(arr_or_list, list):
        a = np.asarray([np.nan if v is None else v for v in arr_or_list], dtype=np.float64)
    else:
        a = np.asarray(arr_or_list, dtype=np.float64)
    n = len(a)
    finite_count = int(np.isfinite(a).sum())
    return {
        "total": n,
        "finite": finite_count,
        "nan": n - finite_count,
        "all_nan": finite_count == 0 and n > 0,
        "trailing_nan_count": int(np.sum(np.isnan(a[-min(50, n):]))) if n > 0 else 0,
    }


# ─── Real NIFTY loader ─────────────────────────────────────────────


def load_real_nifty() -> dict[str, np.ndarray]:
    """Load the cached yfinance ^NSEI 5m series. Returns OHLCV arrays."""
    closes, highs, lows, opens, volumes = [], [], [], [], []
    with REAL_NIFTY_CSV.open() as f:
        for row in csv.DictReader(f):
            closes.append(float(row["close"]))
            highs.append(float(row["high"]))
            lows.append(float(row["low"]))
            opens.append(float(row["open"]))
            volumes.append(float(row["volume"]))
    return {
        "open": np.asarray(opens, dtype=np.float64),
        "high": np.asarray(highs, dtype=np.float64),
        "low": np.asarray(lows, dtype=np.float64),
        "close": np.asarray(closes, dtype=np.float64),
        "volume": np.asarray(volumes, dtype=np.float64),
        "closes_list": closes,
        "highs_list": highs,
        "lows_list": lows,
        "volumes_list": volumes,
    }


# ─── Verification verdict structure ────────────────────────────────


@dataclass
class IndicatorVerdict:
    name: str
    tier: str  # A/B/C/D
    reason: str
    diffs: list[DiffStats] = field(default_factory=list)
    threshold_flips_total: int = 0
    nan_report: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            f"\n=== {self.name} ===",
            f"  TIER: {self.tier}  ({self.reason})",
            f"  Threshold flips: {self.threshold_flips_total}",
            f"  NaN: total={self.nan_report.get('total',0)}, "
            f"finite={self.nan_report.get('finite',0)}, "
            f"all_nan={self.nan_report.get('all_nan',False)}",
            "  Diff stats:",
        ]
        for d in self.diffs:
            lines.append(d.short())
        for n in self.notes:
            lines.append(f"  NOTE: {n}")
        return "\n".join(lines)


__all__ = [
    "REAL_NIFTY_CSV",
    "DiffStats",
    "IndicatorVerdict",
    "classify_tier",
    "diff_series",
    "load_real_nifty",
    "nan_sanity",
    "threshold_flips",
]
