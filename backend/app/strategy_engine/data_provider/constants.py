"""Locked constants for the Dhan historical-data adapter.

Single tunable knobs for endpoint URLs, rate-limit handling, cache
behaviour, and the bundled symbol resolution map. Keep this module
dependency-free.
"""

from __future__ import annotations

from typing import Final

# ─── Endpoints ─────────────────────────────────────────────────────────

DHAN_API_BASE_URL: Final[str] = "https://api.dhan.co/v2"
"""Base URL for Dhan API v2 (matches ``settings.dhan_api_base_url``
default in :mod:`app.core.config`). Tests override via dependency
injection rather than mutating this constant."""

DHAN_HISTORICAL_DAILY_PATH: Final[str] = "/charts/historical"
DHAN_HISTORICAL_INTRADAY_PATH: Final[str] = "/charts/intraday"

# ─── Rate-limit + retry ────────────────────────────────────────────────

DHAN_RATE_LIMIT_PER_SECOND: Final[int] = 5
"""Per the Dhan support article — data APIs allow 5 requests/sec.
Hitting it produces a 429 response, optionally with a ``Retry-After``
header."""

DHAN_RATE_LIMIT_PER_DAY: Final[int] = 100_000
"""Headline daily cap. Documented for context; the adapter does not
enforce a daily quota."""

MAX_RETRY_ATTEMPTS: Final[int] = 3
INITIAL_BACKOFF_SECONDS: Final[float] = 2.0
"""On 429 / 5xx the fetcher waits ``INITIAL_BACKOFF_SECONDS *
(2 ** attempt)`` before retrying, capped at :data:`MAX_RETRY_ATTEMPTS`
total attempts. When Dhan returns a ``Retry-After`` header it is used
directly instead of the exponential schedule."""

# ─── Cache ─────────────────────────────────────────────────────────────

CACHE_DIR_NAME: Final[str] = "tradetri_dhan_cache"
"""Cache directory name — created under ``/tmp`` when writable,
otherwise under ``~/.cache``. Phase B only cares about pickle-safe
JSON, so the cache is a flat directory of ``*.json`` files."""

CACHE_TTL_RECENT_HOURS: Final[int] = 1
"""TTL for data whose ``to_date`` is within the last 7 days. Recent
bars are still in flux (last bar of an active session can change), so
a short TTL prevents stale reads."""

CACHE_TTL_HISTORICAL_HOURS: Final[int] = 24
"""TTL for data whose ``to_date`` is older than 7 days. Older bars are
immutable, so a 24-hour TTL keeps cache pressure low while letting a
data fix on the Dhan side propagate within a day."""

RECENT_DATA_THRESHOLD_DAYS: Final[int] = 7
"""Cut-off used to pick between :data:`CACHE_TTL_RECENT_HOURS` and
:data:`CACHE_TTL_HISTORICAL_HOURS`."""

# ─── Constraint floors ────────────────────────────────────────────────

INTRADAY_MAX_DAYS_PER_REQUEST: Final[int] = 90
"""Dhan refuses intraday requests spanning more than 90 days. Phase B
rejects them client-side rather than waiting for the server's 4xx."""

QUALITY_SCORE_WARN_THRESHOLD: Final[float] = 40.0
"""Below this Phase 11 quality score the fetcher logs a warning. The
data is still returned — the caller decides whether to proceed."""

# ─── Timeframe map (public string → endpoint + interval) ──────────────

# Phase B exposes ``Literal["1m","5m","15m","1h","1d"]``. Dhan's
# intraday endpoint accepts the integer minute counts ``1, 5, 15, 25,
# 60``; we omit ``25m`` from the public surface.
TIMEFRAME_TO_INTERVAL_MINUTES: Final[dict[str, int]] = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "1h": 60,
}

DAILY_TIMEFRAME: Final[str] = "1d"

# ─── Symbol resolution ────────────────────────────────────────────────

# Alias map applied *before* :data:`KNOWN_SYMBOLS` lookup. Whitespace
# is collapsed and the result upper-cased before matching.
#
# Step 1/5 additions cover the new F&O-tradeable BSE indices and
# friendly variants of MIDCPNIFTY (a Dhan-canonical key that reads as
# initialism — users will type "Nifty Midcap Select" naturally). The
# normalise_symbol() fix in fetcher.py preserves internal whitespace
# on alias miss; no current KNOWN_SYMBOLS key uses internal spaces
# (NIFTY NEXT 50 was the one such key, dropped — see below), but the
# policy stays in place so future spaced canonical Dhan trading-
# symbols (or alias targets) resolve correctly without code churn.
SYMBOL_ALIASES: Final[dict[str, str]] = {
    # ── pre-existing ──────────────────────────────────────────────────
    "NIFTY 50": "NIFTY",
    "NIFTY50": "NIFTY",
    "BANK NIFTY": "BANKNIFTY",
    "BANKNIFTY 50": "BANKNIFTY",
    "FIN NIFTY": "FINNIFTY",
    # ── Step 1/5 v2 (new) ─────────────────────────────────────────────
    "NIFTY MIDCAP SELECT": "MIDCPNIFTY",
    "MIDCAP NIFTY": "MIDCPNIFTY",
    "BSE BANKEX": "BANKEX",
    "BSE SENSEX 50": "SNSX50",
    "SENSEX 50": "SNSX50",
    # ── Equity-name aliases (Step 1 follow-up) ───────────────────────
    # Free-text typers entering full spaced names need these. The
    # picker dropdown emits the canonical joined form already and is
    # unaffected. TCS and ITC need no alias — already canonical.
    "HDFC BANK": "HDFCBANK",
    "ICICI BANK": "ICICIBANK",
    "AXIS BANK": "AXISBANK",
    "RELIANCE INDUSTRIES": "RELIANCE",
    "INFOSYS": "INFY",
}


class _SymbolMeta:
    """Internal record. Bundled so a future edit can extend the map
    without drifting the surface schema."""

    __slots__ = ("exchange_segment", "instrument", "security_id")

    def __init__(self, security_id: str, exchange_segment: str, instrument: str) -> None:
        self.security_id = security_id
        self.exchange_segment = exchange_segment
        self.instrument = instrument


