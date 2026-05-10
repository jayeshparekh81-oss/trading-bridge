"""Pine source pattern extractor — regex-based, NOT a full parser.

Recognises the basic safe subset documented in the Phase 7 master
prompt:

    Indicator assignments
        ``name = ta.func(arg1, arg2, ...)`` for func in
        {ema, sma, rsi, macd, bb, atr, vwap, highest, lowest}.

    Cross-conditions
        ``name = ta.crossover(a, b)``  /  ``ta.crossunder(a, b)``
        Stored as the pending entry / exit condition until an
        ``if name`` block ties it to a strategy direction.

    Strategy directives
        ``strategy.entry("id", strategy.long | strategy.short)``
        ``strategy.close(...)``

The output is a tiny dataclass tree, *not* a real syntax tree. Anything
the regexes don't recognise is either ignored (declarations the importer
doesn't need) or surfaced as an unsupported note via the validator —
this module never raises for unfamiliar Pine.

**No eval / exec / compile / dynamic import.** The module is regexes
plus dataclasses; pure textual extraction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

from app.strategy_engine.pine_import.lexer import preprocess

# ─── AST shapes ────────────────────────────────────────────────────────


class CrossKind(StrEnum):
    CROSSOVER = "crossover"
    CROSSUNDER = "crossunder"


class EntryDirection(StrEnum):
    LONG = "long"
    SHORT = "short"


@dataclass(frozen=True)
class IndicatorCall:
    """``var = ta.<func>(<arg>, ...)`` — one indicator assignment."""

    var_name: str
    func: str
    args: tuple[str | int | float, ...]


@dataclass(frozen=True)
class CrossCall:
    """``var = ta.crossover(a, b)`` or ``ta.crossunder(a, b)``."""

    var_name: str
    kind: CrossKind
    left: str
    right: str


@dataclass(frozen=True)
class StrategyEntry:
    """``strategy.entry(<id_str>, strategy.long|short)`` directive."""

    label: str
    direction: EntryDirection
    triggered_by: str | None
    """The variable name from the surrounding ``if <var>`` block, when
    present. ``None`` if the call lives at module scope."""


@dataclass(frozen=True)
class StrategyClose:
    """``strategy.close(...)`` directive."""

    triggered_by: str | None


@dataclass(frozen=True)
class PineProgram:
    """Output of :func:`parse_source`."""

    indicators: tuple[IndicatorCall, ...] = field(default_factory=tuple)
    crosses: tuple[CrossCall, ...] = field(default_factory=tuple)
    entries: tuple[StrategyEntry, ...] = field(default_factory=tuple)
    closes: tuple[StrategyClose, ...] = field(default_factory=tuple)
    unsupported_calls: tuple[str, ...] = field(default_factory=tuple)
    """``ta.foo`` calls that aren't on the supported list — surfaced
    so the converter can mark the import as partial."""


# ─── Supported function whitelist ──────────────────────────────────────

#: ``ta.<func>`` names this importer recognises.
#:
#: Original Phase 7 set: ``ema sma rsi macd bb atr vwap highest lowest``.
#: Batch 1 extension (commit-local): adds 22 names covering the most
#: common Pine v5/v6 TA functions. Six map to ACTIVE registry
#: indicators and produce a full strategy; sixteen map to COMING_SOON
#: ones and surface a note (same pattern as ``highest``/``lowest``)
#: so the user's import doesn't silently drop a recognisable
#: indicator. Adding to the set here is pure data — the parsing
#: algorithm is unchanged.
SUPPORTED_TA_INDICATORS: frozenset[str] = frozenset(
    {
        # Phase 7 originals.
        "ema",
        "sma",
        "rsi",
        "macd",
        "bb",
        "atr",
        "vwap",
        "highest",
        "lowest",
        # Batch 1 additions — ACTIVE in TRADETRI registry.
        "wma",
        "adx",
        "cmf",
        "trix",
        "aroon",
        "obv",
        # Batch 1 additions — COMING_SOON in TRADETRI registry.
        "stoch",
        "stoch_rsi",
        "cci",
        "mfi",
        "williams_r",
        "roc",
        "mom",
        "psar",
        "supertrend",
        "donchian",
        "keltner",
        "dema",
        "tema",
        "hma",
        "vwma",
        "heikinashi",
        # Pack 2 ACTIVE additions (commit 511f591 + dispatch follow-up):
        # ``ta.rma`` -> ``smma`` (Wilder's smoothed MA), ``ta.cmo`` ->
        # ``chande_momentum``. Both were never in the importer before.
        "rma",
        "cmo",
        # Pack 4 ACTIVE additions — Pine ta.* names that map to Pack 4
        # registry ids (real Pine functions, not invented):
        #   ta.pivothigh -> swing_high
        #   ta.pivotlow  -> swing_low
        #   ta.stdev     -> std_dev
        #   ta.variance  -> variance
        #   ta.correlation -> correlation_coefficient
        # The other 7 Pack 4 indicators (camarilla / woodie / regression
        # channel / HV / TR / HL spread / inside bar) have no standard
        # Pine equivalent and are deliberately not registered here.
        "pivothigh",
        "pivotlow",
        "stdev",
        "variance",
        "correlation",
        # Pack 5 ACTIVE additions — Pine ta.* names that map to Pack 5
        # registry ids:
        #   ta.percentrank             -> percentile_rank
        #   ta.percentile_nearest_rank -> percentile_nearest
        #   ta.median                  -> median_value
        # The other 9 Pack 5 indicators (sharpe / sortino / calmar /
        # omega / max_drawdown_pct / underwater_curve /
        # recovery_factor / hurst_exponent / zscore) are
        # builder-UI only — no standard Pine equivalent.
        "percentrank",
        "percentile_nearest_rank",
        "median",
        # Pack 6 ACTIVE additions — Pine ta.* names that map to Pack 6
        # registry ids:
        #   ta.accdist -> accumulation_distribution
        #   ta.ao      -> awesome_oscillator
        # The other 10 Pack 6 indicators (chaikin_oscillator,
        # price_volume_trend, ease_of_movement, twiggs_money_flow,
        # mass_index, elder_ray_bull, elder_ray_bear,
        # choppiness_index, bollinger_bandwidth,
        # bollinger_percent_b) have no standard Pine equivalent
        # and are deliberately not registered here.
        # ``ta.uo`` exists in Pine but ``ultimate_oscillator`` is
        # already an active in TRADETRI's registry (Phase 9), out
        # of Pack 6's scope.
        "accdist",
        "ao",
        # Pack 7 ACTIVE additions — Pine ta.* names that map to
        # Pack 7 registry ids:
        #   ta.vortex -> vortex_positive (the negative line is a
        #                separate registry config; the parser
        #                doesn't unpack tuples).
        # ``ta.aroon`` and ``ta.trix`` already wired to the pre-
        # existing ``aroon`` / ``trix`` actives — out of Pack 7
        # scope to re-wire. Other Pack 7 indicators
        # (klinger_volume_oscillator, detrended_price_oscillator,
        # coppock_curve, fisher_transform, chande_kroll_stop,
        # relative_vigor_index, balance_of_power) have no standard
        # Pine v5 equivalent.
        "vortex",
    }
)


# ─── Regex patterns ────────────────────────────────────────────────────


_IDENT = r"[A-Za-z_][A-Za-z0-9_]*"

_TA_CALL_ASSIGN = re.compile(
    rf"""^\s*
        (?P<var>{_IDENT})\s*=\s*
        ta\s*\.\s*(?P<fn>{_IDENT})
        \s*\((?P<args>[^()]*)\)
        \s*$""",
    re.VERBOSE | re.MULTILINE,
)

_CROSS_ASSIGN = re.compile(
    rf"""^\s*
        (?P<var>{_IDENT})\s*=\s*
        ta\s*\.\s*(?P<kind>crossover|crossunder)
        \s*\(\s*(?P<a>{_IDENT})\s*,\s*(?P<b>{_IDENT})\s*\)
        \s*$""",
    re.VERBOSE | re.MULTILINE,
)

_STRATEGY_ENTRY = re.compile(
    r"""strategy\s*\.\s*entry\s*\(
        \s*"(?P<label>[^"]*)"\s*,
        \s*strategy\s*\.\s*(?P<dir>long|short)\b""",
    re.VERBOSE,
)

_STRATEGY_CLOSE = re.compile(
    r"strategy\s*\.\s*close(?:_all)?\s*\("
)

# Track ``if <name>`` blocks so we can attribute the strategy.* call
# living on the indented next line back to the trigger variable.
_IF_LINE = re.compile(rf"^\s*if\s+(?P<var>{_IDENT})\s*$", re.MULTILINE)


# ─── Public API ────────────────────────────────────────────────────────


def parse_source(source: str) -> PineProgram:
    """Extract the supported subset from ``source``.

    Returns a :class:`PineProgram`. The function never raises for
    unknown Pine — anything not recognised is either ignored or surfaced
    via ``unsupported_calls``.
    """
    pre = preprocess(source)
    code = pre.code

    crosses: list[CrossCall] = []
    indicators: list[IndicatorCall] = []
    unsupported_calls: set[str] = set()

    # --- Cross conditions ---
    cross_var_names: set[str] = set()
    for match in _CROSS_ASSIGN.finditer(code):
        cross_var_names.add(match.group("var"))
        crosses.append(
            CrossCall(
                var_name=match.group("var"),
                kind=CrossKind(match.group("kind")),
                left=match.group("a"),
                right=match.group("b"),
            )
        )

    # --- Indicator assignments ---
    for match in _TA_CALL_ASSIGN.finditer(code):
        var = match.group("var")
        if var in cross_var_names:
            # Already handled by _CROSS_ASSIGN.
            continue
        fn = match.group("fn")
        args_str = match.group("args")
        if fn in {"crossover", "crossunder"}:
            # Cross with non-identifier args → unsupported.
            unsupported_calls.add(f"ta.{fn} with non-identifier arguments")
            continue
        if fn not in SUPPORTED_TA_INDICATORS:
            unsupported_calls.add(f"ta.{fn}")
            continue
        try:
            args = _parse_args(args_str)
        except _ArgParseError as exc:
            unsupported_calls.add(f"ta.{fn} ({exc})")
            continue
        indicators.append(IndicatorCall(var_name=var, func=fn, args=args))

    # --- Strategy directives ---
    if_blocks = _build_if_index(code)
    entries: list[StrategyEntry] = []
    for match in _STRATEGY_ENTRY.finditer(code):
        triggered_by = _enclosing_if(match.start(), code, if_blocks)
        entries.append(
            StrategyEntry(
                label=match.group("label"),
                direction=EntryDirection(match.group("dir")),
                triggered_by=triggered_by,
            )
        )

    closes: list[StrategyClose] = []
    for match in _STRATEGY_CLOSE.finditer(code):
        triggered_by = _enclosing_if(match.start(), code, if_blocks)
        closes.append(StrategyClose(triggered_by=triggered_by))

    return PineProgram(
        indicators=tuple(indicators),
        crosses=tuple(crosses),
        entries=tuple(entries),
        closes=tuple(closes),
        unsupported_calls=tuple(sorted(unsupported_calls)),
    )


# ─── Argument parsing ──────────────────────────────────────────────────


class _ArgParseError(Exception):
    """Raised internally when arguments aren't simple identifiers / numbers."""


