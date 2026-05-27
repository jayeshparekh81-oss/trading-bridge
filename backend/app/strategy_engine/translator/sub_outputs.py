"""Sub-output synonym resolution for the template translator.

Seed templates reference indicator *sub-outputs* by bare snake-case name
(``macd_line``, ``signal_line``, ``bb_lower``, ``orb_15_high``) rather than the
parent instance id declared in ``config_json.indicators``. The StrategyJSON
referential-integrity validator rejects those undeclared ids. This module maps
each such name to its parent indicator + output so the parser can auto-declare a
sub-output :class:`IndicatorConfig` (carrying the ``output`` field) that the
backtest runner emits under the referenced name.

Two naming styles appear in the seed set:

* **Fixed semantic synonyms** — no params in the name; bind to the single
  declared parent of the matching registry type (``signal_line`` → the declared
  ``macd`` instance's ``signal`` line).
* **``<parent_id>_<suffix>``** — params embedded in the name; the prefix is a
  parseable instance id and the suffix names the output (``orb_15_high`` →
  parent ``orb_15`` + output ``high``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from app.strategy_engine.schema.strategy import IndicatorConfig
from app.strategy_engine.translator.errors import UnknownIndicatorError
from app.strategy_engine.translator.field_mappers import parse_indicator_id

#: Style A. ``token`` → ``(parent registry type, runner output key)``. The
#: output keys MUST match the sub-output suffixes emitted by
#: ``backtest/indicator_runner.py`` (macd → macd/signal/histogram;
#: bollinger_bands → upper/middle/lower).
_FIXED_SUBOUTPUT_SYNONYMS: Final[dict[str, tuple[str, str]]] = {
    "macd_line": ("macd", "macd"),
    "signal_line": ("macd", "signal"),
    "macd_histogram": ("macd", "histogram"),
    "bb_upper": ("bollinger_bands", "upper"),
    "bb_middle": ("bollinger_bands", "middle"),
    "bb_lower": ("bollinger_bands", "lower"),
}

#: Style B. parent registry type → valid output suffixes appended to a parseable
#: parent instance id (``orb_15`` + ``high`` → ``orb_15_high``).
_SUFFIX_SUBOUTPUTS: Final[dict[str, frozenset[str]]] = {
    "opening_range_breakout": frozenset({"high", "low"}),
}


@dataclass(frozen=True)
class ResolvedSubOutput:
    """Resolution of a sub-output reference to its parent indicator + output."""

    sub_id: str
    parent_type: str
    params: dict[str, Any]
    output: str


def resolve_sub_output(
    token: str, declared: list[IndicatorConfig]
) -> ResolvedSubOutput | None:
    """Resolve a referenced id to a parent indicator + output, or ``None``.

    ``None`` means the token is not a recognised sub-output reference — either a
    genuinely undeclared id (which the schema validator should still reject) or a
    Style-A synonym that is ambiguous because zero, or more than one, parent of
    the required type is declared.
    """
    # Style A — fixed semantic synonym, bound to the single declared parent.
    fixed = _FIXED_SUBOUTPUT_SYNONYMS.get(token)
    if fixed is not None:
        parent_type, output = fixed
        parents = [c for c in declared if c.type == parent_type]
        if len(parents) == 1:
            return ResolvedSubOutput(
                sub_id=token,
                parent_type=parent_type,
                params=dict(parents[0].params),
                output=output,
            )
        return None

    # Style B — "<parent_id>_<suffix>".
    for parent_type, suffixes in _SUFFIX_SUBOUTPUTS.items():
        for suffix in suffixes:
            if not token.endswith("_" + suffix):
                continue
            parent_id = token[: -(len(suffix) + 1)]
            try:
                cfg = parse_indicator_id(parent_id)
            except UnknownIndicatorError:
                continue
            if cfg.type == parent_type:
                return ResolvedSubOutput(
                    sub_id=token,
                    parent_type=parent_type,
                    params=dict(cfg.params),
                    output=suffix,
                )
    return None


__all__ = ["ResolvedSubOutput", "resolve_sub_output"]
