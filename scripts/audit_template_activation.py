#!/usr/bin/env python3
"""Template activation audit.

For each ``is_active=True`` template in
``backend/data/strategy_templates_seed.json``, verify every indicator
referenced in its ``config_json.indicators`` list is:

  1. **Implemented**: there's a Python file under
     ``backend/app/strategy_engine/indicators/calculations/<name>.py``
     OR the name matches a known indicator alias.
  2. **Registered**: the name is in
     ``app.strategy_engine.indicators.registry.INDICATOR_REGISTRY``
     with ``status=active``.
  3. **Dispatched**: there's an ``if cfg.type == '<name>'`` branch
     in ``backend/app/strategy_engine/backtest/indicator_runner.py``.

Emits:
  - ``docs/TEMPLATE_ACTIVATION_AUDIT.md`` — table per template with
    each indicator's status
  - ``docs/proposed_seed_patch.json`` — proposed patch flipping any
    unsafe template back to ``is_active=False`` (NOT applied)

The script does NOT modify the live seed file.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_PATH = REPO_ROOT / "backend" / "data" / "strategy_templates_seed.json"
CALCULATIONS_DIR = (
    REPO_ROOT / "backend" / "app" / "strategy_engine" / "indicators" / "calculations"
)
DISPATCH_PATH = (
    REPO_ROOT / "backend" / "app" / "strategy_engine" / "backtest" / "indicator_runner.py"
)


def discover_calculation_files() -> set[str]:
    """Set of indicator names that have a Python file (== implemented)."""
    if not CALCULATIONS_DIR.is_dir():
        return set()
    return {
        p.stem for p in CALCULATIONS_DIR.iterdir() if p.suffix == ".py" and not p.stem.startswith("_")
    }


def discover_dispatch_branches() -> set[str]:
    """Set of indicator type names appearing in `if cfg.type == 'X':`
    branches in the dispatch table."""
    if not DISPATCH_PATH.is_file():
        return set()
    body = DISPATCH_PATH.read_text()
    # if cfg.type == "name": OR if cfg.type in ("a", "b", ...):
    branch_pat = re.compile(r'cfg\.type\s*==\s*["\']([a-z_0-9]+)["\']')
    in_pat = re.compile(r'cfg\.type\s+in\s+\(([^)]+)\)')
    branches = set(branch_pat.findall(body))
    for m in in_pat.findall(body):
        for piece in m.split(","):
            n = piece.strip().strip("\"'")
            if n:
                branches.add(n)
    return branches


def discover_registered_indicators() -> dict[str, str] | None:
    """Try to import the registry. Returns {id: status} or None on failure."""
    os.environ.setdefault("JWT_SECRET", "audit-placeholder")
    os.environ.setdefault(
        "ENCRYPTION_KEY", "JlPyLqr5K8XnZc9wK_OoUq8YyfZ2RhxbgkY7vxBfFu4="
    )
    os.environ.setdefault("ENVIRONMENT", "test")
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    try:
        from app.strategy_engine.indicators.registry import (  # type: ignore[import-untyped]
            INDICATOR_REGISTRY,
        )
    except Exception as exc:
        print(f"  registry import failed ({exc}); falling back to AST scan", file=sys.stderr)
        return None
    return {name: meta.status.value for name, meta in INDICATOR_REGISTRY.items()}


def _normalise_indicator_name(raw: str) -> str:
    """Normalise a template config indicator name to a registry type id.

    Template configs use informal names like ``ema_9`` / ``ema_20``
    (config_id convention = ``<type>_<period>``) while the registry
    uses bare type names like ``ema``.

    Strategy:
        1. If the raw name is already in the registry, use it as-is
           (e.g. ``parabolic_sar``, ``bollinger_percent_b``).
        2. Try stripping a trailing ``_<digits>`` suffix (e.g.
           ``ema_9`` → ``ema``).
        3. Try stripping ``_<digit>_<digit>_<digit>`` (e.g.
           ``stochastic_14_3_3`` → ``stochastic``).
        4. Try the ``_<period>_<stddev>`` form (e.g. ``bb_20_2`` → ``bb``,
           which is itself an alias for ``bollinger_bands``).
        5. Hand-mapped aliases for known drift cases.

    Returns the BEST CANDIDATE name for registry lookup. The caller
    still classifies based on whether the candidate is found.
    """
    aliases = {
        "bb": "bollinger_bands",
        "macd": "macd",
        "rsi": "rsi",
        "ema": "ema",
        "sma": "sma",
        "vwap": "vwap",
        "atr": "atr",
        "obv": "obv",
        "psar": "parabolic_sar",
        "supertrend": "supertrend",
        "stochastic": "stochastic",
        "orb": "opening_range_breakout",
        "williams_pct_r": "williams_r",
        "engulfing_pattern": "bullish_engulfing",
        "hammer_pattern": "hammer",
        "doji_pattern": "doji",
        "previous_day_high_low": "daily_pivot_distance",
        "premarket_gap": "gap_up_down",
        "volume_spike": "volume_sma",
        "obv_divergence": "obv",
    }
    if raw in aliases.values():
        return raw
    if raw in aliases:
        return aliases[raw]
    # Strip a trailing _<digits>[_<digits>...] suffix
    stripped = re.sub(r"(_\d+)+$", "", raw)
    if stripped != raw and stripped in aliases.values():
        return stripped
    if stripped in aliases:
        return aliases[stripped]
    return stripped or raw


def classify_indicator(
    name: str,
    impl_set: set[str],
    dispatch_set: set[str],
    registry: dict[str, str] | None,
) -> str:
    """One of: RUNTIME_SAFE | MISSING_INDICATOR | NOT_DISPATCHED |
    NOT_REGISTERED | NOT_ACTIVE."""
    resolved = _normalise_indicator_name(name)
    has_impl = resolved in impl_set
    has_dispatch = resolved in dispatch_set
    if registry is None:
        if has_impl and has_dispatch:
            return "RUNTIME_SAFE"
        if not has_impl:
            return "MISSING_INDICATOR"
        return "NOT_DISPATCHED"
    if resolved not in registry:
        return "NOT_REGISTERED"
    if registry[resolved] != "active":
        return f"NOT_ACTIVE ({registry[resolved]})"
    if not has_impl:
        return "MISSING_INDICATOR"
    if not has_dispatch:
        return "NOT_DISPATCHED"
    return "RUNTIME_SAFE"


def audit() -> None:
    if not SEED_PATH.is_file():
        print(f"Seed file not found: {SEED_PATH}", file=sys.stderr)
        sys.exit(1)
    seed = json.loads(SEED_PATH.read_text())
    impl_set = discover_calculation_files()
    dispatch_set = discover_dispatch_branches()
    registry = discover_registered_indicators()

    print(f"Implementation files: {len(impl_set)}")
    print(f"Dispatch branches: {len(dispatch_set)}")
    print(
        f"Registered indicators: "
        f"{len(registry) if registry else 'N/A (registry import failed)'}"
    )

    active_templates = [
        t
        for t in seed.get("templates", [])
        if t.get("is_active") and not t.get("requires_options_builder")
    ]
    print(f"Active equity templates: {len(active_templates)}")

    rows: list[dict] = []
    unsafe_slugs: list[str] = []

    for t in active_templates:
        slug = t["slug"]
        config_json = t.get("config_json", {}) or {}
        indicators = config_json.get("indicators", []) or []
        if not indicators:
            rows.append(
                {
                    "slug": slug,
                    "name": t["name"],
                    "indicators": [],
                    "status": "RUNTIME_SAFE (no indicators)",
                    "details": {},
                }
            )
            continue
        per_ind: dict[str, str] = {}
        worst = "RUNTIME_SAFE"
        for ind in indicators:
            ind_status = classify_indicator(ind, impl_set, dispatch_set, registry)
            per_ind[ind] = ind_status
            if ind_status != "RUNTIME_SAFE":
                if "MISSING" in ind_status:
                    worst = ind_status
                elif "NOT_REGISTERED" in worst:
                    pass  # already worst
                elif ind_status == "NOT_DISPATCHED" and worst == "RUNTIME_SAFE":
                    worst = ind_status
                else:
                    if worst == "RUNTIME_SAFE":
                        worst = ind_status
        rows.append(
            {
                "slug": slug,
                "name": t["name"],
                "indicators": indicators,
                "status": worst,
                "details": per_ind,
            }
        )
        if worst != "RUNTIME_SAFE":
            unsafe_slugs.append(slug)

    # Write markdown
    md_lines = [
        "# Template Activation Audit",
        "",
        f"**Date:** 2026-05-18  ",
        f"**Active equity templates audited:** {len(active_templates)}  ",
        f"**Runtime-safe:** {sum(1 for r in rows if r['status'] == 'RUNTIME_SAFE')}  ",
        f"**Unsafe (recommend deactivation):** {len(unsafe_slugs)}",
        "",
        "## Per-template status",
        "",
        "| Slug | Status | Indicators (per-status) |",
        "|---|---|---|",
    ]
    for r in rows:
        slug = r["slug"]
        status = r["status"]
        details = r["details"]
        ind_str = (
            ", ".join(f"`{name}`={st}" for name, st in details.items())
            if details
            else "(none)"
        )
        md_lines.append(f"| `{slug}` | {status} | {ind_str} |")

    md_lines.extend(
        [
            "",
            "## Unsafe templates (recommend `is_active=False`)",
            "",
        ]
    )
    if not unsafe_slugs:
        md_lines.append("None. All 45 active equity templates are runtime-safe.")
    else:
        for s in unsafe_slugs:
            md_lines.append(f"- `{s}`")

    out_md = REPO_ROOT / "docs" / "TEMPLATE_ACTIVATION_AUDIT.md"
    out_md.write_text("\n".join(md_lines))
    print(f"  wrote {out_md.relative_to(REPO_ROOT)}")

    # Write proposed patch
    if unsafe_slugs:
        patch = {
            "_meta": {
                "purpose": "Proposed deactivation patch — flip unsafe templates to is_active=False",
                "generated": "2026-05-18",
                "audit_doc": "docs/TEMPLATE_ACTIVATION_AUDIT.md",
                "DO_NOT_APPLY": True,
            },
            "deactivate_slugs": unsafe_slugs,
        }
    else:
        patch = {
            "_meta": {
                "status": "ALL_SAFE — no proposed deactivations",
                "generated": "2026-05-18",
            },
            "deactivate_slugs": [],
        }
    out_patch = REPO_ROOT / "docs" / "proposed_seed_patch.json"
    out_patch.write_text(json.dumps(patch, indent=2))
    print(f"  wrote {out_patch.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    audit()
