"""Parameter-sensitivity analysis — does the edge survive small param tweaks?

For each numeric tunable parameter on the strategy (indicator periods,
exit percentages), we build four variants at ``[-VAR, -VAR/2, +VAR/2,
+VAR]`` of the base value (``VAR = PARAMETER_SENSITIVITY_VARIATION =
0.20``), run the Phase 3 backtest on each, then score each via
:func:`calculate_trust_score`. A variant whose trust score drops more
than :data:`SENSITIVITY_DEGRADATION_POINTS` (20) below the base is
counted as "degraded".

If the fraction of degraded variants exceeds
:data:`PARAMETER_SENSITIVITY_FRAGILE_THRESHOLD` (0.30), the strategy is
flagged as fragile.

**Tunable parameter inventory** (Phase 4):

    Indicator params:   ``period`` (int, all single-period indicators),
                        ``std_dev`` (float, Bollinger),
                        ``fast_period`` / ``slow_period`` /
                        ``signal_period`` (int, MACD).
    Exit rules:         ``targetPercent``, ``stopLossPercent``,
                        ``trailingStopPercent``.

We deliberately do NOT vary:
    * Indicator ``source`` strings (categorical).
    * Entry / exit condition ``value`` constants — varying a comparator
      threshold like RSI < 30 by ±20 % changes meaning, not magnitude.
      Phase 9 may add a smarter param-mapping layer.
    * Risk caps — these are policy, not strategy edge.

The module orchestrates :func:`run_backtest` and
:func:`calculate_trust_score` exactly; no parallel implementation.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.strategy_engine.backtest import (
    BacktestInput,
    CostSettings,
    run_backtest,
)
from app.strategy_engine.backtest.runner import AmbiguityMode
from app.strategy_engine.reliability.constants import (
    PARAMETER_SENSITIVITY_FRAGILE_THRESHOLD,
    PARAMETER_SENSITIVITY_VARIATION,
    SENSITIVITY_DEGRADATION_POINTS,
)
from app.strategy_engine.reliability.trust_score import calculate_trust_score
from app.strategy_engine.schema.ohlcv import Candle
from app.strategy_engine.schema.strategy import StrategyJSON


class VariantOutcome(BaseModel):
    """One ``(param_path, variation, score)`` row."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    param_path: str = Field(..., min_length=1)
    base_value: float
    variant_value: float
    variation_pct: float
    score: int
    score_delta: int
    degraded: bool