# All security_ids and the exact ``SEM_TRADING_SYMBOL`` strings below
# were verified against the live Dhan scrip-master CSV
# (``https://images.dhan.co/api-data/api-scrip-master.csv``).
#
# Structure (Step 3):
#   * :data:`INDEX_SYMBOLS`       — 7 F&O-tradeable indices (NSE + BSE).
#   * :data:`FNO_STOCK_SYMBOLS`   — 209 F&O underlyings, alphabetical;
#                                   includes the 7 large-caps that
#                                   were in this dict pre-Step-3
#                                   (RELIANCE, TCS, INFY, HDFCBANK,
#                                   ICICIBANK, AXISBANK, ITC), since
#                                   they are themselves F&O-tradeable.
#   * :data:`CASH_EQUITY_SYMBOLS` — reserved for cash-only equities
#                                   (non-F&O). Empty today; populated
#                                   in Steps 4-5 when broader Nifty 100
#                                   / Midcap 150 / Smallcap 250
#                                   additions land.
#
# :data:`KNOWN_SYMBOLS` is the merged superset, the canonical public
# surface the rest of the code uses. Merge order: INDEX → CASH_EQUITY
# → FNO_STOCK. Python's last-writer-wins dict-spread semantics mean
# FNO_STOCK entries override CASH_EQUITY entries on key collision;
# today both contain byte-identical values for the 7 historical
# large-caps, so the order is functionally a tie and chosen for
# conceptual clarity (FNO is the broader, authoritative source).
#
# Regeneration (when Dhan updates its F&O list):
#   curl -s -o /tmp/dhan_sm.csv \
#     https://images.dhan.co/api-data/api-scrip-master.csv
#   python /tmp/gen_fno.py > /tmp/fno_block.txt
# (gen_fno.py: filter FUTSTK rows, drop NSETEST, strip
#  ``-{Mmm}{YYYY}-FUT`` suffix, dedup, alphabetise, cross-reference
#  each underlying to its matching NSE_EQ EQUITY row for security_id.
#  Source under version control alongside the PR commit body.)
#
# Step 1/5 v2 equity additions (HDFCBANK / ICICIBANK / AXISBANK / ITC)
# fixed a pre-existing bug where the frontend picker exposed these
# four for a Dhan-historical backtest but the backend had no entries
# — :func:`_resolve_symbol` raised ``ValueError`` (no fallback path
# exists) and the uncaught exception surfaced as a generic 500.
INDEX_SYMBOLS: Final[dict[str, _SymbolMeta]] = {
    # NSE indices ─ Dhan's IDX_I segment, INDEX instrument type.
    "NIFTY": _SymbolMeta("13", "IDX_I", "INDEX"),
    "BANKNIFTY": _SymbolMeta("25", "IDX_I", "INDEX"),
    "FINNIFTY": _SymbolMeta("27", "IDX_I", "INDEX"),
    "MIDCPNIFTY": _SymbolMeta("442", "IDX_I", "INDEX"),
    # BSE indices ─ same IDX_I segment per Dhan docs (one segment
    # value covers all indices regardless of exchange). Runtime-
    # validated in Step 1: all three fetch real daily bars cleanly.
    "SENSEX": _SymbolMeta("51", "IDX_I", "INDEX"),
    "BANKEX": _SymbolMeta("69", "IDX_I", "INDEX"),
    "SNSX50": _SymbolMeta("83", "IDX_I", "INDEX"),
}
# Nifty Next 50 (sec_id=38, IDX_I, INDEX) is deliberately absent —
# Dhan rejects it with HTTP 400 on the historical-data endpoint
# despite the scrip-master listing it. See
# ``docs/POST_LAUNCH_TECH_DEBT.md`` for the investigation trail
# (four alternate triples for sec_id=38 also failed; likely plan-
# gated or an undocumented historical-data identifier).


