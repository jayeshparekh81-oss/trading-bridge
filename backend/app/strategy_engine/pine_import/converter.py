"""Top-level Pine importer entrypoint.

Pipeline::

    source string
        ↓ validate_source — license + safety
        ↓ parse_source    — regex extract supported subset
        ↓ map_program     — build StrategyJSON-shaped dict
        ↓ StrategyJSON.model_validate — schema check
        → ConversionResult

The pipeline is **purely textual / structural** — no eval, no exec, no
compile. ``test_no_dynamic_code_execution`` AST-inspects this package
to make that property load-bearing.

Output contract (matches the Phase 7 master prompt):

    success → ``{"success": True, "strategy": ..., "explanation": ..., ...}``
    failure → ``{"success": False, "partial": ..., "converted": ...,
                 "unsupported": [...], "message": ...}``

Both shapes carry a ``license_status`` so the UI can show a permissive
green-tick or surface a "needs review" warning.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.strategy_engine.pine_import.explainer import explain
from app.strategy_engine.pine_import.mapper import map_program
from app.strategy_engine.pine_import.parser import parse_source
from app.strategy_engine.pine_import.validator import (
    validate_source,
)
from app.strategy_engine.schema.strategy import StrategyJSON


def convert_pine_to_strategy(source: str) -> dict[str, Any]:
    """Convert ``source`` (Pine v5/v6 text) into a Tradetri strategy.

    Returns one of two dict shapes:

        success:
            ``{"success": True, "strategy": {...}, "explanation": str,
            "license_status": str, "notes": [...]}``

        failure / partial:
            ``{"success": False, "partial": bool, "converted": {...} | None,
            "unsupported": [...], "message": str, "license_status": str}``
    """
    if not isinstance(source, str):
        raise TypeError(  # pragma: no cover — sanity guard
            f"source must be a str; got {type(source).__name__}."
        )

    report = validate_source(source)

    # ── Hard block — license-protected sources ────────────────────────
    if report.blocked:
        return {
            "success": False,
            "partial": False,
            "converted": None,
            "unsupported": [report.block_reason] if report.block_reason else [],
            "message": (
                report.block_reason
                or "Script is marked protected / invite-only / paid."
            ),
            "license_status": report.license_status.value,
        }

    program = parse_source(source)
    strategy_dict, notes = map_program(program)

    # Combine validator notes (license, prohibited constructs) with
    # mapper notes (unsupported / partial conversions).
    all_notes: list[str] = list(report.notes) + list(notes)
    unsupported_items: list[str] = list(report.prohibited_constructs)
    unsupported_items.extend(program.unsupported_calls)

    # ── Hard block — prohibited constructs found ──────────────────────
    if report.prohibited_constructs:
        return {
            "success": False,
            "partial": False,
            "converted": None,
            "unsupported": unsupported_items,
            "message": (
                "Source uses prohibited constructs that cannot be imported "
                "safely: " + "; ".join(report.prohibited_constructs) + "."
            ),
            "license_status": report.license_status.value,
        }

    # ── Schema validation ─────────────────────────────────────────────
    try:
        validated = StrategyJSON.model_validate(strategy_dict)
    except ValidationError as exc:
        return {
            "success": False,
            "partial": True,
            "converted": strategy_dict,
            "unsupported": unsupported_items,
            "message": (
                "Generated strategy did not pass StrategyJSON validation: "
                f"{exc.errors()[0]['msg'] if exc.errors() else exc!s}"
            ),
            "license_status": report.license_status.value,
        }

    # ── Partial-but-valid (some unsupported elements found) ───────────
    if program.unsupported_calls:
        return {
            "success": False,
            "partial": True,
            "converted": validated.model_dump(by_alias=True, mode="json"),
            "unsupported": unsupported_items,
            "message": (
                "Strategy imported with caveats: "
                + ", ".join(program.unsupported_calls)
                + "."
            ),
            "license_status": report.license_status.value,
        }

    # ── Success ──────────────────────────────────────────────────────
    return {
        "success": True,
        "strategy": validated.model_dump(by_alias=True, mode="json"),
        "explanation": explain(program, report, all_notes),
        "license_status": report.license_status.value,
        "notes": all_notes,
    }


__all__ = ["convert_pine_to_strategy"]
