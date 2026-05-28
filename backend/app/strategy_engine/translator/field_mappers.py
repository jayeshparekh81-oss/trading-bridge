"""Per-field prose → StrategyJSON conversion rules.

Two layers:
    * ``parse_indicator_id`` — recover the registry ``(type, params)``
      pair from a snake-case instance id like ``ema_9`` or ``macd_12_26_9``.
    * ``parse_condition``   — match a prose entry/exit condition string
      against a small ordered ruleset and return the corresponding
      structured :class:`~app.strategy_engine.schema.strategy.Condition`.

Both are intentionally narrow on coverage in this prototype — we
target the high-volume mechanical patterns first (single-indicator
crossovers, scalar comparisons, basic time guards) and surface
everything else as ``UnparseableConditionError`` so the override
catalog gets a complete failure list per Queue AA's Option Z hybrid
recommendation.
"""

from __future__ import annotations

import re
from typing import Any, Final

from app.strategy_engine.schema.strategy import (
    Condition,
    IndicatorCondition,
    IndicatorConditionOp,
    IndicatorConfig,
    TimeCondition,
    TimeConditionOp,
)
from app.strategy_engine.translator.errors import (
    UnknownIndicatorError,
    UnparseableConditionError,
)


# ─── Indicator id grammar ───────────────────────────────────────────────


#: Indicator id parameter conventions per registry ``type``.
#: Maps a registry type to the parameter NAMES whose VALUES are encoded
#: positionally in the snake-case id suffix.
#: e.g. ``ema_9``  -> type=ema,  params={period: 9}
#:      ``rsi_14`` -> type=rsi,  params={period: 14}
#:      ``macd_12_26_9`` -> type=macd, params={fast_period: 12, slow_period: 26, signal_period: 9}
#:      ``ichimoku_9_26_52`` -> type=ichimoku, params={tenkan_period: 9, kijun_period: 26, senkou_b_period: 52}
_INDICATOR_PARAM_SCHEMA: Final[dict[str, list[str]]] = {
    "ema": ["period"],
    "sma": ["period"],
    "wma": ["period"],
    "rsi": ["period"],
    "cci": ["period"],
    "atr": ["period"],
    "adx": ["period"],
    "mfi": ["period"],
    "cmf": ["period"],
    "williams_r": ["period"],
    "hull_ma": ["period"],
    "donchian_channel": ["period"],
    "supertrend": ["atr_period", "multiplier"],
    "macd": ["fast_period", "slow_period", "signal_period"],
    "ichimoku": ["tenkan_period", "kijun_period", "senkou_b_period"],
    "aroon_up": ["period"],
    "aroon_down": ["period"],
    "camarilla_pivots": [],
    "vwap": [],
    "obv": [],
}

#: Template-shorthand → canonical registry type. Used by
#: ``parse_indicator_id`` BEFORE the longest-prefix match so
#: ``bb_20_2`` resolves to ``bollinger_bands`` and ``orb_15`` to
#: ``opening_range_breakout``.
_INDICATOR_ID_ALIASES: Final[dict[str, str]] = {
    "bb": "bollinger_bands",
    "orb": "opening_range_breakout",
}

#: Param schemas keyed on the CANONICAL type (after alias expansion). Param
#: NAMES must match the registry's InputSpec names (registry.py / _pack8_active.py)
#: so ``validate_indicator_params`` accepts them downstream — e.g. bollinger uses
#: ``std_dev`` (not ``std``) and ORB uses ``range_minutes`` (not ``minutes``).
_INDICATOR_PARAM_SCHEMA["bollinger_bands"] = ["period", "std_dev"]
_INDICATOR_PARAM_SCHEMA["opening_range_breakout"] = ["range_minutes"]

#: Indicators whose id may carry NO numeric suffix (plain singletons).
_PARAMLESS_INDICATORS: Final[frozenset[str]] = frozenset(
    {ind for ind, params in _INDICATOR_PARAM_SCHEMA.items() if not params}
)