FNO_STOCK_SYMBOLS: Final[dict[str, _SymbolMeta]] = {
    # 209 entries, alphabetical. Cross-verified May 11 2026 against
    # NSE's live F&O eligibility API (zero drift in either direction).
    "360ONE":     _SymbolMeta("13061", "NSE_EQ", "EQUITY"),
    "ABB":        _SymbolMeta("13", "NSE_EQ", "EQUITY"),
    "ABCAPITAL":  _SymbolMeta("21614", "NSE_EQ", "EQUITY"),
    "ADANIENSOL": _SymbolMeta("10217", "NSE_EQ", "EQUITY"),
    "ADANIENT":   _SymbolMeta("25", "NSE_EQ", "EQUITY"),
    "ADANIGREEN": _SymbolMeta("3563", "NSE_EQ", "EQUITY"),
    "ADANIPORTS": _SymbolMeta("15083", "NSE_EQ", "EQUITY"),
    "ADANIPOWER": _SymbolMeta("17388", "NSE_EQ", "EQUITY"),
    "ALKEM":      _SymbolMeta("11703", "NSE_EQ", "EQUITY"),
    "AMBER":      _SymbolMeta("1185", "NSE_EQ", "EQUITY"),
    "AMBUJACEM":  _SymbolMeta("1270", "NSE_EQ", "EQUITY"),
    "ANGELONE":   _SymbolMeta("324", "NSE_EQ", "EQUITY"),
    "APLAPOLLO":  _SymbolMeta("25780", "NSE_EQ", "EQUITY"),
    "APOLLOHOSP": _SymbolMeta("157", "NSE_EQ", "EQUITY"),
    "ASHOKLEY":   _SymbolMeta("212", "NSE_EQ", "EQUITY"),
    "ASIANPAINT": _SymbolMeta("236", "NSE_EQ", "EQUITY"),
    "ASTRAL":     _SymbolMeta("14418", "NSE_EQ", "EQUITY"),
    "AUBANK":     _SymbolMeta("21238", "NSE_EQ", "EQUITY"),
    "AUROPHARMA": _SymbolMeta("275", "NSE_EQ", "EQUITY"),
    "AXISBANK":   _SymbolMeta("5900", "NSE_EQ", "EQUITY"),
    "BAJAJ-AUTO": _SymbolMeta("16669", "NSE_EQ", "EQUITY"),
    "BAJAJFINSV": _SymbolMeta("16675", "NSE_EQ", "EQUITY"),
    "BAJAJHLDNG": _SymbolMeta("305", "NSE_EQ", "EQUITY"),
    "BAJFINANCE": _SymbolMeta("317", "NSE_EQ", "EQUITY"),
    "BANDHANBNK": _SymbolMeta("2263", "NSE_EQ", "EQUITY"),
    "BANKBARODA": _SymbolMeta("4668", "NSE_EQ", "EQUITY"),
    "BANKINDIA":  _SymbolMeta("4745", "NSE_EQ", "EQUITY"),
    "BDL":        _SymbolMeta("2144", "NSE_EQ", "EQUITY"),
    "BEL":        _SymbolMeta("383", "NSE_EQ", "EQUITY"),
    "BHARATFORG": _SymbolMeta("422", "NSE_EQ", "EQUITY"),
    "BHARTIARTL": _SymbolMeta("10604", "NSE_EQ", "EQUITY"),
    "BHEL":       _SymbolMeta("438", "NSE_EQ", "EQUITY"),
    "BIOCON":     _SymbolMeta("11373", "NSE_EQ", "EQUITY"),
    "BLUESTARCO": _SymbolMeta("8311", "NSE_EQ", "EQUITY"),
    "BOSCHLTD":   _SymbolMeta("2181", "NSE_EQ", "EQUITY"),
    "BPCL":       _SymbolMeta("526", "NSE_EQ", "EQUITY"),
    "BRITANNIA":  _SymbolMeta("547", "NSE_EQ", "EQUITY"),
    "BSE":        _SymbolMeta("19585", "NSE_EQ", "EQUITY"),
    "CAMS":       _SymbolMeta("342", "NSE_EQ", "EQUITY"),
    "CANBK":      _SymbolMeta("10794", "NSE_EQ", "EQUITY"),
    "CDSL":       _SymbolMeta("21174", "NSE_EQ", "EQUITY"),
    "CGPOWER":    _SymbolMeta("760", "NSE_EQ", "EQUITY"),
    "CHOLAFIN":   _SymbolMeta("19257", "NSE_EQ", "EQUITY"),
    "CIPLA":      _SymbolMeta("694", "NSE_EQ", "EQUITY"),
    "COALINDIA":  _SymbolMeta("20374", "NSE_EQ", "EQUITY"),
    "COCHINSHIP": _SymbolMeta("21508", "NSE_EQ", "EQUITY"),
    "COFORGE":    _SymbolMeta("11543", "NSE_EQ", "EQUITY"),
    "COLPAL":     _SymbolMeta("15141", "NSE_EQ", "EQUITY"),
    "CONCOR":     _SymbolMeta("4749", "NSE_EQ", "EQUITY"),
    "CROMPTON":   _SymbolMeta("17094", "NSE_EQ", "EQUITY"),
    "CUMMINSIND": _SymbolMeta("1901", "NSE_EQ", "EQUITY"),
    "DABUR":      _SymbolMeta("772", "NSE_EQ", "EQUITY"),
    "DALBHARAT":  _SymbolMeta("8075", "NSE_EQ", "EQUITY"),
    "DELHIVERY":  _SymbolMeta("9599", "NSE_EQ", "EQUITY"),
    "DIVISLAB":   _SymbolMeta("10940", "NSE_EQ", "EQUITY"),
    "DIXON":      _SymbolMeta("21690", "NSE_EQ", "EQUITY"),
    "DLF":        _SymbolMeta("14732", "NSE_EQ", "EQUITY"),
    "DMART":      _SymbolMeta("19913", "NSE_EQ", "EQUITY"),
    "DRREDDY":    _SymbolMeta("881", "NSE_EQ", "EQUITY"),
    "EICHERMOT":  _SymbolMeta("910", "NSE_EQ", "EQUITY"),
    "ETERNAL":    _SymbolMeta("5097", "NSE_EQ", "EQUITY"),
    "EXIDEIND":   _SymbolMeta("676", "NSE_EQ", "EQUITY"),
    "FEDERALBNK": _SymbolMeta("1023", "NSE_EQ", "EQUITY"),
    "FORCEMOT":   _SymbolMeta("11573", "NSE_EQ", "EQUITY"),
    "FORTIS":     _SymbolMeta("14592", "NSE_EQ", "EQUITY"),
    "GAIL":       _SymbolMeta("4717", "NSE_EQ", "EQUITY"),
    "GLENMARK":   _SymbolMeta("7406", "NSE_EQ", "EQUITY"),
    "GMRAIRPORT": _SymbolMeta("13528", "NSE_EQ", "EQUITY"),
    "GODFRYPHLP": _SymbolMeta("1181", "NSE_EQ", "EQUITY"),
    "GODREJCP":   _SymbolMeta("10099", "NSE_EQ", "EQUITY"),
    "GODREJPROP": _SymbolMeta("17875", "NSE_EQ", "EQUITY"),
    "GRASIM":     _SymbolMeta("1232", "NSE_EQ", "EQUITY"),
    "HAL":        _SymbolMeta("2303", "NSE_EQ", "EQUITY"),
    "HAVELLS":    _SymbolMeta("9819", "NSE_EQ", "EQUITY"),
    "HCLTECH":    _SymbolMeta("7229", "NSE_EQ", "EQUITY"),
    "HDFCAMC":    _SymbolMeta("4244", "NSE_EQ", "EQUITY"),
    "HDFCBANK":   _SymbolMeta("1333", "NSE_EQ", "EQUITY"),
    "HDFCLIFE":   _SymbolMeta("467", "NSE_EQ", "EQUITY"),
    "HEROMOTOCO": _SymbolMeta("1348", "NSE_EQ", "EQUITY"),
    "HINDALCO":   _SymbolMeta("1363", "NSE_EQ", "EQUITY"),
    "HINDPETRO":  _SymbolMeta("1406", "NSE_EQ", "EQUITY"),
    "HINDUNILVR": _SymbolMeta("1394", "NSE_EQ", "EQUITY"),
    "HINDZINC":   _SymbolMeta("1424", "NSE_EQ", "EQUITY"),
    "HYUNDAI":    _SymbolMeta("25844", "NSE_EQ", "EQUITY"),
    "ICICIBANK":  _SymbolMeta("4963", "NSE_EQ", "EQUITY"),
    "ICICIGI":    _SymbolMeta("21770", "NSE_EQ", "EQUITY"),
    "ICICIPRULI": _SymbolMeta("18652", "NSE_EQ", "EQUITY"),
    "IDEA":       _SymbolMeta("14366", "NSE_EQ", "EQUITY"),
    "IDFCFIRSTB": _SymbolMeta("11184", "NSE_EQ", "EQUITY"),
    "IEX":        _SymbolMeta("220", "NSE_EQ", "EQUITY"),
    "INDHOTEL":   _SymbolMeta("1512", "NSE_EQ", "EQUITY"),
    "INDIANB":    _SymbolMeta("14309", "NSE_EQ", "EQUITY"),
    "INDIGO":     _SymbolMeta("11195", "NSE_EQ", "EQUITY"),
    "INDUSINDBK": _SymbolMeta("5258", "NSE_EQ", "EQUITY"),
    "INDUSTOWER": _SymbolMeta("29135", "NSE_EQ", "EQUITY"),
    "INFY":       _SymbolMeta("1594", "NSE_EQ", "EQUITY"),
    "INOXWIND":   _SymbolMeta("7852", "NSE_EQ", "EQUITY"),
    "IOC":        _SymbolMeta("1624", "NSE_EQ", "EQUITY"),
    "IREDA":      _SymbolMeta("20261", "NSE_EQ", "EQUITY"),
    "IRFC":       _SymbolMeta("2029", "NSE_EQ", "EQUITY"),
    "ITC":        _SymbolMeta("1660", "NSE_EQ", "EQUITY"),
    "JINDALSTEL": _SymbolMeta("6733", "NSE_EQ", "EQUITY"),
    "JIOFIN":     _SymbolMeta("18143", "NSE_EQ", "EQUITY"),
    "JSWENERGY":  _SymbolMeta("17869", "NSE_EQ", "EQUITY"),
    "JSWSTEEL":   _SymbolMeta("11723", "NSE_EQ", "EQUITY"),
    "JUBLFOOD":   _SymbolMeta("18096", "NSE_EQ", "EQUITY"),
    "KALYANKJIL": _SymbolMeta("2955", "NSE_EQ", "EQUITY"),
    "KAYNES":     _SymbolMeta("12092", "NSE_EQ", "EQUITY"),
    "KEI":        _SymbolMeta("13310", "NSE_EQ", "EQUITY"),
    "KFINTECH":   _SymbolMeta("13359", "NSE_EQ", "EQUITY"),
    "KOTAKBANK":  _SymbolMeta("1922", "NSE_EQ", "EQUITY"),
    "KPITTECH":   _SymbolMeta("9683", "NSE_EQ", "EQUITY"),
    "LAURUSLABS": _SymbolMeta("19234", "NSE_EQ", "EQUITY"),
    "LICHSGFIN":  _SymbolMeta("1997", "NSE_EQ", "EQUITY"),
    "LICI":       _SymbolMeta("9480", "NSE_EQ", "EQUITY"),
    "LODHA":      _SymbolMeta("3220", "NSE_EQ", "EQUITY"),
    "LT":         _SymbolMeta("11483", "NSE_EQ", "EQUITY"),
    "LTF":        _SymbolMeta("24948", "NSE_EQ", "EQUITY"),
    "LTM":        _SymbolMeta("17818", "NSE_EQ", "EQUITY"),
    "LUPIN":      _SymbolMeta("10440", "NSE_EQ", "EQUITY"),
    "M&M":        _SymbolMeta("2031", "NSE_EQ", "EQUITY"),
    "MANAPPURAM": _SymbolMeta("19061", "NSE_EQ", "EQUITY"),
    "MANKIND":    _SymbolMeta("15380", "NSE_EQ", "EQUITY"),
    "MARICO":     _SymbolMeta("4067", "NSE_EQ", "EQUITY"),
    "MARUTI":     _SymbolMeta("10999", "NSE_EQ", "EQUITY"),
    "MAXHEALTH":  _SymbolMeta("22377", "NSE_EQ", "EQUITY"),
    "MAZDOCK":    _SymbolMeta("509", "NSE_EQ", "EQUITY"),
    "MCX":        _SymbolMeta("31181", "NSE_EQ", "EQUITY"),
    "MFSL":       _SymbolMeta("2142", "NSE_EQ", "EQUITY"),
    "MOTHERSON":  _SymbolMeta("25510", "NSE_EQ", "EQUITY"),
    "MOTILALOFS": _SymbolMeta("14947", "NSE_EQ", "EQUITY"),
    "MPHASIS":    _SymbolMeta("4503", "NSE_EQ", "EQUITY"),
    "MUTHOOTFIN": _SymbolMeta("23650", "NSE_EQ", "EQUITY"),
    "NAM-INDIA":  _SymbolMeta("357", "NSE_EQ", "EQUITY"),
    "NATIONALUM": _SymbolMeta("6364", "NSE_EQ", "EQUITY"),
    "NAUKRI":     _SymbolMeta("13751", "NSE_EQ", "EQUITY"),
    "NBCC":       _SymbolMeta("31415", "NSE_EQ", "EQUITY"),
    "NESTLEIND":  _SymbolMeta("17963", "NSE_EQ", "EQUITY"),
    "NHPC":       _SymbolMeta("17400", "NSE_EQ", "EQUITY"),
    "NMDC":       _SymbolMeta("15332", "NSE_EQ", "EQUITY"),
    "NTPC":       _SymbolMeta("11630", "NSE_EQ", "EQUITY"),
    "NUVAMA":     _SymbolMeta("18721", "NSE_EQ", "EQUITY"),
    "NYKAA":      _SymbolMeta("6545", "NSE_EQ", "EQUITY"),
    "OBEROIRLTY": _SymbolMeta("20242", "NSE_EQ", "EQUITY"),
    "OFSS":       _SymbolMeta("10738", "NSE_EQ", "EQUITY"),
    "OIL":        _SymbolMeta("17438", "NSE_EQ", "EQUITY"),
    "ONGC":       _SymbolMeta("2475", "NSE_EQ", "EQUITY"),
    "PAGEIND":    _SymbolMeta("14413", "NSE_EQ", "EQUITY"),
    "PATANJALI":  _SymbolMeta("17029", "NSE_EQ", "EQUITY"),
    "PAYTM":      _SymbolMeta("6705", "NSE_EQ", "EQUITY"),
    "PERSISTENT": _SymbolMeta("18365", "NSE_EQ", "EQUITY"),
    "PETRONET":   _SymbolMeta("11351", "NSE_EQ", "EQUITY"),
    "PFC":        _SymbolMeta("14299", "NSE_EQ", "EQUITY"),
    "PGEL":       _SymbolMeta("25358", "NSE_EQ", "EQUITY"),
    "PHOENIXLTD": _SymbolMeta("14552", "NSE_EQ", "EQUITY"),
    "PIDILITIND": _SymbolMeta("2664", "NSE_EQ", "EQUITY"),
    "PIIND":      _SymbolMeta("24184", "NSE_EQ", "EQUITY"),
    "PNB":        _SymbolMeta("10666", "NSE_EQ", "EQUITY"),
    "PNBHOUSING": _SymbolMeta("18908", "NSE_EQ", "EQUITY"),
    "POLICYBZR":  _SymbolMeta("6656", "NSE_EQ", "EQUITY"),
    "POLYCAB":    _SymbolMeta("9590", "NSE_EQ", "EQUITY"),
    "POWERGRID":  _SymbolMeta("14977", "NSE_EQ", "EQUITY"),
    "POWERINDIA": _SymbolMeta("18457", "NSE_EQ", "EQUITY"),
    "PREMIERENE": _SymbolMeta("25049", "NSE_EQ", "EQUITY"),
    "PRESTIGE":   _SymbolMeta("20302", "NSE_EQ", "EQUITY"),
    "RBLBANK":    _SymbolMeta("18391", "NSE_EQ", "EQUITY"),
    "RECLTD":     _SymbolMeta("15355", "NSE_EQ", "EQUITY"),
    "RELIANCE":   _SymbolMeta("2885", "NSE_EQ", "EQUITY"),
    "RVNL":       _SymbolMeta("9552", "NSE_EQ", "EQUITY"),
    "SAIL":       _SymbolMeta("2963", "NSE_EQ", "EQUITY"),
    "SAMMAANCAP": _SymbolMeta("30125", "NSE_EQ", "EQUITY"),
    "SBICARD":    _SymbolMeta("17971", "NSE_EQ", "EQUITY"),
    "SBILIFE":    _SymbolMeta("21808", "NSE_EQ", "EQUITY"),
    "SBIN":       _SymbolMeta("3045", "NSE_EQ", "EQUITY"),
    "SHREECEM":   _SymbolMeta("3103", "NSE_EQ", "EQUITY"),
    "SHRIRAMFIN": _SymbolMeta("4306", "NSE_EQ", "EQUITY"),
    "SIEMENS":    _SymbolMeta("3150", "NSE_EQ", "EQUITY"),
    "SOLARINDS":  _SymbolMeta("13332", "NSE_EQ", "EQUITY"),
    "SONACOMS":   _SymbolMeta("4684", "NSE_EQ", "EQUITY"),
    "SRF":        _SymbolMeta("3273", "NSE_EQ", "EQUITY"),
    "SUNPHARMA":  _SymbolMeta("3351", "NSE_EQ", "EQUITY"),
    "SUPREMEIND": _SymbolMeta("3363", "NSE_EQ", "EQUITY"),
    "SUZLON":     _SymbolMeta("12018", "NSE_EQ", "EQUITY"),
    "SWIGGY":     _SymbolMeta("27066", "NSE_EQ", "EQUITY"),
    "TATACONSUM": _SymbolMeta("3432", "NSE_EQ", "EQUITY"),
    "TATAELXSI":  _SymbolMeta("3411", "NSE_EQ", "EQUITY"),
    "TATAPOWER":  _SymbolMeta("3426", "NSE_EQ", "EQUITY"),
    "TATASTEEL":  _SymbolMeta("3499", "NSE_EQ", "EQUITY"),
    "TCS":        _SymbolMeta("11536", "NSE_EQ", "EQUITY"),
    "TECHM":      _SymbolMeta("13538", "NSE_EQ", "EQUITY"),
    "TIINDIA":    _SymbolMeta("312", "NSE_EQ", "EQUITY"),
    "TITAN":      _SymbolMeta("3506", "NSE_EQ", "EQUITY"),
    "TMPV":       _SymbolMeta("3456", "NSE_EQ", "EQUITY"),
    "TORNTPHARM": _SymbolMeta("3518", "NSE_EQ", "EQUITY"),
    "TRENT":      _SymbolMeta("1964", "NSE_EQ", "EQUITY"),
    "TVSMOTOR":   _SymbolMeta("8479", "NSE_EQ", "EQUITY"),
    "ULTRACEMCO": _SymbolMeta("11532", "NSE_EQ", "EQUITY"),
    "UNIONBANK":  _SymbolMeta("10753", "NSE_EQ", "EQUITY"),
    "UNITDSPR":   _SymbolMeta("10447", "NSE_EQ", "EQUITY"),
    "UNOMINDA":   _SymbolMeta("14154", "NSE_EQ", "EQUITY"),
    "UPL":        _SymbolMeta("11287", "NSE_EQ", "EQUITY"),
    "VBL":        _SymbolMeta("18921", "NSE_EQ", "EQUITY"),
    "VEDL":       _SymbolMeta("3063", "NSE_EQ", "EQUITY"),
    "VMM":        _SymbolMeta("27969", "NSE_EQ", "EQUITY"),
    "VOLTAS":     _SymbolMeta("3718", "NSE_EQ", "EQUITY"),
    "WAAREEENER": _SymbolMeta("25907", "NSE_EQ", "EQUITY"),
    "WIPRO":      _SymbolMeta("3787", "NSE_EQ", "EQUITY"),
    "YESBANK":    _SymbolMeta("11915", "NSE_EQ", "EQUITY"),
    "ZYDUSLIFE":  _SymbolMeta("7929", "NSE_EQ", "EQUITY"),
}


