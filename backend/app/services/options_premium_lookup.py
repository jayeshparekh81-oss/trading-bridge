"""Pure option-premium lookup over the orderflow recorder's parquet layout.

Options Brick #4, slice ③-a. STANDALONE + FIXTURE-TESTED — nothing imports
this yet; wiring into entry/exit P&L, the real EC2/S3 data, and the
``expiry_date + entry_premium`` migration are slice ③-b (separately gated).

Recorder layout consumed (audited from ``feat/orderflow-r0-recorder`` @
``00fc4fe`` — writer.py / schema.py / main.py / scrip_master.py):

    {day_dir}/manifest.json
        {"date": "...", "instruments": [{"symbol": "NIFTY_CE_24800",
         "security_id": 49081, ..., "kind": "option", "expiry": "2026-07-16"}]}
    {day_dir}/{SYMBOL}_{security_id}.parquet
        TICK_SCHEMA rows — ``ts_recv_ns`` (epoch-ns UTC at receipt),
        ``ltp`` (THE premium), 5-level depth ``bid_price_1``/``ask_price_1``…

Policy (audit §4 — every ambiguity decided + documented here):

  * **Tick rule** — the LAST row at-or-before ``ts_ns`` (LTP semantics),
    bounded by staleness. Options are gap-exempt in the recorder (far strikes
    legitimately go quiet), so staleness is a fact of the data, not an error.
  * **Bounds** — ``ltp`` is trusted up to ``LTP_MAX_STALENESS_S`` (120 s: two
    minutes is a sane premium-estimate horizon for a paper-P&L join; far
    strikes trade sparsely but their premium drifts slowly). Past that, up to
    ``MID_MAX_STALENESS_S`` (600 s), the row's top-of-book mid
    (``(bid_price_1 + ask_price_1) / 2``) is used — quotes stay fresher than
    trades on quiet strikes. Past 600 s nothing is trustworthy → typed
    no-data. Both bounds are keyword-overridable; defaults documented here.
  * **Precedence** — fresh ``ltp`` wins; depth-mid ONLY as the staleness
    fallback (a fresh trade is truth; a quote is an estimate).
  * **Expiry match** — EXACT date only. The recorder arms ONE chain expiry
    per underlying per day, so a same-strike file can belong to a different
    contract — strike alone is ambiguous (audit's headline guard). No
    tolerance: a wrong-expiry premium is a wrong number.
  * **Timestamps** — ``ts_ns`` is epoch-NANOSECONDS UTC, matching
    ``ts_recv_ns``. The CALLER converts (``position.opened_at`` /
    ``signal.received_at`` → ns); this fn stays pure on integers.
  * **Missing data is a NORMAL, TYPED outcome — never an exception, never a
    silently-wrong number.** Reasons: ``absent_strike`` (no manifest entry,
    file missing, or file unreadable — all mean "this strike is not a usable
    data source today"; ±20-no-recenter makes this routine),
    ``expiry_mismatch``, ``core_only_day`` (disk-guard session recorded no
    options at all), ``stale_beyond_bound`` (incl. "no tick at-or-before ts"
    — infinite staleness), ``manifest_missing`` (absent/unreadable manifest —
    the whole day-dir is unusable). The caller decides the fallback (payload
    price + provenance flag) — not this fn.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger("app.services.options_premium_lookup")

#: Trust ``ltp`` up to this age (seconds). See module docstring for rationale.
LTP_MAX_STALENESS_S: float = 120.0
#: Past the ltp bound, accept top-of-book mid up to this age; beyond → no-data.
MID_MAX_STALENESS_S: float = 600.0


@dataclass(frozen=True)
class PremiumLookup:
    """Typed lookup result. ``premium is None`` ⇔ ``source == 'no_data'``."""

    premium: float | None
    source: str                    # "ltp" | "depth_mid" | "no_data"
    reason: str | None = None      # set ONLY when source == "no_data"
    ts_used_ns: int | None = None  # the tick actually used
    staleness_s: float | None = None


def _no_data(reason: str) -> PremiumLookup:
    return PremiumLookup(premium=None, source="no_data", reason=reason)


def _strike_label(strike: Any) -> str:
    """Mirror the recorder's label rule: int-rendered when integral
    (``label = int(strike) if float(strike).is_integer() else strike``)."""
    f = float(strike)
    return str(int(f)) if f.is_integer() else str(f)


def premium_at(
    day_dir: Path | str,
    *,
    underlying: str,
    strike: Any,
    opt_type: str,
    expiry: date,
    ts_ns: int,
    ltp_max_staleness_s: float = LTP_MAX_STALENESS_S,
    mid_max_staleness_s: float = MID_MAX_STALENESS_S,
) -> PremiumLookup:
    """Premium of ``{underlying} {strike} {opt_type}`` at ``ts_ns`` from one
    recorded day-dir. Pure; never raises for missing/unusable data."""
    day = Path(day_dir)
    symbol = f"{underlying.upper()}_{opt_type.upper()}_{_strike_label(strike)}"

    # 1. Manifest — the day's instrument index (symbol → security_id + expiry).
    try:
        manifest = json.loads((day / "manifest.json").read_text())
        instruments = list(manifest.get("instruments") or [])
    except Exception:  # broad by design — absent/corrupt manifest = unusable day
        return _no_data("manifest_missing")

    entry = next(
        (i for i in instruments if str(i.get("symbol", "")).upper() == symbol),
        None,
    )
    if entry is None:
        # Distinguish "this strike wasn't recorded" from "NO options were
        # recorded at all" (disk-guard CORE-ONLY session).
        any_option = any(i.get("kind") == "option" for i in instruments)
        return _no_data("absent_strike" if any_option else "core_only_day")

    # 2. Expiry guard — one armed chain expiry per day; strike alone is
    #    ambiguous. Exact-date match only.
    if str(entry.get("expiry", "")) != expiry.isoformat():
        return _no_data("expiry_mismatch")

    # 3. The instrument's daily parquet.
    path = day / f"{symbol}_{entry.get('security_id')}.parquet"
    try:
        import pyarrow.parquet as pq

        table = pq.read_table(
            path, columns=["ts_recv_ns", "ltp", "bid_price_1", "ask_price_1"]
        )
    except Exception:  # broad by design — missing/unreadable file, same outcome
        logger.info(
            "options_premium_lookup.file_unusable",
            symbol=symbol, path=str(path),
        )
        return _no_data("absent_strike")

    # 4. LAST row at-or-before ts_ns (rows are not assumed globally sorted —
    #    part-file consolidation preserves write order, not a guarantee).
    ts_col = table.column("ts_recv_ns").to_numpy(zero_copy_only=False)
    best_idx: int | None = None
    best_ts = -1
    for i, t in enumerate(ts_col):
        if t is not None and t <= ts_ns and t > best_ts:
            best_ts = int(t)
            best_idx = i
    if best_idx is None:
        return _no_data("stale_beyond_bound")  # nothing at-or-before ts

    age_s = (ts_ns - best_ts) / 1e9
    ltp = table.column("ltp")[best_idx].as_py()
    bid = table.column("bid_price_1")[best_idx].as_py()
    ask = table.column("ask_price_1")[best_idx].as_py()

    # 5. Premium selection with provenance.
    if age_s <= ltp_max_staleness_s and ltp is not None:
        return PremiumLookup(
            premium=float(ltp), source="ltp",
            ts_used_ns=best_ts, staleness_s=age_s,
        )
    if age_s <= mid_max_staleness_s and bid is not None and ask is not None:
        return PremiumLookup(
            premium=(float(bid) + float(ask)) / 2.0, source="depth_mid",
            ts_used_ns=best_ts, staleness_s=age_s,
        )
    return _no_data("stale_beyond_bound")


__all__ = [
    "LTP_MAX_STALENESS_S",
    "MID_MAX_STALENESS_S",
    "PremiumLookup",
    "premium_at",
]