def parse_indicator_id(ind_id: str) -> IndicatorConfig:
    """Recover ``(type, params)`` from a snake-case instance id.

    Strategy:
        1. Try paramless: if ``ind_id`` is exactly a known paramless
           registry id, return with empty params.
        2. Strip the longest known type prefix that matches; parse the
           remaining ``_N_M_...`` digits as the type's positional
           parameters.

    Raises :class:`UnknownIndicatorError` when neither path resolves.
    """
    if ind_id in _PARAMLESS_INDICATORS:
        return IndicatorConfig(id=ind_id, type=ind_id, params={})

    # Alias expansion: ``bb_20_2`` -> match on canonical ``bollinger_bands``.
    expanded_prefix_map: dict[str, str] = {}
    for shorthand, canonical in _INDICATOR_ID_ALIASES.items():
        if ind_id.startswith(shorthand + "_"):
            expanded_prefix_map[shorthand] = canonical

    # Longest-prefix match — try multi-word types first so ``donchian_channel_20``
    # doesn't get classified as type=donchian.
    candidates = sorted(
        (t for t in _INDICATOR_PARAM_SCHEMA if ind_id.startswith(t + "_")),
        key=len,
        reverse=True,
    )
    for ind_type in candidates:
        suffix = ind_id[len(ind_type) + 1 :]
        parts = suffix.split("_")
        if not all(p.isdigit() for p in parts):
            continue
        nums = [int(p) for p in parts]
        param_names = _INDICATOR_PARAM_SCHEMA[ind_type]
        if len(nums) != len(param_names):
            continue
        return IndicatorConfig(
            id=ind_id,
            type=ind_type,
            params=dict(zip(param_names, nums, strict=True)),
        )

    # Fall back to alias-prefix paths if no direct candidate matched.
    for shorthand, canonical in expanded_prefix_map.items():
        suffix = ind_id[len(shorthand) + 1 :]
        parts = suffix.split("_")
        if not all(p.isdigit() for p in parts):
            continue
        nums = [int(p) for p in parts]
        param_names = _INDICATOR_PARAM_SCHEMA.get(canonical, [])
        if len(nums) != len(param_names):
            continue
        return IndicatorConfig(
            id=ind_id,
            type=canonical,
            params=dict(zip(param_names, nums, strict=True)),
        )

    raise UnknownIndicatorError(ind_id)


# ─── Condition grammar ──────────────────────────────────────────────────


# Indicator id token: lower-snake, must start with a letter.
_IND_ID = r"[a-z][a-z0-9_]*"
# Numeric scalar token. Accepts an optional ``+`` or ``-`` sign so prose
# like ``"cci_20 crosses above +100"`` or ``"williams_r_14 crosses above -80"``
# parses cleanly without losing the sign.
_NUM = r"[+-]?\d+(?:\.\d+)?"
# Time token (HH:MM).
_TIME = r"\d{2}:\d{2}"


