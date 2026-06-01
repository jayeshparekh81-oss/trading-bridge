"""Queue ZZ Sprint 7b — indicator-dependency audit.

For each of the 113 templates in strategy_templates_seed.json, extract the
``indicators`` list from ``config_json`` and resolve every reference against
the Sprint 6e dual-scoreboard (92 verified A/B + 4 D-tier). Categorize each
template by the worst case among its references.

Resolution kinds (per indicator reference):
    direct  — name appears verbatim in dual_scoreboard.csv
    base    — name resolves after stripping trailing param tokens
              (``ema_50`` → ``ema``;  ``macd_12_26_9`` is itself a direct match)
    alias   — name resolves via an explicit shorthand map
              (``bb_20_2`` → ``bollinger_bands``;  ``orb_15`` → ``opening_range_breakout``)
    unknown — no resolution; the indicator is not in the verified set

Template buckets (priority order — first match wins):
    HAS_UNKNOWN          — any reference is unknown
    HAS_D_TIER           — any reference resolves to a D-tier indicator
    PARTIAL_VERIFIED     — mix of direct + (base|alias)
    INDIRECT_DEPENDENCY  — all references are (base|alias), zero direct
                           (founder direction 2026-06-01: distinct from HAS_UNKNOWN)
    ALL_VERIFIED         — every reference is a direct match, all A/B
    MISSING_INDICATOR    — ``indicators`` list is empty / absent on a populated config
    PHASE_2_PLACEHOLDER  — ``config_json == {}`` (excluded from failure totals)

Output: backend/tests/queue_zz_sprint_7/dependency_audit.csv (113 rows × 8 cols).
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

_REPO_ROOT = _BACKEND_ROOT.parent
_SEED_PATH = _BACKEND_ROOT / "data" / "strategy_templates_seed.json"
_SCOREBOARD = _BACKEND_ROOT / "tests" / "queue_xx_sprint_3" / "dual_scoreboard.csv"
_OUT_CSV = _BACKEND_ROOT / "tests" / "queue_zz_sprint_7" / "dependency_audit.csv"

# Shorthand template name → canonical scoreboard name. Each entry is a
# semantically lossless alias — same indicator, different naming convention.
# Anything not on this list and not a direct/base hit is UNKNOWN.
_ALIAS: dict[str, str] = {
    "bb": "bollinger_bands",
    "orb": "opening_range_breakout",
    "chandelier": "chandelier_exit_long",
    "bollinger_pct_b": "bollinger_percent_b",
    "stochastic_slow": "stochastic",
}


def _load_scoreboard() -> dict[str, str]:
    """Return {indicator_name: tier_pine}."""
    out: dict[str, str] = {}
    with _SCOREBOARD.open() as fh:
        for row in csv.DictReader(fh):
            out[row["indicator"]] = row["tier_pine"]
    return out


def _resolve(name: str, scoreboard: dict[str, str]) -> tuple[str, str | None, str | None]:
    """Return (kind, canonical_name, tier). kind ∈ {direct, base, alias, unknown}."""
    if name in scoreboard:
        return "direct", name, scoreboard[name]

    parts = name.split("_")
    # Iterative prefix-strip — drop trailing tokens until we hit a known name.
    # `keltner_channel_20_1.5_atr14` → keltner_channel; `parabolic_sar_0.02_0.2`
    # → parabolic_sar (not in scoreboard → keeps stripping until empty → unknown).
    while len(parts) > 1:
        parts.pop()
        candidate = "_".join(parts)
        if candidate in scoreboard:
            return "base", candidate, scoreboard[candidate]
        if candidate in _ALIAS:
            canon = _ALIAS[candidate]
            if canon in scoreboard:
                return "alias", canon, scoreboard[canon]

    return "unknown", None, None


def _tier_is_verified(tier: str) -> bool:
    return tier in {"A", "B", "A_with_warmup_note"}


def _tier_is_d(tier: str) -> bool:
    return tier.startswith("D")


def _bucket(resolutions: list[dict]) -> str:
    if not resolutions:
        return "MISSING_INDICATOR"

    has_unknown = any(r["kind"] == "unknown" for r in resolutions)
    has_d = any(r["tier"] and _tier_is_d(r["tier"]) for r in resolutions)
    has_direct = any(r["kind"] == "direct" for r in resolutions)
    has_indirect = any(r["kind"] in {"base", "alias"} for r in resolutions)

    if has_unknown:
        return "HAS_UNKNOWN"
    if has_d:
        return "HAS_D_TIER"
    if has_direct and has_indirect:
        return "PARTIAL_VERIFIED"
    if has_indirect and not has_direct:
        return "INDIRECT_DEPENDENCY"
    return "ALL_VERIFIED"


def run() -> dict:
    scoreboard = _load_scoreboard()
    with _SEED_PATH.open() as fh:
        seed = json.load(fh)
    templates = seed["templates"]

    rows: list[dict] = []
    buckets: Counter[str] = Counter()
    indicator_resolution_counter: Counter[tuple[str, str]] = Counter()

    for i, t in enumerate(templates):
        cfg = t.get("config_json", {})
        slug = t.get("slug", "")
        name_field = t.get("name", "")
        is_active = bool(t.get("is_active", False))

        if not isinstance(cfg, dict) or cfg == {}:
            status = "PHASE_2_PLACEHOLDER"
            inds: list[str] = []
            resolutions: list[dict] = []
            resolution_summary = "—"
            flagged = "—"
        else:
            inds = cfg.get("indicators", []) or []
            if not isinstance(inds, list):
                inds = []

            resolutions = []
            for ind in inds:
                if not isinstance(ind, str):
                    resolutions.append({"name": str(ind), "kind": "unknown", "canonical": None, "tier": None})
                    continue
                kind, canonical, tier = _resolve(ind, scoreboard)
                resolutions.append({"name": ind, "kind": kind, "canonical": canonical, "tier": tier})
                indicator_resolution_counter[(ind, kind)] += 1

            status = _bucket(resolutions)

            kind_counts = Counter(r["kind"] for r in resolutions)
            tier_counts = Counter(r["tier"] for r in resolutions if r["tier"])
            resolution_summary = (
                f"direct={kind_counts.get('direct', 0)} "
                f"base={kind_counts.get('base', 0)} "
                f"alias={kind_counts.get('alias', 0)} "
                f"unknown={kind_counts.get('unknown', 0)} "
                f"| tiers={dict(tier_counts)}"
            )

            flagged_parts = []
            for r in resolutions:
                if r["kind"] == "unknown":
                    flagged_parts.append(f"{r['name']}[UNKNOWN]")
                elif r["tier"] and _tier_is_d(r["tier"]):
                    flagged_parts.append(f"{r['name']}→{r['canonical']}[D]")
                elif r["kind"] in {"base", "alias"}:
                    flagged_parts.append(f"{r['name']}→{r['canonical']}[{r['kind']}]")
            flagged = "; ".join(flagged_parts) if flagged_parts else "—"

        buckets[status] += 1
        rows.append(
            {
                "index": i,
                "slug": slug,
                "name": name_field,
                "is_active": is_active,
                "status": status,
                "indicators": "; ".join(inds) if inds else "—",
                "resolution_summary": resolution_summary,
                "flagged_indicators": flagged,
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
                "is_active",
                "status",
                "indicators",
                "resolution_summary",
                "flagged_indicators",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    populated_total = sum(1 for r in rows if r["status"] != "PHASE_2_PLACEHOLDER")
    failures = sum(
        1 for r in rows if r["status"] in {"HAS_UNKNOWN", "HAS_D_TIER", "MISSING_INDICATOR"}
    )

    # Roll-up of distinct unknown indicators (for the report).
    unknowns = sorted({n for (n, k) in indicator_resolution_counter if k == "unknown"})
    indirects = sorted({n for (n, k) in indicator_resolution_counter if k in {"base", "alias"}})

    return {
        "total": len(rows),
        "buckets": dict(buckets),
        "populated_total": populated_total,
        "failures_excl_placeholders": failures,
        "failure_rate_excl_placeholders": (
            round(100.0 * failures / populated_total, 1) if populated_total else 0.0
        ),
        "active_total": sum(1 for r in rows if r["is_active"]),
        "active_all_verified": sum(
            1 for r in rows if r["is_active"] and r["status"] == "ALL_VERIFIED"
        ),
        "active_with_unknown": sum(
            1 for r in rows if r["is_active"] and r["status"] == "HAS_UNKNOWN"
        ),
        "active_with_d_tier": sum(
            1 for r in rows if r["is_active"] and r["status"] == "HAS_D_TIER"
        ),
        "distinct_unknown_indicators": unknowns,
        "distinct_indirect_indicators": indirects,
        "output_csv": str(_OUT_CSV.relative_to(_REPO_ROOT)),
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
