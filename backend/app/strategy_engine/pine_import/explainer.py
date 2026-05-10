"""Human-readable explanation of an import.

Reads the parsed program plus the converter's notes and emits a
short summary the UI can show alongside the imported strategy.
"""

from __future__ import annotations

from app.strategy_engine.pine_import.parser import PineProgram
from app.strategy_engine.pine_import.validator import (
    LicenseStatus,
    ValidationReport,
)


def explain(
    program: PineProgram,
    report: ValidationReport,
    notes: list[str],
) -> str:
    """Return a 1-3 sentence summary plus a bullet of the discovered shape."""
    lines: list[str] = []

    indicator_words = ", ".join(
        f"{call.var_name} ({call.func})" for call in program.indicators
    ) or "no indicators"
    cross_words = ", ".join(
        f"{c.kind.value}({c.left}, {c.right})" for c in program.crosses
    ) or "no cross conditions"

    lines.append(
        f"Imported {len(program.indicators)} indicator(s): {indicator_words}."
    )
    lines.append(f"Cross conditions: {cross_words}.")

    if report.license_status is LicenseStatus.PERMISSIVE:
        lines.append(
            f"License: {report.license_match} (permissive — safe to use)."
        )
    elif report.license_status is LicenseStatus.COMPLIANCE_REQUIRED:
        lines.append(
            f"License: {report.license_match} — review the license terms "
            "before deploying."
        )
    elif report.license_status is LicenseStatus.NEEDS_REVIEW:
        lines.append(
            "License: not detected — confirm you have rights to import."
        )
    elif report.license_status is LicenseStatus.BLOCKED:
        lines.append(
            f"License: {report.license_match} — script blocked from import."
        )

    if notes:
        lines.append("Notes:")
        lines.extend(f"  - {note}" for note in notes)

    return "\n".join(lines)


__all__ = ["explain"]
