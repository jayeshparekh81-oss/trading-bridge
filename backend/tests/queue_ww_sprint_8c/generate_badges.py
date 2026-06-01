"""Regenerate ``docs/indicator_library_badges.json`` from the Sprint 6e
dual-scoreboard CSV.

The badge JSON is what the frontend consumes (see
``docs/INDICATOR_LIBRARY_VERIFICATION_SPEC.md`` §5). Run this whenever
the dual-scoreboard CSV is updated to keep the spec artifact in sync.

Run:
    cd backend && python3 -m tests.queue_ww_sprint_8c.generate_badges
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CSV = _REPO_ROOT / "backend" / "tests" / "queue_xx_sprint_3" / "dual_scoreboard.csv"
_OUT = _REPO_ROOT / "docs" / "indicator_library_badges.json"


def _badge(pine: str, talib: str) -> tuple[str, str]:
    p, t = pine.strip(), talib.strip()
    if p == "A" and t == "A":
        return ("Verified", "Tier-A match across Pine + talib references")
    if p == "A" and t == "A_with_warmup_note":
        return ("Verified*", "Tier-A; minor warmup-bar drift documented")
    if p == "A" and t == "(no talib)":
        return ("Verified", "Tier-A vs Pine; no talib counterpart for this indicator")
    if p == "A" and t == "D_convention":
        return ("Convention varies", "Tier-A under one convention, divergent under the other")
    if p == "B" and t == "B":
        return ("Best-effort", "Tier-B match — small numeric drift within tolerance")
    if p == "B" and t == "(no talib)":
        return ("Best-effort", "Tier-B vs Pine; no talib counterpart")
    if p == "D" and t == "(no talib)":
        return ("Under review", "Tier-D — verification gap, not yet promoted")
    if p == "D" and t == "D":
        return ("Under review", "Tier-D under both conventions")
    return ("Unclassified", f"(pine={p}, talib={t})")


def main() -> int:
    with open(_CSV) as f:
        rows = list(csv.DictReader(f))

    entries = []
    for r in rows:
        pine = r["tier_pine"].strip()
        talib = r["tier_talib"].strip()
        badge_label, badge_help = _badge(pine, talib)
        entries.append({
            "indicator": r["indicator"].strip(),
            "tier_pine": pine,
            "tier_talib": talib,
            "divergence_note": r["divergence_note"].strip(),
            "badge": badge_label,
            "badge_help": badge_help,
        })

    payload = {
        "generated_from": str(_CSV.relative_to(_REPO_ROOT)),
        "row_count": len(entries),
        "entries": entries,
    }
    _OUT.write_text(json.dumps(payload, indent=2))
    print(f"wrote {_OUT.relative_to(_REPO_ROOT)} ({len(entries)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
