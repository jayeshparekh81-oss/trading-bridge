"""Typed errors raised by the template translator.

Each subclass carries enough structured context for the caller to either
(a) classify the failure for the founder-overrides workflow, or (b)
surface a sensible message in CI/test output. The base ``TranslationError``
is what end-callers should catch; subclasses exist for granular asserts
in tests and the override-catalog generator.
"""

from __future__ import annotations


class TranslationError(Exception):
    """Base — any prose-to-StrategyJSON failure inherits from this."""

    category: str = "TRANSLATION_ERROR"


class UnknownIndicatorError(TranslationError):
    """A token in the indicators list (or referenced in a condition)
    cannot be resolved to an ``IndicatorConfig`` shape. Raised by the
    indicator-id grammar layer when the prefix doesn't match a known
    registry ``type``.
    """

    category = "UNKNOWN_INDICATOR"

    def __init__(self, ind_id: str, *, slug: str | None = None) -> None:
        self.ind_id = ind_id
        self.slug = slug
        super().__init__(
            f"Unknown indicator id {ind_id!r}"
            + (f" in template {slug!r}" if slug else "")
        )


class UnparseableConditionError(TranslationError):
    """Prose condition string did not match any registered grammar
    pattern. Raised by ``parse_condition``. The full prose is preserved
    on the exception for the override catalog.
    """

    category = "UNPARSEABLE_CONDITION"

    def __init__(self, prose: str, *, field: str, slug: str | None = None) -> None:
        self.prose = prose
        self.field = field  # "entry_long" / "exit_long" / etc.
        self.slug = slug
        super().__init__(
            f"Cannot parse {field} condition {prose!r}"
            + (f" in template {slug!r}" if slug else "")
        )


class AmbiguousFieldError(TranslationError):
    """Prose matches more than one grammar rule and we cannot pick one
    without founder input. Carries the candidate interpretations.
    """

    category = "AMBIGUOUS_FIELD"

    def __init__(
        self,
        prose: str,
        *,
        field: str,
        candidates: list[str],
        slug: str | None = None,
    ) -> None:
        self.prose = prose
        self.field = field
        self.candidates = candidates
        self.slug = slug
        super().__init__(
            f"Ambiguous {field} prose {prose!r} matches {len(candidates)} grammar "
            f"rules: {candidates}"
            + (f" in template {slug!r}" if slug else "")
        )


class MissingFieldError(TranslationError):
    """Template ``config_json`` is missing a field required by the
    translator (e.g. ``entry_long`` for a long-only strategy). Distinct
    from Pydantic validation errors on the OUTPUT — these fire on the
    INPUT.
    """

    category = "MISSING_FIELD"

    def __init__(self, field: str, *, slug: str | None = None) -> None:
        self.field = field
        self.slug = slug
        super().__init__(
            f"Template config_json missing required field {field!r}"
            + (f" in template {slug!r}" if slug else "")
        )


__all__ = [
    "AmbiguousFieldError",
    "MissingFieldError",
    "TranslationError",
    "UnknownIndicatorError",
    "UnparseableConditionError",
]
