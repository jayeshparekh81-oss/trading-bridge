"""Queue ZZ Sprint 7d — performance-sanity audit.

For the 20 active templates that produced trade flow in 7c (FIRES_CLEAN +
FIRES_WITH_WARNINGS), re-run the deterministic backtest and capture the
full ``BacktestResult`` metric suite (which 7c's CSV elided). Apply a
small set of suspicious-pattern flags. We are NOT scoring profitability
on synthetic data — the goal is to surface metrics that look
mathematically degenerate, not metrics that look unprofitable.

Sanity flags (per founder direction):
    WIN_RATE_OUT_OF_BAND        — win_rate outside [0, 1] (Pydantic forbids
                                  this so the flag is double-belt; included for
                                  audit completeness)
    PROFIT_FACTOR_NON_FINITE    — profit_factor is inf, -inf, or NaN
    SUSPICIOUS_PERFECT_WIN      — win_rate == 1.0 AND total_trades > 5
    SUSPICIOUS_ZERO_DRAWDOWN    — max_drawdown == 0 AND total_trades > 100
    SUSPICIOUS_INF_PROFIT_FACTOR — profit_factor is +inf (no losing trades
                                  on a small population — rare degenerate)
    MDD_EXCESSIVE               — max_drawdown > 10% of initial_capital
                                  (>10,000 on the 100,000 default)
    PASS_SANITY                 — no flags raised

Output: backend/tests/queue_zz_sprint_7/performance_sanity.csv
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

os.environ.setdefault("ENCRYPTION_KEY", "TZNZeqzMl_RWXVukYW1Cl9JLn2hHIxOmQYx3FW6S_uA=")
os.environ.setdefault("JWT_SECRET", "x" * 32)
os.environ.setdefault("ENVIRONMENT", "test")

from app.strategy_engine.api.backtest import _synthetic_candles  # noqa: E402
from app.strategy_engine.backtest.runner import (  # noqa: E402
    BacktestInput,
    BacktestResult,
    run_backtest,
)
from app.strategy_engine.translator.errors import TranslationError  # noqa: E402
from app.strategy_engine.translator.parser import translate_template  # noqa: E402

_REPO_ROOT = _BACKEND_ROOT.parent
_SEED_PATH = _BACKEND_ROOT / "data" / "strategy_templates_seed.json"
_PRIOR_CSV = _BACKEND_ROOT / "tests" / "queue_zz_sprint_7" / "backtest_execution.csv"
_OUT_CSV = _BACKEND_ROOT / "tests" / "queue_zz_sprint_7" / "performance_sanity.csv"

_SYNTH_BARS = 720
_DEFAULT_CAPITAL = 100_000.0
_MDD_EXCESSIVE_FRACTION = 0.10  # 10% of initial capital


def _load_targets() -> list[int]:
    """Return the indices of the 20 templates that fired in 7c."""
    out: list[int] = []
    with _PRIOR_CSV.open() as fh:
        for row in csv.DictReader(fh):
            if row["is_active"] == "True" and row["status"] in {
                "FIRES_CLEAN",
                "FIRES_WITH_WARNINGS",
            }:
                out.append(int(row["index"]))
    return out


def _apply_flags(result: BacktestResult) -> list[str]:
    flags: list[str] = []
    if not (0.0 <= result.win_rate <= 1.0):
        flags.append("WIN_RATE_OUT_OF_BAND")

    pf = result.profit_factor
    if math.isnan(pf) or math.isinf(pf):
        # +inf is the well-defined "no losses" case; -inf shouldn't occur.
        if math.isinf(pf) and pf > 0:
            flags.append("SUSPICIOUS_INF_PROFIT_FACTOR")
        else:
            flags.append("PROFIT_FACTOR_NON_FINITE")

    if result.win_rate == 1.0 and result.total_trades > 5:
        flags.append("SUSPICIOUS_PERFECT_WIN")

    if result.max_drawdown == 0.0 and result.total_trades > 100:
        flags.append("SUSPICIOUS_ZERO_DRAWDOWN")

    if result.max_drawdown > _DEFAULT_CAPITAL * _MDD_EXCESSIVE_FRACTION:
        flags.append("MDD_EXCESSIVE")

    return flags or ["PASS_SANITY"]


def run() -> dict:
    targets = _load_targets()
    with _SEED_PATH.open() as fh:
        seed = json.load(fh)
    templates = seed["templates"]

    candles = _synthetic_candles(_SYNTH_BARS)

    rows: list[dict] = []
    flag_tallies: dict[str, int] = {}

    for i in targets:
        t = templates[i]
        slug = t.get("slug", "")
        name = t.get("name", "")
        try:
            strategy_json = translate_template(t)
            payload = BacktestInput(candles=candles, strategy=strategy_json)
            result = run_backtest(payload)
        except TranslationError as exc:
            # Should not happen — 7c already proved these translate. Capture
            # defensively so the row count stays at 20.
            rows.append(
                {
                    "index": i,
                    "slug": slug,
                    "name": name,
                    "trades": "",
                    "win_rate": "",
                    "profit_factor": "",
                    "max_drawdown": "",
                    "expectancy": "",
                    "total_pnl": "",
                    "flags": f"REGRESSION_TRANSLATION_FAILED: {exc}",
                }
            )
            flag_tallies["REGRESSION_TRANSLATION_FAILED"] = (
                flag_tallies.get("REGRESSION_TRANSLATION_FAILED", 0) + 1
            )
            continue

        flags = _apply_flags(result)
        for f in flags:
            flag_tallies[f] = flag_tallies.get(f, 0) + 1

        rows.append(
            {
                "index": i,
                "slug": slug,
                "name": name,
                "trades": result.total_trades,
                "win_rate": round(result.win_rate, 4),
                "profit_factor": (
                    "inf" if math.isinf(result.profit_factor) else round(result.profit_factor, 4)
                ),
                "max_drawdown": round(result.max_drawdown, 2),
                "expectancy": round(result.expectancy, 2),
                "total_pnl": round(result.total_pnl, 2),
                "flags": "; ".join(flags),
            }
        )

    _OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with _OUT_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "index",
                "slug",
                "name",
                "trades",
                "win_rate",
                "profit_factor",
                "max_drawdown",
                "expectancy",
                "total_pnl",
                "flags",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    return {
        "targets_total": len(targets),
        "rows_written": len(rows),
        "flag_tallies": flag_tallies,
        "pass_sanity_count": flag_tallies.get("PASS_SANITY", 0),
        "flagged_count": sum(v for k, v in flag_tallies.items() if k != "PASS_SANITY"),
        "output_csv": str(_OUT_CSV.relative_to(_REPO_ROOT)),
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
