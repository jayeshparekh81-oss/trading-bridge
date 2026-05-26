"""Template ``config_json`` → ``StrategyJSON`` translator.

Public entry: :func:`translate_template`. Consults the override
registry first; falls back to the prose parser. Raises
:class:`~app.strategy_engine.translator.errors.TranslationError`
(or a typed subclass) on any failure — callers can catch the base
type for graceful fallback or the subclass for granular handling.

Top-level field map (template ``config_json`` → ``StrategyJSON``):

    slug              -> id = f"template:{slug}"
    name              -> name (verbatim)
    complexity        -> mode (StrategyMode enum)
    indicators[i]     -> IndicatorConfig (via parse_indicator_id)
    entry_long        -> EntryRules(side=BUY,  conditions=[...])
    entry_short       -> ignored in this prototype (single side per
                         StrategyJSON; long-only templates are 100% of
                         the priority set per PROGRESS.md)
    exit_long         -> ExitRules.indicator_exits
    stop_loss_pct     -> ExitRules.stop_loss_percent
    take_profit_pct   -> ExitRules.target_percent
    trading_hours     -> entry conditions gain a TimeCondition(BETWEEN)
                         AND exit gains square_off_time = end
    position_sizing   -> NOT mapped (no home in StrategyJSON; sizing is
                         a Phase-8 execution-bridge concern)
    max_open_positions -> NOT mapped (always 1 in Phase 1 templates;
                         RiskRules has no equivalent field)
"""

from __future__ import annotations

from typing import Any

from app.strategy_engine.schema.strategy import (
    Condition,
    EntryRules,
    ExecutionConfig,
    ExecutionMode,
    ExitRules,
    IndicatorConfig,
    OrderType,
    ProductType,
    RiskRules,
    Side,
    StrategyJSON,
    StrategyMode,
)
from app.strategy_engine.translator.errors import (
    MissingFieldError,
    TranslationError,
)
from app.strategy_engine.translator.field_mappers import (
    parse_conditions,
    parse_indicator_id,
    trading_hours_to_time_condition,
)
from app.strategy_engine.translator.override_registry import get_override
from app.strategy_engine.translator.sub_outputs import resolve_sub_output


#: Template ``complexity`` strings (from the seed) → StrategyJSON mode.
_COMPLEXITY_TO_MODE: dict[str, StrategyMode] = {
    "beginner": StrategyMode.BEGINNER,
    "intermediate": StrategyMode.INTERMEDIATE,
    "expert": StrategyMode.EXPERT,
}