_PATTERNS: Final[list[tuple[re.Pattern[str], str]]] = [
    # Rule 1: indicator crossover ("ema_9 crosses above ema_21")
    (
        re.compile(
            rf"^(?P<left>{_IND_ID})\s+crosses\s+above\s+(?P<right>{_IND_ID})$",
            re.IGNORECASE,
        ),
        "ind_crossover_ind",
    ),
    (
        re.compile(
            rf"^(?P<left>{_IND_ID})\s+crosses\s+below\s+(?P<right>{_IND_ID})$",
            re.IGNORECASE,
        ),
        "ind_crossunder_ind",
    ),
    # Rule 2a: indicator-vs-scalar comparison ("rsi_14 > 70", "adx_14 >= 25")
    (
        re.compile(
            rf"^(?P<left>{_IND_ID})\s*(?P<op>>=|<=|>|<)\s*(?P<value>{_NUM})$"
        ),
        "ind_compare_value",
    ),
    # Rule 2b: indicator-vs-indicator non-crossover comparison
    # ("rsi_14 > 50" is Rule 2a; "ema_9 > ema_21" is this rule).
    # We use a NEGATIVE lookahead on `_NUM` after the operator so the
    # value-form (Rule 2a) wins when the RHS parses as a number; the
    # ordering of registration ALSO matters because both patterns can
    # match an ambiguous shape — value form is registered first.
    (
        re.compile(
            rf"^(?P<left>{_IND_ID})\s*(?P<op>>=|<=|>|<)\s*(?P<right>{_IND_ID})$"
        ),
        "ind_compare_ind",
    ),
    # Rule 2c: indicator-crosses-scalar — there's no crossover-vs-value
    # op in the schema (CROSSOVER requires `right` indicator id). We map
    # ``"X crosses above N"`` and the verbose ``"... from below"`` variant
    # to a steady-state ``GT`` comparison. Loses the crossover semantics
    # (single-bar edge vs steady state) — flagged for founder review
    # for strategies where the difference matters (e.g. mean-reversion
    # bounces where re-entry on the same condition would be wrong).
    # See FOUNDER_OVERRIDES_NEEDED.md for the affected templates.
    (
        re.compile(
            rf"^(?P<left>{_IND_ID})\s+crosses\s+above\s+(?P<value>{_NUM})"
            r"(?:\s+from\s+below)?$",
            re.IGNORECASE,
        ),
        "ind_cross_above_value",
    ),
    (
        re.compile(
            rf"^(?P<left>{_IND_ID})\s+crosses\s+below\s+(?P<value>{_NUM})"
            r"(?:\s+from\s+above)?$",
            re.IGNORECASE,
        ),
        "ind_cross_below_value",
    ),
    # Rule 3: time-of-day comparators ("timestamp >= 09:30", "time after 14:45")
    (
        re.compile(
            rf"^(?:timestamp|time)\s*(?P<op>>=|<=|>|<)\s*(?P<value>{_TIME})(?:\s+IST)?$",
            re.IGNORECASE,
        ),
        "time_compare",
    ),
    (
        re.compile(
            rf"^time\s+(?P<op>after|before)\s+(?P<value>{_TIME})(?:\s+IST)?$",
            re.IGNORECASE,
        ),
        "time_after_before",
    ),
]


_TIME_OP_FROM_COMPARATOR: Final[dict[str, TimeConditionOp]] = {
    ">": TimeConditionOp.AFTER,
    ">=": TimeConditionOp.AFTER,
    "<": TimeConditionOp.BEFORE,
    "<=": TimeConditionOp.BEFORE,
    "after": TimeConditionOp.AFTER,
    "before": TimeConditionOp.BEFORE,
}


def parse_condition(prose: str, *, field: str) -> Condition:
    """Translate a single prose condition into a structured Condition.

    Convenience wrapper around :func:`parse_conditions` for callers that
    expect exactly one condition. Raises
    :class:`UnparseableConditionError` if the prose decomposes into
    zero or more than one condition; use :func:`parse_conditions` for
    multi-clause prose.
    """
    parts = parse_conditions(prose, field=field)
    if len(parts) != 1:
        raise UnparseableConditionError(
            prose, field=field
        )
    return parts[0]


def parse_conditions(prose: str, *, field: str) -> list[Condition]:
    """Translate a prose string into one or more structured Conditions.

    Splits on top-level ``" AND "`` / ``" OR "`` (case-insensitive,
    space-required to avoid eating tokens like ``"ANDREW"`` or
    ``"OR_VAR"``) and parses each clause independently. The decision of
    whether to combine with AND vs OR is the caller's — only AND is
    supported in this prototype (EntryRules.operator defaults to AND).
    Mixed ``AND`` + ``OR`` in the same prose raises
    :class:`UnparseableConditionError` since the schema's flat operator
    field can't express precedence.

    Per-clause normalisation:
        * Trailing parenthetical commentary is stripped:
          ``"cmf_20 > 0.05 (positive money flow)"`` becomes
          ``"cmf_20 > 0.05"``. Decorative copy in seed templates is
          common; semantically irrelevant.
        * ``"crosses back above|below"`` is treated as ``"crosses
          above|below"`` — same op, just stylistic.

    Raises:
        :class:`UnparseableConditionError` when any clause doesn't match
            a grammar rule or when the prose mixes AND with OR.
    """
    cleaned = prose.strip()
    if not cleaned:
        raise UnparseableConditionError("", field=field)

    has_and = bool(re.search(r"\s+AND\s+", cleaned, re.IGNORECASE))
    has_or = bool(re.search(r"\s+OR\s+", cleaned, re.IGNORECASE))
    if has_and and has_or:
        raise UnparseableConditionError(
            prose, field=field
        )

    splitter = re.compile(
        r"\s+AND\s+" if has_and else (r"\s+OR\s+" if has_or else r"$^"),
        re.IGNORECASE,
    )
    clauses = splitter.split(cleaned) if (has_and or has_or) else [cleaned]

    out: list[Condition] = []
    for clause in clauses:
        clause_s = _normalise_clause(clause)
        for pattern, rule_name in _PATTERNS:
            m = pattern.match(clause_s)
            if not m:
                continue
            out.append(_build_condition(m, rule_name))
            break
        else:
            raise UnparseableConditionError(prose, field=field)
    return out


