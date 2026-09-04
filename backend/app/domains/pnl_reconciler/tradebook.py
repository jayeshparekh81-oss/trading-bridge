"""Dhan trade-book rows → :class:`AccountFill` (futures only, options excluded).

The reconciler needs the WHOLE account's fills on a contract to apply the
founder's exit rule (see :mod:`attribution`). Dhan's trade book (``GET
/v2/trades/{from}/{to}/{page}``, and ``GET /v2/trades`` for today) is the
source; this module only parses rows that were already fetched and saved as
JSON lines — it performs no network or DB access itself.

Row shapes seen on 2026-09-04 (both are handled):

* history rows: ``customSymbol`` like ``"BSE SEP FUT"``, ``drvOptionType``
  ``"NA"`` for futures / ``"CALL"``/``"PUT"`` for options
* today rows: ``tradingSymbol`` like ``"BSE-Sep2026-FUT"`` / ``"BSE-Oct2026-3400-PE"``
  and ``drvOptionType`` may be ``"NA"`` even for an option — the symbol suffix
  is authoritative.

Rule 1 (founder, 2026-09-04): EVERY option leg is excluded — the bot trades
futures only. Equity-cash rows (``exchangeSegment`` not F&O) are excluded too.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.domains.pnl_reconciler.attribution import AccountFill

_OPTION_SUFFIXES = ("CE", "PE", "CALL", "PUT")


def _symbol(row: dict[str, Any]) -> str:
    return str(row.get("tradingSymbol") or row.get("customSymbol") or "").strip()


def is_futures_row(row: dict[str, Any]) -> bool:
    """True for an F&O FUTURES trade row; False for options / equity / junk."""
    sym = _symbol(row).upper()
    if not sym.endswith("FUT"):
        return False
    if sym.split("-")[-1] in _OPTION_SUFFIXES or sym.split()[-1] in _OPTION_SUFFIXES:
        return False
    opt = str(row.get("drvOptionType") or "NA").upper()
    if opt in ("CE", "PE", "CALL", "PUT"):
        return False
    seg = str(row.get("exchangeSegment") or "")
    return "FNO" in seg.upper() or seg == ""


def _decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def account_fill_from_row(row: dict[str, Any]) -> AccountFill | None:
    """Parse one Dhan trade row; ``None`` when it is not a priceable futures fill."""
    if not is_futures_row(row):
        return None
    price = _decimal(row.get("tradedPrice"))
    try:
        qty = int(row.get("tradedQuantity") or 0)
    except (TypeError, ValueError):
        return None
    order_id = str(row.get("orderId") or "").strip()
    # History rows stamp ``2026-09-03T12:45:13``; today's page stamps
    # ``2026-09-04 13:15:12``. Normalise to the ISO "T" form so the two shapes
    # sort chronologically together and a re-pulled row de-duplicates.
    ts = str(row.get("exchangeTime") or "").strip().replace(" ", "T")
    side = str(row.get("transactionType") or "").strip().upper()
    contract = str(row.get("securityId") or _symbol(row)).strip()
    if (
        price is None
        or price <= 0
        or qty <= 0
        or not order_id
        or not ts
        or side
        not in (
            "BUY",
            "SELL",
        )
    ):
        return None
    return AccountFill(
        contract=contract,
        order_id=order_id,
        side=side,
        qty=qty,
        price=price,
        ts=ts,
        trade_id=str(row.get("exchangeTradeId") or ""),
    )


def _is_real_trade_id(trade_id: str) -> bool:
    return trade_id not in ("", "0", "None")


def account_fills_from_rows(rows: Iterable[dict[str, Any]]) -> list[AccountFill]:
    """Parse + de-duplicate (an order can appear once per page pull) + sort.

    De-dup key: ``(orderId, exchangeTradeId)`` when the row carries a real
    trade id (today's page does; two genuine partial fills of one order —
    e.g. 23226090443106 as 200 + 200 — have different ids and both survive).
    History rows stamp ``exchangeTradeId = "0"`` for every fill, so for those
    the key is the row's own values ``(orderId, ts, side, qty, price)``: a row
    pulled twice (overlapping windows) collapses to one, but two genuine
    partials of one order that are byte-identical would collapse too. That
    is why the reconciler checks every BOT order's book quantity against the
    execution's ``filledQty`` before writing (``check_book_coverage``).

    NEVER combine a today-page file with a later history pull of the same
    day: the same fill would carry a real id in one and "0" in the other and
    be counted twice.
    """
    seen: set[tuple[str, ...]] = set()
    fills: list[AccountFill] = []
    for row in rows:
        fill = account_fill_from_row(row)
        if fill is None:
            continue
        key: tuple[str, ...]
        if _is_real_trade_id(fill.trade_id):
            key = ("id", fill.order_id, fill.trade_id)
        else:
            key = ("row", fill.order_id, fill.ts, fill.side, str(fill.qty), str(fill.price))
        if key in seen:
            continue
        seen.add(key)
        fills.append(fill)
    fills.sort(key=lambda f: (f.ts, f.order_id, f.trade_id))
    return fills


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith("{"):
                continue  # log lines from the pull script
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and obj.get("kind", "trade") == "trade":
                yield obj


def load_dhan_tradebook(*paths: str | Path) -> list[AccountFill]:
    """Load one or more JSONL trade-book files (any row shape above)."""
    rows: list[dict[str, Any]] = []
    for p in paths:
        rows.extend(_iter_jsonl(Path(p)))
    return account_fills_from_rows(rows)


__all__ = [
    "account_fill_from_row",
    "account_fills_from_rows",
    "is_futures_row",
    "load_dhan_tradebook",
]
