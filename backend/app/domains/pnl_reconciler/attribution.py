"""Founder's exit rule (2026-09-04): account-level attribution of a bot trade.

Why this exists
---------------
The founder trades the SAME contracts manually, in the same Dhan account the
bot uses. Our ``strategy_executions`` only see the bot's own orders (those with
``correlationId`` ``strategy-engine`` / ``strategy-engine-direct-exit``); every
other fill on the contract is the founder's manual activity and lives only in
the broker's trade book. A bot stop that fires AFTER the founder has already
flattened the position does not close the bot's trade — it opens a new one on
the founder's book — so pricing "bot entry → bot exit" can be wrong by the
whole move. The rule below prices a bot trade from what the ACCOUNT did.

The rule (verbatim from the founder, 2026-09-04)
------------------------------------------------
    A bot trade closes when the account goes FLAT on that contract by any
    fill, PROVIDED no manual lots on that contract predate the bot's entry.
    If prior manual lots exist — where lot-matching would be a guess —
    final_pnl stays NULL and the position carries a visible
    "human-interfered — not attributable" tag on the record.
    No lot-matching conventions. No guesses.

Operationalised, per closed position:

1. **Entry** = the bot's own entry fill(s) (order ids from our executions).
   No traded bot entry in the book → ``unpriceable`` (paper / phantom / TRANSIT).
2. **No prior lots**: the account's running net on the contract must be
   exactly 0 immediately before the first entry fill, and exactly the signed
   entry quantity right after the last one. Anything else →
   ``human_interfered``.
3. **Flat by any fill**: walk the book forward. Every fill until the net
   returns to 0 must REDUCE exposure (bot or manual). A fill that increases
   exposure, or that crosses through zero, means the exit price would be a
   lot-matching choice → ``human_interfered``. The net never returning to 0
   inside the supplied book → ``human_interfered`` (caller must supply fills
   past the position's ``closed_at``).
4. Otherwise the trade is priced from the entry fills and the reducing fills:
   ``bot_only`` when every exit fill is the bot's, ``account_flat`` when a
   manual fill took part in flattening.

This module is PURE (no DB, no broker). It never imports the sacred execution
path. Fills are ordered by the caller-supplied timestamp — the broker's
``exchangeTime`` — then order id, then trade id.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal

BOT_CORRELATION_IDS: frozenset[str] = frozenset({"strategy-engine", "strategy-engine-direct-exit"})

# Attribution tags stored on ``strategy_positions.pnl_attribution``.
TAG_BOT_ONLY = "bot_only"
TAG_ACCOUNT_FLAT = "account_flat"
TAG_HUMAN_INTERFERED = "human_interfered"
TAG_UNPRICEABLE = "unpriceable"
#: A PAPER trip (simulated fills, no broker book) priced from its own sim
#: fills. Real enough for the owner's paper view, NEVER for a live ledger:
#: the live snapshot counts only ``bot_only`` / ``account_flat``.
TAG_PAPER_SIM = "paper_sim"

#: Copy shown wherever a NULL P&L is explained (ledger / showcase / positions).
HUMAN_INTERFERED_LABEL = "human-interfered — not attributable"

ATTRIBUTION_TAGS: frozenset[str] = frozenset(
    {TAG_BOT_ONLY, TAG_ACCOUNT_FLAT, TAG_HUMAN_INTERFERED, TAG_UNPRICEABLE, TAG_PAPER_SIM}
)


@dataclass(frozen=True)
class AccountFill:
    """One traded fill of the whole ACCOUNT (bot or manual) on one contract."""

    contract: str  # stable contract key (Dhan securityId) — all fills of one contract share it
    order_id: str
    side: str  # BUY | SELL
    qty: int
    price: Decimal
    ts: str  # ISO-8601 exchange time; sorts chronologically as text
    trade_id: str = ""

    @property
    def signed_qty(self) -> int:
        return self.qty if self.side.upper() == "BUY" else -self.qty

    def describe(self, *, bot_order_ids: Iterable[str]) -> str:
        who = "BOT" if self.order_id in set(bot_order_ids) else "MANUAL"
        return f"{self.order_id} {who} {self.side.upper()} {self.qty} @{self.price} {self.ts}"


@dataclass(frozen=True)
class Attribution:
    """Outcome of applying the rule to one closed position."""

    tag: str
    entry_fills: tuple[AccountFill, ...]
    exit_fills: tuple[AccountFill, ...]
    gross_pnl: Decimal | None  # None unless priced
    reason: str  # human-readable, cites order ids

    @property
    def priced(self) -> bool:
        return self.tag in (TAG_BOT_ONLY, TAG_ACCOUNT_FLAT)

    @property
    def manual_exit(self) -> bool:
        return self.tag == TAG_ACCOUNT_FLAT

    @property
    def entry_qty(self) -> int:
        return sum(f.qty for f in self.entry_fills)

    @property
    def entry_turnover(self) -> Decimal:
        return sum((f.price * f.qty for f in self.entry_fills), Decimal(0))

    @property
    def exit_turnover(self) -> Decimal:
        return sum((f.price * f.qty for f in self.exit_fills), Decimal(0))

    @property
    def distinct_orders(self) -> int:
        return len({f.order_id for f in self.entry_fills} | {f.order_id for f in self.exit_fills})


def _sorted(fills: Iterable[AccountFill]) -> list[AccountFill]:
    return sorted(fills, key=lambda f: (f.ts, f.order_id, f.trade_id))


def attribute(
    entry_order_ids: Iterable[str],
    account_fills: Sequence[AccountFill],
    *,
    bot_order_ids: Iterable[str],
) -> Attribution:
    """Apply the founder's rule to one bot position.

    ``entry_order_ids`` — the bot's entry order id(s) for this position (from
    our executions). ``account_fills`` — EVERY traded futures fill of the
    account, all contracts welcome (filtered to the entry's contract here),
    covering the contract from its first fill through past the position's
    close. ``bot_order_ids`` — every order id the bot placed (used only to
    label fills and to pick ``bot_only`` vs ``account_flat``).
    """
    entry_ids = {str(o) for o in entry_order_ids}
    bot_ids = {str(o) for o in bot_order_ids}
    book = _sorted(account_fills)

    entry_idx = [i for i, f in enumerate(book) if f.order_id in entry_ids]
    if not entry_idx:
        return Attribution(
            TAG_UNPRICEABLE,
            (),
            (),
            None,
            "no traded bot entry fill in the account's trade book (paper / phantom / never filled)",
        )

    contract = book[entry_idx[0]].contract
    if any(book[i].contract != contract for i in entry_idx):
        return Attribution(
            TAG_HUMAN_INTERFERED, (), (), None, "entry fills span more than one contract"
        )

    # Running net on THIS contract, fill by fill, from the first fill supplied.
    net_before: dict[int, int] = {}
    net_after: dict[int, int] = {}
    running = 0
    for i, f in enumerate(book):
        if f.contract != contract:
            continue
        net_before[i] = running
        running += f.signed_qty
        net_after[i] = running

    entries = tuple(book[i] for i in entry_idx)
    first, last = entry_idx[0], entry_idx[-1]
    n0 = net_before[first]
    if n0 != 0:
        return Attribution(
            TAG_HUMAN_INTERFERED,
            entries,
            (),
            None,
            f"prior lots on the contract: account net was {n0:+d} immediately before the "
            f"bot's entry {entries[0].order_id} at {entries[0].ts}",
        )
    entry_qty = sum(f.qty for f in entries)
    sign = 1 if entries[0].side.upper() == "BUY" else -1
    if any(f.signed_qty * sign <= 0 for f in entries):
        return Attribution(
            TAG_HUMAN_INTERFERED, entries, (), None, "entry fills are not all on one side"
        )
    if net_after[last] != sign * entry_qty:
        return Attribution(
            TAG_HUMAN_INTERFERED,
            entries,
            (),
            None,
            f"other fills interleaved with the entry: account net after the last entry fill "
            f"is {net_after[last]:+d}, not {sign * entry_qty:+d}",
        )

    # Walk forward until flat; every fill must reduce exposure, never cross zero.
    exits: list[AccountFill] = []
    reason: str | None = None
    went_flat = False
    for i in range(last + 1, len(book)):
        f = book[i]
        if f.contract != contract:
            continue
        before, after = net_before[i], net_after[i]
        if f.signed_qty * sign > 0:
            reason = (
                f"exposure increased before the account went flat: "
                f"{f.describe(bot_order_ids=bot_ids)} (net {before:+d} → {after:+d})"
            )
            break
        if after * sign < 0:
            reason = (
                f"a fill crossed through zero: {f.describe(bot_order_ids=bot_ids)} "
                f"(net {before:+d} → {after:+d})"
            )
            break
        exits.append(f)
        if after == 0:
            went_flat = True
            break
    if reason is None and not went_flat:
        reason = (
            "the account never went flat on the contract within the supplied fills "
            f"(net {net_after.get(max(net_after), 0):+d} at the end of the book)"
        )
    if reason is not None:
        return Attribution(TAG_HUMAN_INTERFERED, entries, tuple(exits), None, reason)

    exit_qty = sum(f.qty for f in exits)
    assert exit_qty == entry_qty, (exit_qty, entry_qty)  # guaranteed by the walk
    entry_value = sum((f.price * f.qty for f in entries), Decimal(0))
    exit_value = sum((f.price * f.qty for f in exits), Decimal(0))
    gross = (exit_value - entry_value) if sign > 0 else (entry_value - exit_value)
    manual = [f for f in exits if f.order_id not in bot_ids]
    if manual:
        tag = TAG_ACCOUNT_FLAT
        reason = "closed when the account went flat; manual fill(s) took part: " + "; ".join(
            f.describe(bot_order_ids=bot_ids) for f in manual
        )
    else:
        tag = TAG_BOT_ONLY
        reason = "closed by the bot's own fills; no manual fill touched the trade"
    return Attribution(tag, entries, tuple(exits), gross, reason)


__all__ = [
    "ATTRIBUTION_TAGS",
    "BOT_CORRELATION_IDS",
    "HUMAN_INTERFERED_LABEL",
    "TAG_ACCOUNT_FLAT",
    "TAG_BOT_ONLY",
    "TAG_HUMAN_INTERFERED",
    "TAG_PAPER_SIM",
    "TAG_UNPRICEABLE",
    "AccountFill",
    "Attribution",
    "attribute",
]