_TRAILING_PAREN_RE: Final[re.Pattern[str]] = re.compile(r"\s*\([^)]*\)\s*$")
_CROSSES_BACK_RE: Final[re.Pattern[str]] = re.compile(
    r"\bcrosses\s+back\s+(above|below)\b", re.IGNORECASE
)


def _normalise_clause(clause: str) -> str:
    """Strip trailing parentheticals and ``crosses back`` filler."""
    stripped = clause.strip()
    # Repeat-strip in case of nested or multiple trailing parens.
    while True:
        new = _TRAILING_PAREN_RE.sub("", stripped).strip()
        if new == stripped:
            break
        stripped = new
    stripped = _CROSSES_BACK_RE.sub(r"crosses \1", stripped)
    return stripped


def _build_condition(match: re.Match[str], rule: str) -> Condition:
    """Construct the Condition variant for the matched grammar rule."""
    if rule == "ind_crossover_ind":
        return IndicatorCondition(
            type="indicator",
            left=match["left"].lower(),
            op=IndicatorConditionOp.CROSSOVER,
            right=match["right"].lower(),
        )
    if rule == "ind_crossunder_ind":
        return IndicatorCondition(
            type="indicator",
            left=match["left"].lower(),
            op=IndicatorConditionOp.CROSSUNDER,
            right=match["right"].lower(),
        )
    if rule == "ind_compare_value":
        return IndicatorCondition(
            type="indicator",
            left=match["left"].lower(),
            op=IndicatorConditionOp(match["op"]),
            value=float(match["value"]),
        )
    if rule == "ind_compare_ind":
        return IndicatorCondition(
            type="indicator",
            left=match["left"].lower(),
            op=IndicatorConditionOp(match["op"]),
            right=match["right"].lower(),
        )
    if rule == "ind_cross_above_value":
        return IndicatorCondition(
            type="indicator",
            left=match["left"].lower(),
            op=IndicatorConditionOp.GT,
            value=float(match["value"]),
        )
    if rule == "ind_cross_below_value":
        return IndicatorCondition(
            type="indicator",
            left=match["left"].lower(),
            op=IndicatorConditionOp.LT,
            value=float(match["value"]),
        )
    if rule == "time_compare" or rule == "time_after_before":
        return TimeCondition(
            type="time",
            op=_TIME_OP_FROM_COMPARATOR[match["op"].lower()],
            value=match["value"],
        )
    raise RuntimeError(f"unknown rule {rule!r} — grammar/handler drift")  # pragma: no cover


def trading_hours_to_time_condition(
    start: str, end: str
) -> TimeCondition:
    """Project the template's ``trading_hours`` block into a single
    ``BETWEEN`` :class:`TimeCondition`. Used by the entry-rules builder
    to gate every entry on session hours.
    """
    return TimeCondition(
        type="time",
        op=TimeConditionOp.BETWEEN,
        value=start,
        end=end,
    )


__all__ = [
    "parse_condition",
    "parse_conditions",
    "parse_indicator_id",
    "trading_hours_to_time_condition",
]