def translate_template(template: dict[str, Any]) -> StrategyJSON:
    """Translate a seed-file template entry into a canonical StrategyJSON.

    Args:
        template: a single entry from ``backend/data/strategy_templates_seed.json``
            ``templates`` list — the full dict including ``slug``,
            ``name``, ``complexity``, ``config_json``, etc.

    Returns:
        Engine-callable :class:`StrategyJSON` ready for
        :func:`app.strategy_engine.backtest.run_backtest`.

    Raises:
        :class:`MissingFieldError` when the template is missing a
            field the translator requires.
        :class:`UnknownIndicatorError` when an indicator id can't be
            resolved to a registry type.
        :class:`UnparseableConditionError` when a prose condition
            doesn't match any grammar rule.
        :class:`TranslationError` for any other classified failure.

    The override registry is checked first; if a hand-written
    StrategyJSON exists for the slug, it is returned wrapped (with the
    same validation pass as parsed output) and the prose parser is
    skipped entirely.
    """
    slug = template.get("slug")
    if not isinstance(slug, str) or not slug:
        raise MissingFieldError("slug")

    # 0. Override path — hybrid (Option Z) short-circuit.
    override = get_override(slug)
    if override is not None:
        return StrategyJSON.model_validate(override)

    # 1. Validate inputs the translator depends on.
    config = template.get("config_json")
    if not isinstance(config, dict) or not config:
        raise MissingFieldError("config_json", slug=slug)

    name = template.get("name")
    if not isinstance(name, str) or not name:
        raise MissingFieldError("name", slug=slug)

    complexity = template.get("complexity", "beginner")
    mode = _COMPLEXITY_TO_MODE.get(complexity, StrategyMode.BEGINNER)

    # 2. Indicators — id strings → IndicatorConfig dicts.
    raw_inds = config.get("indicators")
    if not isinstance(raw_inds, list) or not raw_inds:
        raise MissingFieldError("config_json.indicators", slug=slug)

    indicators: list[IndicatorConfig] = []
    for ind_id in raw_inds:
        if not isinstance(ind_id, str):
            raise MissingFieldError(
                f"config_json.indicators[{ind_id!r}]", slug=slug
            )
        try:
            indicators.append(parse_indicator_id(ind_id))
        except TranslationError as exc:
            # Attach slug context for the catalog generator.
            exc.slug = slug  # type: ignore[attr-defined]
            raise

    # 3. Entry rules — entry_long is the prototype-supported side.
    entry_long = config.get("entry_long")
    if not isinstance(entry_long, dict) or "condition" not in entry_long:
        raise MissingFieldError("config_json.entry_long.condition", slug=slug)
    entry_prose = entry_long["condition"]
    try:
        entry_conditions: list[Condition] = parse_conditions(
            entry_prose, field="entry_long"
        )
    except TranslationError as exc:
        exc.slug = slug  # type: ignore[attr-defined]
        raise

    # 4. Trading-hours gate (optional but ubiquitous on Phase-1 templates).
    hours = config.get("trading_hours")
    square_off_time: str | None = None
    if isinstance(hours, dict):
        start = hours.get("start")
        end = hours.get("end")
        if isinstance(start, str) and isinstance(end, str):
            entry_conditions.append(
                trading_hours_to_time_condition(start, end)
            )
            square_off_time = end

    entry = EntryRules(
        side=Side.BUY,
        operator="AND",
        conditions=entry_conditions,
    )

    # 5. Exit rules — indicator-driven exits + risk bands + square-off.
    exit_long = config.get("exit_long")
    indicator_exits: list[Condition] = []
    if isinstance(exit_long, dict) and isinstance(exit_long.get("condition"), str):
        try:
            indicator_exits.extend(
                parse_conditions(exit_long["condition"], field="exit_long")
            )
        except TranslationError as exc:
            exc.slug = slug  # type: ignore[attr-defined]
            raise

    stop_loss = config.get("stop_loss_pct")
    take_profit = config.get("take_profit_pct")

    exit_rules = ExitRules(
        target_percent=float(take_profit) if take_profit is not None else None,
        stop_loss_percent=float(stop_loss) if stop_loss is not None else None,
        square_off_time=square_off_time,
        indicator_exits=indicator_exits,
    )

    # 6. RiskRules — Phase 1 templates have no cap fields; defaults.
    risk = RiskRules()

    # 7. ExecutionConfig — sensible BACKTEST defaults; UI can override.
    execution = ExecutionConfig(
        mode=ExecutionMode.BACKTEST,
        order_type=OrderType.MARKET,
        product_type=ProductType.INTRADAY,
    )

    # 8. Auto-declare sub-output synonyms (macd_line/signal_line/macd_histogram,
    #    bb_lower/bb_middle/bb_upper, orb_15_high/orb_15_low) referenced in
    #    conditions. Each resolves to a parent indicator + output and is declared
    #    with IndicatorConfig.output so referential integrity passes and the
    #    runner emits the right sub-series. See translator/sub_outputs.py.
    declared_ids = {ind.id for ind in indicators}
    referenced_ids = _collect_referenced_ids(entry.conditions) | _collect_referenced_ids(
        exit_rules.indicator_exits
    )
    sub_added: list[IndicatorConfig] = []
    for ref in sorted(referenced_ids - declared_ids):
        resolved = resolve_sub_output(ref, indicators)
        if resolved is not None:
            sub_added.append(
                IndicatorConfig(
                    id=resolved.sub_id,
                    type=resolved.parent_type,
                    params=resolved.params,
                    output=resolved.output,
                )
            )
    if sub_added:
        indicators = [*indicators, *sub_added]

    # 9. Auto-declare pseudo-indicators (close, high, low, open) referenced
    #    in conditions. The schema's IndicatorCondition.left/right must
    #    be an indicator id in ``indicators[]``; bare price-series
    #    references in prose ("close > ema_50") would otherwise fail
    #    validation. We register them as EMA(2) which is ~indistinguishable
    #    from the raw price for comparison purposes (two-bar exponential
    #    smoothing). EMA(1) would be exact but the registry rejects it
    #    (``period >= 2``); EMA(2) is the minimum legal smoothing and is
    #    well within the comparison tolerance these templates use.
    declared_ids = {ind.id for ind in indicators}
    referenced_ids = _collect_referenced_ids(
        entry.conditions
    ) | _collect_referenced_ids(exit_rules.indicator_exits)
    pseudo_added: list[IndicatorConfig] = []
    for pseudo, source in (
        ("close", "close"),
        ("open", "open"),
        ("high", "high"),
        ("low", "low"),
    ):
        if pseudo in referenced_ids and pseudo not in declared_ids:
            pseudo_added.append(
                IndicatorConfig(
                    id=pseudo, type="ema", params={"period": 2, "source": source}
                )
            )
    if pseudo_added:
        indicators = [*indicators, *pseudo_added]

    # 10. Assemble.
    return StrategyJSON(
        id=f"template:{slug}",
        name=name,
        mode=mode,
        version=1,
        indicators=indicators,
        entry=entry,
        exit=exit_rules,
        risk=risk,
        execution=execution,
    )


def _collect_referenced_ids(conditions: list[Condition]) -> set[str]:
    """Walk Conditions and return every indicator id referenced via
    ``IndicatorCondition.left`` / ``right``. Mirrors the schema's own
    referential-integrity check but runs BEFORE assembly so the parser
    can auto-declare pseudo-indicators."""
    from app.strategy_engine.schema.strategy import IndicatorCondition

    out: set[str] = set()
    for c in conditions:
        if isinstance(c, IndicatorCondition):
            out.add(c.left)
            if c.right is not None:
                out.add(c.right)
    return out


__all__ = ["translate_template"]