# Cash equity sub-dicts (Steps 4-5). The 3 NSE constituent lists are
# disjoint by index methodology — each stock sits in exactly one of
# the three buckets — so there are no merge-order conflicts within
# CASH_EQUITY_SYMBOLS itself. Net-new totals (May 11 2026):
#   * LARGE_CAP    3  (Nifty 100 minus F&O overlap of 97/100)
#   * MIDCAP      58  (Nifty Midcap 150 minus F&O overlap of 92/150)
#   * SMALLCAP   230  (Nifty Smallcap 250 minus F&O overlap of 20/250)
#   * Total      291
#
# Sub-dict boundaries match NSE's published index constituents at PR
# time. Future re-classifications (e.g., an existing smallcap promoted
# to midcap on the next NSE review) will require regeneration via
# /tmp/ph2_gen.py — the same script used at Step 4-5 PR time.
LARGE_CAP_CASH_EQUITY_SYMBOLS: Final[dict[str, _SymbolMeta]] = {
    "ENRIN":   _SymbolMeta("756871", "NSE_EQ", "EQUITY"),
    "TATACAP": _SymbolMeta("759265", "NSE_EQ", "EQUITY"),
    "TMCV":    _SymbolMeta("759782", "NSE_EQ", "EQUITY"),
}


MIDCAP_CASH_EQUITY_SYMBOLS: Final[dict[str, _SymbolMeta]] = {
    "3MINDIA":    _SymbolMeta("474", "NSE_EQ", "EQUITY"),
    "ABBOTINDIA": _SymbolMeta("17903", "NSE_EQ", "EQUITY"),
    "ACC":        _SymbolMeta("22", "NSE_EQ", "EQUITY"),
    "AIAENG":     _SymbolMeta("13086", "NSE_EQ", "EQUITY"),
    "AIIL":       _SymbolMeta("23553", "NSE_EQ", "EQUITY"),
    "AJANTPHARM": _SymbolMeta("8124", "NSE_EQ", "EQUITY"),
    "ANTHEM":     _SymbolMeta("757885", "NSE_EQ", "EQUITY"),
    "APARINDS":   _SymbolMeta("11491", "NSE_EQ", "EQUITY"),
    "APOLLOTYRE": _SymbolMeta("163", "NSE_EQ", "EQUITY"),
    "ATGL":       _SymbolMeta("6066", "NSE_EQ", "EQUITY"),
    "AWL":        _SymbolMeta("8110", "NSE_EQ", "EQUITY"),
    "BAJAJHFL":   _SymbolMeta("25270", "NSE_EQ", "EQUITY"),
    "BALKRISIND": _SymbolMeta("335", "NSE_EQ", "EQUITY"),
    "BERGEPAINT": _SymbolMeta("404", "NSE_EQ", "EQUITY"),
    "BHARTIHEXA": _SymbolMeta("23489", "NSE_EQ", "EQUITY"),
    "COROMANDEL": _SymbolMeta("739", "NSE_EQ", "EQUITY"),
    "CRISIL":     _SymbolMeta("757", "NSE_EQ", "EQUITY"),
    "ENDURANCE":  _SymbolMeta("18822", "NSE_EQ", "EQUITY"),
    "ESCORTS":    _SymbolMeta("958", "NSE_EQ", "EQUITY"),
    "FLUOROCHEM": _SymbolMeta("13750", "NSE_EQ", "EQUITY"),
    "GICRE":      _SymbolMeta("277", "NSE_EQ", "EQUITY"),
    "GLAXO":      _SymbolMeta("1153", "NSE_EQ", "EQUITY"),
    "GODREJIND":  _SymbolMeta("10925", "NSE_EQ", "EQUITY"),
    "GROWW":      _SymbolMeta("759806", "NSE_EQ", "EQUITY"),
    "GVT&D":      _SymbolMeta("16783", "NSE_EQ", "EQUITY"),
    "HDBFS":      _SymbolMeta("757772", "NSE_EQ", "EQUITY"),
    "HEXT":       _SymbolMeta("29666", "NSE_EQ", "EQUITY"),
    "HONAUT":     _SymbolMeta("3417", "NSE_EQ", "EQUITY"),
    "HUDCO":      _SymbolMeta("20825", "NSE_EQ", "EQUITY"),
    "ICICIAMC":   _SymbolMeta("760407", "NSE_EQ", "EQUITY"),
    "IPCALAB":    _SymbolMeta("1633", "NSE_EQ", "EQUITY"),
    "IRCTC":      _SymbolMeta("13611", "NSE_EQ", "EQUITY"),
    "ITCHOTELS":  _SymbolMeta("29251", "NSE_EQ", "EQUITY"),
    "JKCEMENT":   _SymbolMeta("13270", "NSE_EQ", "EQUITY"),
    "JSL":        _SymbolMeta("11236", "NSE_EQ", "EQUITY"),
    "JSWINFRA":   _SymbolMeta("19020", "NSE_EQ", "EQUITY"),
    "KPRMILL":    _SymbolMeta("14912", "NSE_EQ", "EQUITY"),
    "LENSKART":   _SymbolMeta("759605", "NSE_EQ", "EQUITY"),
    "LGEINDIA":   _SymbolMeta("760213", "NSE_EQ", "EQUITY"),
    "LINDEINDIA": _SymbolMeta("1627", "NSE_EQ", "EQUITY"),
    "LLOYDSME":   _SymbolMeta("17313", "NSE_EQ", "EQUITY"),
    "LTTS":       _SymbolMeta("18564", "NSE_EQ", "EQUITY"),
    "M&MFIN":     _SymbolMeta("13285", "NSE_EQ", "EQUITY"),
    "MAHABANK":   _SymbolMeta("11377", "NSE_EQ", "EQUITY"),
    "MEDANTA":    _SymbolMeta("11956", "NSE_EQ", "EQUITY"),
    "MRF":        _SymbolMeta("2277", "NSE_EQ", "EQUITY"),
    "NIACL":      _SymbolMeta("399", "NSE_EQ", "EQUITY"),
    "NLCINDIA":   _SymbolMeta("8585", "NSE_EQ", "EQUITY"),
    "NTPCGREEN":  _SymbolMeta("27176", "NSE_EQ", "EQUITY"),
    "RADICO":     _SymbolMeta("10990", "NSE_EQ", "EQUITY"),
    "SCHAEFFLER": _SymbolMeta("1011", "NSE_EQ", "EQUITY"),
    "SJVN":       _SymbolMeta("18883", "NSE_EQ", "EQUITY"),
    "SUNDARMFIN": _SymbolMeta("3339", "NSE_EQ", "EQUITY"),
    "TATACOMM":   _SymbolMeta("3721", "NSE_EQ", "EQUITY"),
    "TATAINVEST": _SymbolMeta("1621", "NSE_EQ", "EQUITY"),
    "THERMAX":    _SymbolMeta("3475", "NSE_EQ", "EQUITY"),
    "TORNTPOWER": _SymbolMeta("13786", "NSE_EQ", "EQUITY"),
    "UBL":        _SymbolMeta("16713", "NSE_EQ", "EQUITY"),
}