class SensitivityResult(BaseModel):
    """Aggregate sensitivity verdict."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    base_score: int = Field(..., ge=0, le=100)
    tested_variants: tuple[VariantOutcome, ...]
    fragile: bool
    stability_score: float = Field(..., ge=0, le=1)
    warning: str = Field(default="", max_length=512)


# ─── Public API ────────────────────────────────────────────────────────


def run_sensitivity(
    *,
    strategy: StrategyJSON,
    candles: Sequence[Candle],
    initial_capital: float = 100_000.0,
    quantity: float = 1.0,
    cost_settings: CostSettings | None = None,
    ambiguity_mode: AmbiguityMode = AmbiguityMode.CONSERVATIVE,
) -> SensitivityResult:
    """Run sensitivity analysis on the strategy's tunable numeric params.

    Returns a :class:`SensitivityResult` with one :class:`VariantOutcome`
    per (param, variation) tested. When the strategy has no tunable
    params, returns a result with empty ``tested_variants`` and
    ``fragile=False``.
    """
    cost_settings = cost_settings or CostSettings()
    candles_list = list(candles)

    # Base score: full strategy run + score it.
    base_result = run_backtest(
        BacktestInput(
            candles=candles_list,
            strategy=strategy,
            initial_capital=initial_capital,
            quantity=quantity,
            cost_settings=cost_settings,
            ambiguity_mode=ambiguity_mode,
        )
    )
    base_score = calculate_trust_score(base_result).score

    base_dict = strategy.model_dump(by_alias=True)
    variations = _variation_factors()

    variants: list[VariantOutcome] = []
    for path, base_value in _enumerate_tunables(base_dict):
        for variation in variations:
            new_value = _apply_variation(base_value, variation, path)
            variant_dict = copy.deepcopy(base_dict)
            # Period-style fields must be written back as int — Phase 3's
            # indicator_runner rejects floats for int-only params (e.g.
            # ``ema(period=16.0)`` raises). For float-only fields like
            # ``std_dev`` and ``targetPercent`` we keep float.
            written_value: float | int = int(new_value) if _is_int_field(path) else new_value
            _set_path(variant_dict, path, written_value)
            try:
                variant_strategy = StrategyJSON.model_validate(variant_dict)
            except Exception:
                # A variation pushed the value out of the schema's allowed
                # range (e.g. period < 2). Treat as a non-degraded "skip".
                continue

            variant_result = run_backtest(
                BacktestInput(
                    candles=candles_list,
                    strategy=variant_strategy,
                    initial_capital=initial_capital,
                    quantity=quantity,
                    cost_settings=cost_settings,
                    ambiguity_mode=ambiguity_mode,
                )
            )
            variant_score = calculate_trust_score(variant_result).score
            score_delta = variant_score - base_score
            degraded = (-score_delta) > SENSITIVITY_DEGRADATION_POINTS

            variants.append(
                VariantOutcome(
                    param_path=path,
                    base_value=float(base_value),
                    variant_value=float(new_value),
                    variation_pct=variation,
                    score=variant_score,
                    score_delta=score_delta,
                    degraded=degraded,
                )
            )

    fragile, stability, warning = _summarise(variants)
    return SensitivityResult(
        base_score=base_score,
        tested_variants=tuple(variants),
        fragile=fragile,
        stability_score=stability,
        warning=warning,
    )


# ─── Internal helpers ──────────────────────────────────────────────────


def _variation_factors() -> tuple[float, ...]:
    """``[-V, -V/2, +V/2, +V]`` per locked spec."""
    v = PARAMETER_SENSITIVITY_VARIATION
    return (-v, -v / 2, v / 2, v)


#: Tunable indicator-param keys per indicator type. The dispatcher walks
#: ``strategy.indicators[*].params`` and only varies these named keys.
_TUNABLE_INDICATOR_KEYS: dict[str, tuple[str, ...]] = {
    "ema": ("period",),
    "sma": ("period",),
    "wma": ("period",),
    "rsi": ("period",),
    "atr": ("period",),
    "volume_sma": ("period",),
    "macd": ("fast_period", "slow_period", "signal_period"),
    "bollinger_bands": ("period", "std_dev"),
}

#: Exit-rule fields we vary (camelCase since base_dict was dumped by_alias).
_TUNABLE_EXIT_KEYS: tuple[str, ...] = (
    "targetPercent",
    "stopLossPercent",
    "trailingStopPercent",
)


def _enumerate_tunables(strategy_dict: dict[str, Any]) -> list[tuple[str, float]]:
    """Walk the dumped strategy dict and yield ``(path, value)`` pairs.

    ``path`` is a dotted JSON pointer-style key the runner re-uses to
    write back the variant value via :func:`_set_path`.
    """
    out: list[tuple[str, float]] = []

    indicators = strategy_dict.get("indicators") or []
    for idx, indicator in enumerate(indicators):
        ind_type = indicator.get("type")
        params = indicator.get("params") or {}
        for key in _TUNABLE_INDICATOR_KEYS.get(ind_type, ()):
            if (
                key in params
                and isinstance(params[key], (int, float))
                and not isinstance(params[key], bool)
            ):
                out.append((f"indicators[{idx}].params.{key}", float(params[key])))

    exit_rules = strategy_dict.get("exit") or {}
    for key in _TUNABLE_EXIT_KEYS:
        value = exit_rules.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out.append((f"exit.{key}", float(value)))

    return out


def _apply_variation(base: float, variation: float, path: str) -> float:
    """Apply ``base * (1 + variation)`` and round to int when the path is
    one of the int-only fields (``period``, ``fast_period``, etc.).

    A variant rounded to a value <= 0 (e.g. period * 0.8 -> 0 for period=1)
    would be rejected by the schema; we leave that edge to the caller's
    try/except in :func:`run_sensitivity`.
    """
    raw = base * (1.0 + variation)
    if _is_int_field(path):
        return float(round(raw))
    return raw


#: Path suffixes whose runtime type must be ``int`` (Phase 1 indicator
#: schema enforces it; Phase 3 indicator_runner._coerce_int rejects float).
_INT_FIELD_SUFFIXES: tuple[str, ...] = (
    "params.period",
    "params.fast_period",
    "params.slow_period",
    "params.signal_period",
)


def _is_int_field(path: str) -> bool:
    return any(path.endswith(suffix) for suffix in _INT_FIELD_SUFFIXES)


def _set_path(d: dict[str, Any], path: str, value: float | int) -> None:
    """Write ``value`` into ``d`` at the dotted/indexed ``path``.

    Path syntax (kept narrow on purpose):
        * ``a.b.c``               — nested dict access
        * ``a[idx].b``            — list index then dict key
    """
    parts = _tokenize_path(path)
    cursor: Any = d
    for token in parts[:-1]:
        cursor = _follow(cursor, token)
    last = parts[-1]
    if isinstance(last, int):
        cursor[last] = value
    else:
        cursor[last] = value


def _tokenize_path(path: str) -> list[str | int]:
    """Split ``a[0].b.c`` -> ``['a', 0, 'b', 'c']``."""
    out: list[str | int] = []
    for chunk in path.split("."):
        # Each chunk may carry a [N] suffix.
        while "[" in chunk:
            head, _, rest = chunk.partition("[")
            idx_str, _, tail = rest.partition("]")
            if head:
                out.append(head)
            out.append(int(idx_str))
            chunk = tail
        if chunk:
            out.append(chunk)
    return out


def _follow(cursor: Any, token: str | int) -> Any:
    if isinstance(token, int):
        return cursor[token]
    return cursor[token]


def _summarise(variants: list[VariantOutcome]) -> tuple[bool, float, str]:
    """Compute ``(fragile, stability_score, warning)`` from the variant list."""
    if not variants:
        return False, 1.0, ""
    degraded_count = sum(1 for v in variants if v.degraded)
    fragile_fraction = degraded_count / len(variants)
    fragile = fragile_fraction > PARAMETER_SENSITIVITY_FRAGILE_THRESHOLD
    stability = 1.0 - fragile_fraction
    warning = ""
    if fragile:
        warning = (
            f"{int(fragile_fraction * 100)} % of parameter variants degraded "
            f"the trust score by more than {SENSITIVITY_DEGRADATION_POINTS} "
            "points — strategy is fragile."
        )
    return fragile, stability, warning


__all__ = ["SensitivityResult", "VariantOutcome", "run_sensitivity"]
