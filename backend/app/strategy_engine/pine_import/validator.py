"""License + safety validation for Pine source.

The validator is the importer's first gate. It:

    * Detects license markers and classifies them into the buckets the
      compliance policy cares about (permissive, GPL family →
      ``compliance_required``, none/unknown → ``needs_review``).
    * Refuses scripts that advertise ``protected``, ``invite-only``, or
      ``paid`` access — these belong to their authors and we will not
      ingest them.
    * Lists prohibited constructs (``request.security``, arrays, complex
      loops, labels/tables/boxes, custom user functions, unknown
      ``strategy.*`` calls). The mapper consults this list to decide
      whether to return ``success=False`` or to flag a partial import.

The validator is **purely textual** — it scans the input string with
``re``. There is no evaluation, no AST construction, and no import.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class LicenseStatus(StrEnum):
    """Compliance classification of the source's license header."""

    PERMISSIVE = "permissive"
    """MIT / Apache-2.0 / BSD / public domain — no further action needed."""

    COMPLIANCE_REQUIRED = "compliance_required"
    """GPL family (GPL, LGPL, AGPL) — derivative work must respect the license."""

    NEEDS_REVIEW = "needs_review"
    """No clear license header — operator must confirm rights before use."""

    BLOCKED = "blocked"
    """Protected / invite-only / paid markers — script cannot be imported."""


class ValidationReport(BaseModel):
    """Output of :func:`validate_source`. Frozen + JSON-friendly."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    license_status: LicenseStatus
    license_match: str | None = Field(default=None, max_length=128)
    blocked: bool = False
    block_reason: str | None = Field(default=None, max_length=256)
    prohibited_constructs: tuple[str, ...] = Field(default_factory=tuple)
    notes: tuple[str, ...] = Field(default_factory=tuple)


# ─── License detection ─────────────────────────────────────────────────


_PERMISSIVE_PATTERNS: dict[str, re.Pattern[str]] = {
    "MIT": re.compile(r"\bMIT\b(?!\s*-?\s*free)", re.IGNORECASE),
    "Apache-2.0": re.compile(
        r"\bApache(?:\s+License)?[\s\-]*(?:2(?:\.0)?)?\b", re.IGNORECASE
    ),
    "BSD": re.compile(r"\bBSD\b", re.IGNORECASE),
    "public domain": re.compile(r"\bpublic\s+domain\b", re.IGNORECASE),
    "Unlicense": re.compile(r"\bunlicense\b", re.IGNORECASE),
}

_GPL_PATTERNS: dict[str, re.Pattern[str]] = {
    "AGPL": re.compile(r"\bAGPL(?:[\-\s]?v?[23](?:\.0)?)?\b", re.IGNORECASE),
    "LGPL": re.compile(r"\bLGPL(?:[\-\s]?v?[23](?:\.0)?)?\b", re.IGNORECASE),
    "GPL": re.compile(r"\bGPL(?:[\-\s]?v?[23](?:\.0)?)?\b", re.IGNORECASE),
}

#: Mozilla Public License — common on TradingView; treat as compliance-required.
_MPL_PATTERN: re.Pattern[str] = re.compile(
    r"Mozilla\s+Public\s+License", re.IGNORECASE
)

_BLOCK_PATTERNS: dict[str, re.Pattern[str]] = {
    "protected": re.compile(r"\bprotected\b", re.IGNORECASE),
    "invite-only": re.compile(r"invite[\-\s]?only", re.IGNORECASE),
    "paid": re.compile(r"\bpaid(?:\s+access|\s+only|\s+script)?\b", re.IGNORECASE),
}


def _detect_license(source: str) -> tuple[LicenseStatus, str | None]:
    """Run the license patterns in priority order. First match wins."""
    # Block markers take precedence — refusing is safer than guessing.
    for label, pattern in _BLOCK_PATTERNS.items():
        if pattern.search(source):
            return LicenseStatus.BLOCKED, label

    for label, pattern in _PERMISSIVE_PATTERNS.items():
        if pattern.search(source):
            return LicenseStatus.PERMISSIVE, label

    for label, pattern in _GPL_PATTERNS.items():
        if pattern.search(source):
            return LicenseStatus.COMPLIANCE_REQUIRED, label

    if _MPL_PATTERN.search(source):
        return LicenseStatus.COMPLIANCE_REQUIRED, "MPL-2.0"

    return LicenseStatus.NEEDS_REVIEW, None


# ─── Prohibited constructs ─────────────────────────────────────────────


_PROHIBITED_CONSTRUCT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "request.security() — multi-symbol / higher-timeframe lookup",
        re.compile(r"\brequest\s*\.\s*security\b"),
    ),
    (
        "request.financial() / request.economic() — external data",
        re.compile(r"\brequest\s*\.\s*(?:financial|economic|dividends|splits|earnings)\b"),
    ),
    (
        "array / matrix construction (array.new_*, matrix.new_*)",
        re.compile(r"\b(?:array|matrix)\s*\.\s*new[_a-z]*\b"),
    ),
    (
        "for / while loops",
        re.compile(r"^\s*(?:for|while)\b", re.MULTILINE),
    ),
    (
        "label / table / box drawing primitives",
        re.compile(r"\b(?:label|table|box|line|polyline)\s*\.\s*new\b"),
    ),
    (
        "custom user-defined functions (`f(...) =>`)",
        re.compile(r"^\s*[A-Za-z_][A-Za-z0-9_]*\s*\([^)]*\)\s*=>", re.MULTILINE),
    ),
    (
        "user-defined types (`type Foo`)",
        re.compile(r"^\s*type\s+[A-Za-z_]", re.MULTILINE),
    ),
)


_KNOWN_STRATEGY_CALLS: frozenset[str] = frozenset(
    {"entry", "close", "exit", "close_all", "long", "short"}
)


def _detect_prohibited_constructs(source: str) -> list[str]:
    """Return the labels of every prohibited construct present in ``source``."""
    found: list[str] = []
    for label, pattern in _PROHIBITED_CONSTRUCT_PATTERNS:
        if pattern.search(source):
            found.append(label)

    # Detect unknown strategy.* calls.
    for match in re.finditer(r"strategy\s*\.\s*([A-Za-z_]+)", source):
        name = match.group(1)
        if name not in _KNOWN_STRATEGY_CALLS:
            found.append(f"unknown strategy.{name}() call")
    return found


# ─── Public API ────────────────────────────────────────────────────────


def validate_source(source: str) -> ValidationReport:
    """Run license + safety checks on ``source``. Pure textual scan."""
    license_status, license_match = _detect_license(source)
    notes: list[str] = []
    blocked = False
    block_reason: str | None = None

    if license_status is LicenseStatus.BLOCKED:
        blocked = True
        block_reason = (
            f"Source advertises {license_match!r} access — protected / invite-only "
            "/ paid scripts cannot be imported."
        )

    prohibited = tuple(dict.fromkeys(_detect_prohibited_constructs(source)))

    if license_status is LicenseStatus.NEEDS_REVIEW:
        notes.append(
            "No license marker detected. Confirm you have rights to import this script."
        )
    if license_status is LicenseStatus.COMPLIANCE_REQUIRED:
        notes.append(
            f"License {license_match!r} requires derivative-work compliance — "
            "review the license terms before deploying."
        )

    return ValidationReport(
        license_status=license_status,
        license_match=license_match,
        blocked=blocked,
        block_reason=block_reason,
        prohibited_constructs=prohibited,
        notes=tuple(notes),
    )


__all__ = ["LicenseStatus", "ValidationReport", "validate_source"]