_ARG_KWARG = re.compile(rf"^({_IDENT})\s*=\s*(.+)$")


def _parse_args(args_str: str) -> tuple[str | int | float, ...]:
    """Split args by top-level commas; classify each as id / number.

    Args may carry ``name=value`` kwargs — we accept them and use the
    *value*, dropping the keyword. This keeps the importer working on
    typical scripts like ``ta.ema(close, length=20)`` while avoiding
    the complexity of mapping arbitrary kwargs to parameter positions.
    """
    parts = [p.strip() for p in args_str.split(",") if p.strip()]
    out: list[str | int | float] = []
    for part in parts:
        kwarg = _ARG_KWARG.match(part)
        value = kwarg.group(2).strip() if kwarg else part
        out.append(_classify(value))
    return tuple(out)


def _classify(token: str) -> str | int | float:
    if re.fullmatch(r"-?\d+", token):
        return int(token)
    if re.fullmatch(r"-?\d+\.\d+", token):
        return float(token)
    if re.fullmatch(_IDENT, token):
        return token
    raise _ArgParseError(f"unsupported argument {token!r}")


# ─── If-block attribution ──────────────────────────────────────────────


def _build_if_index(code: str) -> list[tuple[int, int, str]]:
    """For every ``if <var>`` line, record (start_idx, end_idx, var_name).

    ``end_idx`` is the index of the next non-indented line (block end)
    or end of source. Pine uses Python-like indentation; any line whose
    indent is greater than the ``if`` line's belongs to that block.
    """
    blocks: list[tuple[int, int, str]] = []
    lines = code.split("\n")
    line_starts: list[int] = []
    cursor = 0
    for line in lines:
        line_starts.append(cursor)
        cursor += len(line) + 1  # +1 for the newline

    for line_no, line in enumerate(lines):
        m = _IF_LINE.match(line)
        if m is None:
            continue
        if_indent = len(line) - len(line.lstrip())
        # Walk forward to find the first less-or-equal-indented line.
        end_line_no = len(lines)
        for j in range(line_no + 1, len(lines)):
            sibling = lines[j]
            stripped = sibling.strip()
            if stripped == "":
                continue
            indent = len(sibling) - len(sibling.lstrip())
            if indent <= if_indent:
                end_line_no = j
                break
        end_idx = (
            line_starts[end_line_no] if end_line_no < len(lines) else len(code)
        )
        blocks.append((line_starts[line_no], end_idx, m.group("var")))
    return blocks


def _enclosing_if(
    pos: int, code: str, blocks: list[tuple[int, int, str]]
) -> str | None:
    """Return the var name of the innermost ``if`` block containing ``pos``."""
    del code  # only present for symmetry with the index builder
    for start, end, var in reversed(blocks):
        if start <= pos < end:
            return var
    return None


__all__ = [
    "SUPPORTED_TA_INDICATORS",
    "CrossCall",
    "CrossKind",
    "EntryDirection",
    "IndicatorCall",
    "PineProgram",
    "StrategyClose",
    "StrategyEntry",
    "parse_source",
]