SMALLCAP_CASH_EQUITY_SYMBOLS: Final[dict[str, _SymbolMeta]] = {
    "AADHARHFC":  _SymbolMeta("23729", "NSE_EQ", "EQUITY"),
    "AARTIIND":   _SymbolMeta("7", "NSE_EQ", "EQUITY"),
    "AAVAS":      _SymbolMeta("5385", "NSE_EQ", "EQUITY"),
    "ABDL":       _SymbolMeta("24308", "NSE_EQ", "EQUITY"),
    "ABFRL":      _SymbolMeta("30108", "NSE_EQ", "EQUITY"),
    "ABLBL":      _SymbolMeta("756843", "NSE_EQ", "EQUITY"),
    "ABREL":      _SymbolMeta("625", "NSE_EQ", "EQUITY"),
    "ABSLAMC":    _SymbolMeta("6018", "NSE_EQ", "EQUITY"),
    "ACE":        _SymbolMeta("13587", "NSE_EQ", "EQUITY"),
    "ACMESOLAR":  _SymbolMeta("27061", "NSE_EQ", "EQUITY"),
    "ACUTAAS":    _SymbolMeta("5578", "NSE_EQ", "EQUITY"),
    "AEGISLOG":   _SymbolMeta("40", "NSE_EQ", "EQUITY"),
    "AEGISVOPAK": _SymbolMeta("757336", "NSE_EQ", "EQUITY"),
    "AFCONS":     _SymbolMeta("25977", "NSE_EQ", "EQUITY"),
    "AFFLE":      _SymbolMeta("11343", "NSE_EQ", "EQUITY"),
    "ANANDRATHI": _SymbolMeta("7145", "NSE_EQ", "EQUITY"),
    "ANANTRAJ":   _SymbolMeta("13620", "NSE_EQ", "EQUITY"),
    "ANURAS":     _SymbolMeta("2829", "NSE_EQ", "EQUITY"),
    "APTUS":      _SymbolMeta("5435", "NSE_EQ", "EQUITY"),
    "ARE&M":      _SymbolMeta("100", "NSE_EQ", "EQUITY"),
    "ASAHIINDIA": _SymbolMeta("5378", "NSE_EQ", "EQUITY"),
    "ASTERDM":    _SymbolMeta("1508", "NSE_EQ", "EQUITY"),
    "ATHERENERG": _SymbolMeta("757645", "NSE_EQ", "EQUITY"),
    "ATUL":       _SymbolMeta("263", "NSE_EQ", "EQUITY"),
    "BALRAMCHIN": _SymbolMeta("341", "NSE_EQ", "EQUITY"),
    "BATAINDIA":  _SymbolMeta("371", "NSE_EQ", "EQUITY"),
    "BAYERCROP":  _SymbolMeta("17927", "NSE_EQ", "EQUITY"),
    "BBTC":       _SymbolMeta("380", "NSE_EQ", "EQUITY"),
    "BELRISE":    _SymbolMeta("757102", "NSE_EQ", "EQUITY"),
    "BEML":       _SymbolMeta("395", "NSE_EQ", "EQUITY"),
    "BIKAJI":     _SymbolMeta("11966", "NSE_EQ", "EQUITY"),
    "BLS":        _SymbolMeta("17279", "NSE_EQ", "EQUITY"),
    "BLUEDART":   _SymbolMeta("495", "NSE_EQ", "EQUITY"),
    "BLUEJET":    _SymbolMeta("19686", "NSE_EQ", "EQUITY"),
    "BRIGADE":    _SymbolMeta("15184", "NSE_EQ", "EQUITY"),
    "BSOFT":      _SymbolMeta("6994", "NSE_EQ", "EQUITY"),
    "CANFINHOME": _SymbolMeta("583", "NSE_EQ", "EQUITY"),
    "CANHLIFE":   _SymbolMeta("759477", "NSE_EQ", "EQUITY"),
    "CAPLIPOINT": _SymbolMeta("3906", "NSE_EQ", "EQUITY"),
    "CARBORUNIV": _SymbolMeta("595", "NSE_EQ", "EQUITY"),
    "CARTRADE":   _SymbolMeta("5407", "NSE_EQ", "EQUITY"),
    "CASTROLIND": _SymbolMeta("1250", "NSE_EQ", "EQUITY"),
    "CCL":        _SymbolMeta("11452", "NSE_EQ", "EQUITY"),
    "CEATLTD":    _SymbolMeta("15254", "NSE_EQ", "EQUITY"),
    "CEMPRO":     _SymbolMeta("5622", "NSE_EQ", "EQUITY"),
    "CENTRALBK":  _SymbolMeta("14894", "NSE_EQ", "EQUITY"),
    "CESC":       _SymbolMeta("628", "NSE_EQ", "EQUITY"),
    "CGCL":       _SymbolMeta("20329", "NSE_EQ", "EQUITY"),
    "CHALET":     _SymbolMeta("8546", "NSE_EQ", "EQUITY"),
    "CHAMBLFERT": _SymbolMeta("637", "NSE_EQ", "EQUITY"),
    "CHENNPETRO": _SymbolMeta("2049", "NSE_EQ", "EQUITY"),
    "CHOICEIN":   _SymbolMeta("8866", "NSE_EQ", "EQUITY"),
    "CHOLAHLDNG": _SymbolMeta("21740", "NSE_EQ", "EQUITY"),
    "CLEAN":      _SymbolMeta("5049", "NSE_EQ", "EQUITY"),
    "COHANCE":    _SymbolMeta("17945", "NSE_EQ", "EQUITY"),
    "CONCORDBIO": _SymbolMeta("18060", "NSE_EQ", "EQUITY"),
    "CPPLUS":     _SymbolMeta("758858", "NSE_EQ", "EQUITY"),
    "CRAFTSMAN":  _SymbolMeta("2854", "NSE_EQ", "EQUITY"),
    "CREDITACC":  _SymbolMeta("4421", "NSE_EQ", "EQUITY"),
    "CUB":        _SymbolMeta("5701", "NSE_EQ", "EQUITY"),
    "CYIENT":     _SymbolMeta("5748", "NSE_EQ", "EQUITY"),
    "DATAPATTNS": _SymbolMeta("7358", "NSE_EQ", "EQUITY"),
    "DCMSHRIRAM": _SymbolMeta("811", "NSE_EQ", "EQUITY"),
    "DEEPAKFERT": _SymbolMeta("827", "NSE_EQ", "EQUITY"),
    "DEEPAKNTR":  _SymbolMeta("19943", "NSE_EQ", "EQUITY"),
    "DEVYANI":    _SymbolMeta("5373", "NSE_EQ", "EQUITY"),
    "DOMS":       _SymbolMeta("20551", "NSE_EQ", "EQUITY"),
    "ECLERX":     _SymbolMeta("15179", "NSE_EQ", "EQUITY"),
    "EIDPARRY":   _SymbolMeta("916", "NSE_EQ", "EQUITY"),
    "EIHOTEL":    _SymbolMeta("919", "NSE_EQ", "EQUITY"),
    "ELECON":     _SymbolMeta("13643", "NSE_EQ", "EQUITY"),
    "ELGIEQUIP":  _SymbolMeta("937", "NSE_EQ", "EQUITY"),
    "EMAMILTD":   _SymbolMeta("13517", "NSE_EQ", "EQUITY"),
    "EMCURE":     _SymbolMeta("24398", "NSE_EQ", "EQUITY"),
    "EMMVEE":     _SymbolMeta("759728", "NSE_EQ", "EQUITY"),
    "ENGINERSIN": _SymbolMeta("4907", "NSE_EQ", "EQUITY"),
    "ERIS":       _SymbolMeta("21154", "NSE_EQ", "EQUITY"),
    "FACT":       _SymbolMeta("1008", "NSE_EQ", "EQUITY"),
    "FINCABLES":  _SymbolMeta("1038", "NSE_EQ", "EQUITY"),
    "FIRSTCRY":   _SymbolMeta("24814", "NSE_EQ", "EQUITY"),
    "FIVESTAR":   _SymbolMeta("12032", "NSE_EQ", "EQUITY"),
    "FSL":        _SymbolMeta("14304", "NSE_EQ", "EQUITY"),
    "GABRIEL":    _SymbolMeta("1085", "NSE_EQ", "EQUITY"),
    "GALLANTT":   _SymbolMeta("13337", "NSE_EQ", "EQUITY"),
    "GESHIP":     _SymbolMeta("13776", "NSE_EQ", "EQUITY"),
    "GILLETTE":   _SymbolMeta("1576", "NSE_EQ", "EQUITY"),
    "GLAND":      _SymbolMeta("1186", "NSE_EQ", "EQUITY"),
    "GMDCLTD":    _SymbolMeta("5204", "NSE_EQ", "EQUITY"),
    "GODIGIT":    _SymbolMeta("23799", "NSE_EQ", "EQUITY"),
    "GPIL":       _SymbolMeta("13409", "NSE_EQ", "EQUITY"),
    "GRANULES":   _SymbolMeta("11872", "NSE_EQ", "EQUITY"),
    "GRAPHITE":   _SymbolMeta("592", "NSE_EQ", "EQUITY"),
    "GRAVITA":    _SymbolMeta("20534", "NSE_EQ", "EQUITY"),
    "GRSE":       _SymbolMeta("5475", "NSE_EQ", "EQUITY"),
    "GSPL":       _SymbolMeta("13197", "NSE_EQ", "EQUITY"),
    "HBLENGINE":  _SymbolMeta("13966", "NSE_EQ", "EQUITY"),
    "HEG":        _SymbolMeta("1336", "NSE_EQ", "EQUITY"),
    "HFCL":       _SymbolMeta("21951", "NSE_EQ", "EQUITY"),
    "HINDCOPPER": _SymbolMeta("17939", "NSE_EQ", "EQUITY"),
    "HOMEFIRST":  _SymbolMeta("2056", "NSE_EQ", "EQUITY"),
    "HONASA":     _SymbolMeta("19813", "NSE_EQ", "EQUITY"),
    "HSCL":       _SymbolMeta("14334", "NSE_EQ", "EQUITY"),
    "IDBI":       _SymbolMeta("1476", "NSE_EQ", "EQUITY"),
    "IFCI":       _SymbolMeta("1491", "NSE_EQ", "EQUITY"),
    "IGIL":       _SymbolMeta("28378", "NSE_EQ", "EQUITY"),
    "IGL":        _SymbolMeta("11262", "NSE_EQ", "EQUITY"),
    "IIFL":       _SymbolMeta("11809", "NSE_EQ", "EQUITY"),
    "IKS":        _SymbolMeta("28125", "NSE_EQ", "EQUITY"),
    "INDGN":      _SymbolMeta("23693", "NSE_EQ", "EQUITY"),
    "INDIACEM":   _SymbolMeta("1515", "NSE_EQ", "EQUITY"),
    "INDIAMART":  _SymbolMeta("10726", "NSE_EQ", "EQUITY"),
    "INTELLECT":  _SymbolMeta("5926", "NSE_EQ", "EQUITY"),
    "IOB":        _SymbolMeta("9348", "NSE_EQ", "EQUITY"),
    "IRB":        _SymbolMeta("15313", "NSE_EQ", "EQUITY"),
    "IRCON":      _SymbolMeta("4986", "NSE_EQ", "EQUITY"),
    "ITI":        _SymbolMeta("1675", "NSE_EQ", "EQUITY"),
    "J&KBANK":    _SymbolMeta("5633", "NSE_EQ", "EQUITY"),
    "JAINREC":    _SymbolMeta("759244", "NSE_EQ", "EQUITY"),
    "JBCHEPHARM": _SymbolMeta("1726", "NSE_EQ", "EQUITY"),
    "JBMA":       _SymbolMeta("11655", "NSE_EQ", "EQUITY"),
    "JINDALSAW":  _SymbolMeta("3024", "NSE_EQ", "EQUITY"),
    "JKTYRE":     _SymbolMeta("14435", "NSE_EQ", "EQUITY"),
    "JMFINANCIL": _SymbolMeta("13637", "NSE_EQ", "EQUITY"),
    "JPPOWER":    _SymbolMeta("11763", "NSE_EQ", "EQUITY"),
    "JSWCEMENT":  _SymbolMeta("758460", "NSE_EQ", "EQUITY"),
    "JSWDULUX":   _SymbolMeta("1467", "NSE_EQ", "EQUITY"),
    "JUBLINGREA": _SymbolMeta("2783", "NSE_EQ", "EQUITY"),
    "JUBLPHARMA": _SymbolMeta("3637", "NSE_EQ", "EQUITY"),
    "JWL":        _SymbolMeta("20224", "NSE_EQ", "EQUITY"),
    "JYOTICNC":   _SymbolMeta("21334", "NSE_EQ", "EQUITY"),
    "KAJARIACER": _SymbolMeta("1808", "NSE_EQ", "EQUITY"),
    "KARURVYSYA": _SymbolMeta("1838", "NSE_EQ", "EQUITY"),
    "KEC":        _SymbolMeta("13260", "NSE_EQ", "EQUITY"),
    "KIMS":       _SymbolMeta("4847", "NSE_EQ", "EQUITY"),
    "KIRLOSENG":  _SymbolMeta("20936", "NSE_EQ", "EQUITY"),
    "KPIL":       _SymbolMeta("1814", "NSE_EQ", "EQUITY"),
    "LALPATHLAB": _SymbolMeta("11654", "NSE_EQ", "EQUITY"),
    "LATENTVIEW": _SymbolMeta("6818", "NSE_EQ", "EQUITY"),
    "LEMONTREE":  _SymbolMeta("2606", "NSE_EQ", "EQUITY"),
    "LTFOODS":    _SymbolMeta("13816", "NSE_EQ", "EQUITY"),
    "MAPMYINDIA": _SymbolMeta("7227", "NSE_EQ", "EQUITY"),
    "MEESHO":     _SymbolMeta("760229", "NSE_EQ", "EQUITY"),
    "MGL":        _SymbolMeta("17534", "NSE_EQ", "EQUITY"),
    "MINDACORP":  _SymbolMeta("25897", "NSE_EQ", "EQUITY"),
    "MMTC":       _SymbolMeta("17957", "NSE_EQ", "EQUITY"),
    "MRPL":       _SymbolMeta("2283", "NSE_EQ", "EQUITY"),
    "MSUMI":      _SymbolMeta("8596", "NSE_EQ", "EQUITY"),
    "NATCOPHARM": _SymbolMeta("3918", "NSE_EQ", "EQUITY"),
    "NAVA":       _SymbolMeta("4014", "NSE_EQ", "EQUITY"),
    "NAVINFLUOR": _SymbolMeta("14672", "NSE_EQ", "EQUITY"),
    "NCC":        _SymbolMeta("2319", "NSE_EQ", "EQUITY"),
    "NETWEB":     _SymbolMeta("17433", "NSE_EQ", "EQUITY"),
    "NEULANDLAB": _SymbolMeta("2406", "NSE_EQ", "EQUITY"),
    "NEWGEN":     _SymbolMeta("1164", "NSE_EQ", "EQUITY"),
    "NH":         _SymbolMeta("11840", "NSE_EQ", "EQUITY"),
    "NIVABUPA":   _SymbolMeta("27097", "NSE_EQ", "EQUITY"),
    "NSLNISP":    _SymbolMeta("14180", "NSE_EQ", "EQUITY"),
    "NUVOCO":     _SymbolMeta("5426", "NSE_EQ", "EQUITY"),
    "OLAELEC":    _SymbolMeta("24777", "NSE_EQ", "EQUITY"),
    "OLECTRA":    _SymbolMeta("10637", "NSE_EQ", "EQUITY"),
    "ONESOURCE":  _SymbolMeta("29224", "NSE_EQ", "EQUITY"),
    "PARADEEP":   _SymbolMeta("9741", "NSE_EQ", "EQUITY"),
    "PCBL":       _SymbolMeta("2649", "NSE_EQ", "EQUITY"),
    "PFIZER":     _SymbolMeta("2643", "NSE_EQ", "EQUITY"),
    "PINELABS":   _SymbolMeta("759820", "NSE_EQ", "EQUITY"),
    "PIRAMALFIN": _SymbolMeta("759551", "NSE_EQ", "EQUITY"),
    "POLYMED":    _SymbolMeta("25718", "NSE_EQ", "EQUITY"),
    "POONAWALLA": _SymbolMeta("11403", "NSE_EQ", "EQUITY"),
    "PPLPHARMA":  _SymbolMeta("11571", "NSE_EQ", "EQUITY"),
    "PTCIL":      _SymbolMeta("16682", "NSE_EQ", "EQUITY"),
    "PVRINOX":    _SymbolMeta("13147", "NSE_EQ", "EQUITY"),
    "PWL":        _SymbolMeta("759723", "NSE_EQ", "EQUITY"),
    "RAILTEL":    _SymbolMeta("2431", "NSE_EQ", "EQUITY"),
    "RAINBOW":    _SymbolMeta("9408", "NSE_EQ", "EQUITY"),
    "RAMCOCEM":   _SymbolMeta("2043", "NSE_EQ", "EQUITY"),
    "REDINGTON":  _SymbolMeta("14255", "NSE_EQ", "EQUITY"),
    "RHIM":       _SymbolMeta("31163", "NSE_EQ", "EQUITY"),
    "RITES":      _SymbolMeta("3761", "NSE_EQ", "EQUITY"),
    "RKFORGE":    _SymbolMeta("11411", "NSE_EQ", "EQUITY"),
    "RPOWER":     _SymbolMeta("15259", "NSE_EQ", "EQUITY"),
    "RRKABEL":    _SymbolMeta("18566", "NSE_EQ", "EQUITY"),
    "SAGILITY":   _SymbolMeta("27052", "NSE_EQ", "EQUITY"),
    "SAILIFE":    _SymbolMeta("27839", "NSE_EQ", "EQUITY"),
    "SAPPHIRE":   _SymbolMeta("6718", "NSE_EQ", "EQUITY"),
    "SARDAEN":    _SymbolMeta("17758", "NSE_EQ", "EQUITY"),
    "SAREGAMA":   _SymbolMeta("4892", "NSE_EQ", "EQUITY"),
    "SBFC":       _SymbolMeta("18026", "NSE_EQ", "EQUITY"),
    "SCHNEIDER":  _SymbolMeta("31238", "NSE_EQ", "EQUITY"),
    "SCI":        _SymbolMeta("3048", "NSE_EQ", "EQUITY"),
    "SHYAMMETL":  _SymbolMeta("4693", "NSE_EQ", "EQUITY"),
    "SIGNATURE":  _SymbolMeta("18743", "NSE_EQ", "EQUITY"),
    "SOBHA":      _SymbolMeta("13826", "NSE_EQ", "EQUITY"),
    "SONATSOFTW": _SymbolMeta("6596", "NSE_EQ", "EQUITY"),
    "SPLPETRO":   _SymbolMeta("9617", "NSE_EQ", "EQUITY"),
    "STARHEALTH": _SymbolMeta("7083", "NSE_EQ", "EQUITY"),
    "SUMICHEM":   _SymbolMeta("17105", "NSE_EQ", "EQUITY"),
    "SUNTV":      _SymbolMeta("13404", "NSE_EQ", "EQUITY"),
    "SWANCORP":   _SymbolMeta("27095", "NSE_EQ", "EQUITY"),
    "SYNGENE":    _SymbolMeta("10243", "NSE_EQ", "EQUITY"),
    "SYRMA":      _SymbolMeta("10793", "NSE_EQ", "EQUITY"),
    "TARIL":      _SymbolMeta("15174", "NSE_EQ", "EQUITY"),
    "TATACHEM":   _SymbolMeta("3405", "NSE_EQ", "EQUITY"),
    "TATATECH":   _SymbolMeta("20293", "NSE_EQ", "EQUITY"),
    "TBOTEK":     _SymbolMeta("23740", "NSE_EQ", "EQUITY"),
    "TECHNOE":    _SymbolMeta("6445", "NSE_EQ", "EQUITY"),
    "TEGA":       _SymbolMeta("7105", "NSE_EQ", "EQUITY"),
    "TEJASNET":   _SymbolMeta("21131", "NSE_EQ", "EQUITY"),
    "TENNIND":    _SymbolMeta("759880", "NSE_EQ", "EQUITY"),
    "THELEELA":   _SymbolMeta("757014", "NSE_EQ", "EQUITY"),
    "TIMKEN":     _SymbolMeta("14198", "NSE_EQ", "EQUITY"),
    "TITAGARH":   _SymbolMeta("15414", "NSE_EQ", "EQUITY"),
    "TRAVELFOOD": _SymbolMeta("757545", "NSE_EQ", "EQUITY"),
    "TRIDENT":    _SymbolMeta("9685", "NSE_EQ", "EQUITY"),
    "TRITURBINE": _SymbolMeta("25584", "NSE_EQ", "EQUITY"),
    "TTML":       _SymbolMeta("8954", "NSE_EQ", "EQUITY"),
    "UCOBANK":    _SymbolMeta("11223", "NSE_EQ", "EQUITY"),
    "URBANCO":    _SymbolMeta("759084", "NSE_EQ", "EQUITY"),
    "USHAMART":   _SymbolMeta("8840", "NSE_EQ", "EQUITY"),
    "UTIAMC":     _SymbolMeta("527", "NSE_EQ", "EQUITY"),
    "VIJAYA":     _SymbolMeta("5585", "NSE_EQ", "EQUITY"),
    "VTL":        _SymbolMeta("2073", "NSE_EQ", "EQUITY"),
    "WELCORP":    _SymbolMeta("11821", "NSE_EQ", "EQUITY"),
    "WELSPUNLIV": _SymbolMeta("11253", "NSE_EQ", "EQUITY"),
    "WHIRLPOOL":  _SymbolMeta("18011", "NSE_EQ", "EQUITY"),
    "WOCKPHARMA": _SymbolMeta("7506", "NSE_EQ", "EQUITY"),
    "ZEEL":       _SymbolMeta("3812", "NSE_EQ", "EQUITY"),
    "ZENSARTECH": _SymbolMeta("1076", "NSE_EQ", "EQUITY"),
    "ZENTEC":     _SymbolMeta("7508", "NSE_EQ", "EQUITY"),
    "ZFCVINDIA":  _SymbolMeta("16915", "NSE_EQ", "EQUITY"),
    "ZYDUSWELL":  _SymbolMeta("17635", "NSE_EQ", "EQUITY"),
}


