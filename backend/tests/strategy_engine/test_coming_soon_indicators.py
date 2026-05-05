"""Coming-soon indicator guard rails.

Phase 9 grows the registry past 100 entries. Most of the new rows are
``status = COMING_SOON`` stubs whose ``calculation_function`` is
``None``. They show up in the builder UI as planned-but-not-yet
indicators.

Two contracts must hold:

    * Coming-soon entries never resolve to a calculation. Any caller
      asking for one should get a clear error that names the status,
      not a confusing ``AttributeError`` or silent ``None``.

    * Active entries always resolve. This is also covered in
      :mod:`test_registry`, but pinning it here keeps both invariants
      visible side-by-side.
"""

from __future__ import annotations

import pytest

from app.strategy_engine.indicators import (
    INDICATOR_REGISTRY,
    IndicatorParamError,
    get_calculation_function,
)
from app.strategy_engine.schema.indicator import IndicatorStatus


def _coming_soon_ids() -> list[str]:
    return [
        meta.id
        for meta in INDICATOR_REGISTRY.values()
        if meta.status is IndicatorStatus.COMING_SOON
    ]


def test_registry_actually_has_coming_soon_entries() -> None:
    """Sanity — the rest of this file is meaningless without coming-soon rows."""
    assert _coming_soon_ids(), (
        "Phase 9 expansion missing — no COMING_SOON entries in the registry."
    )


def test_get_calculation_function_raises_for_every_coming_soon_entry() -> None:
    """Resolving any coming-soon id must raise IndicatorParamError clearly."""
    failures: list[str] = []
    for cs_id in _coming_soon_ids():
        try:
            get_calculation_function(cs_id)
        except IndicatorParamError as exc:
            # Error message should reference the status string so
            # operators understand why it failed.
            if "coming_soon" not in str(exc):
                failures.append(f"{cs_id}: message did not mention coming_soon: {exc!s}")
        else:
            failures.append(f"{cs_id}: no exception raised")
    assert not failures, "Coming-soon guard regressions:\n" + "\n".join(failures)


def test_coming_soon_entries_have_no_calculation_function_string() -> None:
    """Metadata invariant: ``calculation_function`` must be None for stubs."""
    bad = [
        m.id
        for m in INDICATOR_REGISTRY.values()
        if m.status is IndicatorStatus.COMING_SOON
        and m.calculation_function is not None
    ]
    assert bad == [], (
        f"Coming-soon entries with a calculation_function: {bad}"
    )


@pytest.mark.parametrize(
    "active_id",
    [
        "adx",
        "dmi",
        "aroon",
        "trix",
        "ultimate_oscillator",
        "cmf",
        "force_index",
        "linear_regression",
        "pivot_points",
        "ichimoku",
    ],
)
def test_each_phase_9_active_resolves_to_a_callable(active_id: str) -> None:
    """The 10 new actives all resolve to callable calculation functions."""
    fn = get_calculation_function(active_id)
    assert callable(fn)
