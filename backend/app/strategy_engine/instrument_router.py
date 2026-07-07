"""Instrument-type classifier — first brick of the instrument-router.

Read-only, side-effect-free. Maps a ``Strategy`` to its instrument type
(``"futures" | "options" | "cash"``) so a future router can branch ABOVE the
executor (see ``docs/MULTI_INSTRUMENT_ISOLATION_AUDIT.md`` →
"INSTRUMENT-ROUTER SEAM").

This module is intentionally **NOT wired into any execution path yet** — it is
a pure classifier with no callers in the live flow. Wiring it into the entry
seam (``signal_execution._process_entry``) and the exit seam
(``signal_execution._process_direct_exit``) is a separate later module.

SAFETY INVARIANT
----------------
Any strategy with no clear instrument marker resolves to ``"futures"``. The
live real-money strategies (BSE / CDSL / ANGELONE) have ``strategy_json IS
NULL``, so they deterministically classify as ``"futures"`` and can never be
routed off the existing NFO-hardcoded futures path.

Detection mirrors :func:`app.services.pine_mapper.is_options_strategy`: a
forward-compat top-level ``instrument_type`` attribute is read first, then the
``strategy_json`` marker, then the presence of an ``options`` config block.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid a runtime import of the ORM model (keeps this pure)
    from app.db.models.strategy import Strategy

#: Instrument types the router understands. ``"futures"`` is the safety
#: default for every ambiguous / unmarked / unknown case.
FUTURES = "futures"
OPTIONS = "options"
CASH = "cash"

#: Explicit markers accepted in an ``instrument_type`` value (case-insensitive,
#: whitespace-trimmed). Anything else is treated as "unrecognised" and falls
#: through to the futures default — never an error, never an off-futures route.
_KNOWN_MARKERS: frozenset[str] = frozenset({FUTURES, OPTIONS, CASH})


def _classify_marker(marker: object) -> str | None:
    """Normalise an ``instrument_type`` value to a known type, or ``None``.

    ``None`` means "not a recognised marker" — the caller continues to the
    next detection step rather than defaulting early. Non-string inputs and
    unknown strings both return ``None``.
    """
    if not isinstance(marker, str):
        return None
    normalised = marker.strip().lower()
    if normalised in _KNOWN_MARKERS:
        return normalised
    return None


def resolve_instrument_type(strategy: "Strategy | None") -> str:
    """Classify a strategy as ``"futures" | "options" | "cash"``.

    First-match-wins, futures-default. Pure and side-effect-free; **not wired
    into execution yet.**

    Order:
      1. ``strategy is None`` → ``"futures"`` (safety default).
      2. Forward-compat top-level ``strategy.instrument_type`` attribute, when
         it is a recognised marker (mirrors ``is_options_strategy`` reading
         ``getattr`` first). Unrecognised values fall through.
      3. ``strategy.strategy_json`` is not a dict (incl. ``None``) →
         ``"futures"``. **This is the live BSE/CDSL/ANGELONE case
         (``strategy_json IS NULL``).**
      4. ``strategy_json["instrument_type"]`` marker (cash / options / futures).
      5. ``strategy_json["options"]`` dict block → ``"options"`` (mirrors
         ``is_options_strategy``).
      6. Fall-through → ``"futures"`` (safety default).
    """
    # 1. No strategy at all → futures.
    if strategy is None:
        return FUTURES

    # 2. Forward-compat top-level attribute (a future migration may add the
    #    column). Only a recognised marker wins; anything else falls through
    #    so the futures-default behaviour is preserved.
    direct = _classify_marker(getattr(strategy, "instrument_type", None))
    if direct is not None:
        return direct

    # 3. No usable strategy_json → futures. THIS is the live-strategy path:
    #    BSE/CDSL/ANGELONE have strategy_json IS NULL.
    strategy_json = getattr(strategy, "strategy_json", None)
    if not isinstance(strategy_json, dict):
        return FUTURES

    # 4. Explicit marker inside strategy_json.
    marker = _classify_marker(strategy_json.get("instrument_type"))
    if marker is not None:
        return marker

    # 5. Options config block present (no/unknown marker) → options.
    if isinstance(strategy_json.get("options"), dict):
        return OPTIONS

    # 6. Anything unclear → futures (safety default).
    return FUTURES


__all__ = ["resolve_instrument_type", "FUTURES", "OPTIONS", "CASH"]