CASH_EQUITY_SYMBOLS: Final[dict[str, _SymbolMeta]] = {
    **LARGE_CAP_CASH_EQUITY_SYMBOLS,
    **MIDCAP_CASH_EQUITY_SYMBOLS,
    **SMALLCAP_CASH_EQUITY_SYMBOLS,
}


# Public surface — merged superset. The rest of the data-provider
# code reads from KNOWN_SYMBOLS and is unaffected by the sub-dict
# refactor.
KNOWN_SYMBOLS: Final[dict[str, _SymbolMeta]] = {
    **INDEX_SYMBOLS,
    **CASH_EQUITY_SYMBOLS,
    **FNO_STOCK_SYMBOLS,
}


__all__ = [
    "CACHE_DIR_NAME",
    "CACHE_TTL_HISTORICAL_HOURS",
    "CACHE_TTL_RECENT_HOURS",
    "CASH_EQUITY_SYMBOLS",
    "DAILY_TIMEFRAME",
    "DHAN_API_BASE_URL",
    "DHAN_HISTORICAL_DAILY_PATH",
    "DHAN_HISTORICAL_INTRADAY_PATH",
    "DHAN_RATE_LIMIT_PER_DAY",
    "DHAN_RATE_LIMIT_PER_SECOND",
    "FNO_STOCK_SYMBOLS",
    "INDEX_SYMBOLS",
    "INITIAL_BACKOFF_SECONDS",
    "INTRADAY_MAX_DAYS_PER_REQUEST",
    "KNOWN_SYMBOLS",
    "LARGE_CAP_CASH_EQUITY_SYMBOLS",
    "MAX_RETRY_ATTEMPTS",
    "MIDCAP_CASH_EQUITY_SYMBOLS",
    "QUALITY_SCORE_WARN_THRESHOLD",
    "RECENT_DATA_THRESHOLD_DAYS",
    "SMALLCAP_CASH_EQUITY_SYMBOLS",
    "SYMBOL_ALIASES",
    "TIMEFRAME_TO_INTERVAL_MINUTES",
]
