"""Symbol normalisation for broker-vs-stored position comparison.

WHY THIS EXISTS
---------------
The two sides of a position comparison spell the same contract differently:

    stored / TradingView canonical :  BSE-AUG2026-FUT   NIFTY-MAY2026-FUT
    broker (Dhan tradingSymbol)    :  BSE26AUGFUT       NIFTY24DECFUT
    options                        :  BSE-16JUL2026-2400-CE

A raw string comparison says "different", which a naive caller reads as "the
broker is FLAT". That is the dangerous direction: it would wrongly flip a
customer to MANUAL, or skip a legitimate exit and leave them exposed.

THE RULE (founder, design-locked)
---------------------------------
If a symbol cannot be matched CONFIDENTLY, the answer is UNKNOWN — never
"flat", never "different". :func:`symbols_match` therefore returns a
**tri-state**::

    True  -> same contract, confidently
    False -> different contract, confidently
    None  -> cannot tell (either side unparseable) -> caller must treat as
             POSITION_UNKNOWN and place nothing

Both the fan-out position gate and the subscriber drift service use this one
implementation, so they can never disagree about what "same position" means.

Pure: no DB, no broker, no I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)

_MONTHS: dict[str, int] = {
    m: i
    for i, m in enumerate(
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
         "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"],
        start=1,
    )
}

#: ``BSE-AUG2026-FUT`` — the canonical/TradingView monthly future. Mirrors
#: futures_resolver._CANONICAL_FUT_RE.
_CANONICAL_FUT = re.compile(r"^([A-Z][A-Z0-9]*)-([A-Z]{3})(\d{4})-FUT$")

#: ``BSE26AUGFUT`` / ``NIFTY24DECFUT`` — the compact broker form (YY then MMM).
#: Root is non-greedy so a digit-bearing root (NIFTY50…) still resolves.
_COMPACT_FUT = re.compile(r"^([A-Z][A-Z0-9]*?)(\d{2})([A-Z]{3})FUT$")

#: ``BSE-16JUL2026-2400-CE`` — day-stamped (weekly) option leg.
_OPTION = re.compile(
    r"^([A-Z][A-Z0-9]*)-(\d{1,2})([A-Z]{3})(\d{4})-(\d+(?:\.\d+)?)-(CE|PE)$"
)

#: ``BSE-AUG2026-3200-CE`` — MONTHLY option leg, no day stamp. Same shape as
#: ``_CANONICAL_FUT`` with a strike and CE/PE in place of ``FUT``.
#:
#: This is the spelling Dhan actually returns for monthly option legs on the
#: founder's account, and it went UNPARSED until 2026-08-30. That was not a
#: cosmetic gap: an unparsed sibling row poisons ``total_matching_quantity``
#: into UNKNOWN, so every drift pass on an account holding monthly options
#: returned "cannot tell" and the drift protection was inert there. Parsing it
#: costs nothing and is what makes the feature usable on a real account.
_OPTION_MONTHLY = re.compile(
    r"^([A-Z][A-Z0-9]*)-([A-Z]{3})(\d{4})-(\d+(?:\.\d+)?)-(CE|PE)$"
)

#: Plain equity, optionally exchange-prefixed / ``-EQ`` suffixed.
_EQUITY = re.compile(r"^(?:(?:NSE|BSE|NFO|BFO):)?([A-Z][A-Z0-9]*?)(?:-EQ)?$")


@dataclass(frozen=True)
class NormalizedSymbol:
    """Contract identity, independent of spelling."""

    root: str
    #: ``FUT`` | ``CE`` | ``PE`` | ``EQ``
    kind: str
    year: int | None = None
    month: int | None = None
    day: int | None = None
    strike: str | None = None

    def key(self) -> tuple:
        """Comparable identity tuple."""
        return (self.root, self.kind, self.year, self.month, self.day, self.strike)


def _expand_year(yy: str) -> int:
    """``26`` -> 2026. Two-digit years in this domain are always 20xx."""
    return 2000 + int(yy)


def normalize_symbol(raw: str | None) -> NormalizedSymbol | None:
    """Parse a symbol into a contract identity, or ``None`` if not confident.

    ``None`` means "I could not confidently parse this" and MUST propagate as
    UNKNOWN — it never means equality or inequality.
    """
    if raw is None:
        return None
    sym = str(raw).strip().upper()
    if not sym:
        return None

    # Strip a leading exchange prefix once, uniformly.
    if ":" in sym:
        head, _, tail = sym.partition(":")
        if head in ("NSE", "BSE", "NFO", "BFO", "MCX", "CDS") and tail:
            sym = tail

    if (m := _CANONICAL_FUT.match(sym)) is not None:
        month = _MONTHS.get(m.group(2))
        if month is None:
            # Shape looks right but the month is nonsense (e.g. BSE-XYZ2026-FUT).
            # Refuse rather than guess.
            return None
        return NormalizedSymbol(
            root=m.group(1), kind="FUT", year=int(m.group(3)), month=month
        )

    if (m := _COMPACT_FUT.match(sym)) is not None:
        month = _MONTHS.get(m.group(3))
        if month is None:
            return None
        return NormalizedSymbol(
            root=m.group(1), kind="FUT", year=_expand_year(m.group(2)), month=month
        )

    if (m := _OPTION.match(sym)) is not None:
        month = _MONTHS.get(m.group(3))
        if month is None:
            return None
        strike = m.group(5)
        # Normalise 2400 / 2400.0 / 2400.00 to one spelling.
        strike = str(int(float(strike))) if float(strike).is_integer() else strike
        return NormalizedSymbol(
            root=m.group(1),
            kind=m.group(6),
            year=int(m.group(4)),
            month=month,
            day=int(m.group(2)),
            strike=strike,
        )

    if (m := _OPTION_MONTHLY.match(sym)) is not None:
        month = _MONTHS.get(m.group(2))
        if month is None:
            return None
        strike = m.group(4)
        # Same strike normalisation as the day-stamped form: 3200 / 3200.0 /
        # 3200.00 must be ONE spelling, or two rows in the same contract would
        # compare unequal and be counted as different instruments.
        strike = str(int(float(strike))) if float(strike).is_integer() else strike
        return NormalizedSymbol(
            root=m.group(1),
            kind=m.group(5),
            year=int(m.group(3)),
            month=month,
            day=None,          # monthly: no day stamp, and None is part of key()
            strike=strike,
        )

    if (m := _EQUITY.match(sym)) is not None:
        root = m.group(1)
        # A bare root that still looks like an UNPARSED derivative must not be
        # silently accepted as equity — we would then compare it confidently
        # when we do not actually understand it.
        #
        # Careful: plenty of real equities end in "CE"/"PE" (RELIANCE!), so
        # that suffix alone proves nothing. Only treat it as derivative-ish
        # when digits are present too (e.g. BSE24AUG2400CE). A trailing "FUT"
        # is unambiguous on its own.
        has_digit = any(ch.isdigit() for ch in root)
        if root.endswith("FUT") or (root.endswith(("CE", "PE")) and has_digit):
            return None
        return NormalizedSymbol(root=root, kind="EQ")

    return None


def symbols_match(stored: str | None, broker: str | None) -> bool | None:
    """Tri-state comparison. ``None`` = cannot tell (caller: POSITION_UNKNOWN).

    See the module docstring — ``None`` is the safety-critical case and must
    never be collapsed into ``False``.
    """
    a = normalize_symbol(stored)
    b = normalize_symbol(broker)
    if a is None or b is None:
        logger.warning(
            "symbol_match.unparseable",
            stored=stored,
            broker=broker,
            stored_parsed=a is not None,
            broker_parsed=b is not None,
            note="treated as UNKNOWN — never as flat",
        )
        return None
    return a.key() == b.key()


def total_matching_quantity(stored_symbol: str | None, broker_positions):
    """Total quantity the broker holds in ``stored_symbol``, across ALL rows.

    Returns ``(total, certain)`` with the same tri-state contract as
    :func:`find_matching_position`:
      * ``(n, True)``     - confident: the broker holds ``n`` in this contract
      * ``(0, True)``     - confidently NOT present
      * ``(None, False)`` - a symbol was unparseable; UNKNOWN, act on nothing

    WHY THIS EXISTS, separately from ``find_matching_position``.

    That function returns the FIRST matching row, which is correct for the
    presence/absence question the fan-out asks. It is WRONG for a quantity
    question: Dhan's /positions returns one row per (securityId, productType),
    so one contract can legitimately appear more than once - e.g. an NRML leg
    the bot opened and a MIS leg the account owner opened by hand. Reading only
    the first row under-reports the holding, and an under-reported holding
    looks exactly like a SHORTFALL, which is the drift detector's trigger.

    Concretely, that bug flips a customer who never closed anything: rows of
    200 and 800 against a stored 800 read as "broker holds 200", i.e. a partial
    close, i.e. AUTO -> MANUAL.

    ABSOLUTE values are summed, deliberately. On a hedged account (+800 NRML,
    -200 MIS) the signed net is 600, which is BELOW the stored 800 and would
    itself trigger a false flip. Summing magnitudes can only over-report, so it
    errs toward NOT flipping - the direction this whole subsystem is built to
    fail in. The cost is that a genuine close could be masked by an unrelated
    leg in the same contract; that is the milder failure (the customer simply
    stays on AUTO, and the fan-out's broker gate still refuses to act on an
    unverified position).
    """
    total = 0
    saw_unparseable = normalize_symbol(stored_symbol) is None
    for pos in broker_positions or []:
        verdict = symbols_match(stored_symbol, getattr(pos, "symbol", None))
        if verdict is True:
            try:
                total += abs(int(getattr(pos, "quantity", 0) or 0))
            except (TypeError, ValueError):
                saw_unparseable = True
        elif verdict is None:
            saw_unparseable = True
    if saw_unparseable:
        return None, False
    return total, True


def find_matching_position(stored_symbol: str | None, broker_positions):
    """Find the broker position matching ``stored_symbol``.

    Returns ``(position, certain)``:
      * ``(pos, True)``   — a confident match
      * ``(None, True)``  — confidently NOT present (every side parsed, none matched)
      * ``(None, False)`` — at least one symbol was unparseable, so the answer is
        UNKNOWN. The caller MUST treat this as POSITION_UNKNOWN and act on
        nothing.
    """
    saw_unparseable = normalize_symbol(stored_symbol) is None
    for pos in broker_positions or []:
        verdict = symbols_match(stored_symbol, getattr(pos, "symbol", None))
        if verdict is True:
            return pos, True
        if verdict is None:
            saw_unparseable = True
    return None, not saw_unparseable


__all__ = [
    "NormalizedSymbol",
    "find_matching_position",
    "normalize_symbol",
    "symbols_match",
    "total_matching_quantity",
]
