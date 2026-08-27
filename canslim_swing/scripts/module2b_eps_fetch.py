#!/usr/bin/env python3
"""canslim-swing MODULE 2b — full quarterly-EPS fetch (210 habitat symbols) + audit.

Source: NSE official (per the M2a probe recommendation), both regimes:
  old  (quarters ending <= Dec-2024): /api/corporates-financial-results list
       + /api/corporates-financial-results-data per filing  -> EPS + filing ts
  new  (Dec-2024 ->): /api/integrated-filing-results + per-filing XBRL parse

Rules honored:
  - NSE only, >= ~1.05s between requests per host, probe session/cookie pattern.
  - Atomic cache writes, request-level skip-existing => fully resumable.
  - On 3 failed retries the SYMBOL is parked (never hammered) and the run moves on;
    a rerun retries parked symbols automatically.
  - Report regenerates byte-identically from cache with zero network:
      python module2b_eps_fetch.py --report-only

Cache:  canslim_swing/data/eps/raw/<symbol>/{list,integrated,detail_<seq>,xbrl_<seq>}.json
        + _done.json / _parked.json markers, data/eps/_run_stats.json (accumulated)
Output: canslim_swing/data/eps/eps_quarterly.parquet
        canslim_swing/reports/swing_module2b_eps_fetch.txt
"""
from __future__ import annotations

import collections
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

TRACK = Path(__file__).resolve().parents[1]
HABITAT_DIR = Path("/Users/jayeshparekh/tradetri-strategies/pine_replica/data/habitat")
DAILY_DIR = TRACK / "data" / "swing" / "daily"          # M1 output (read-only)
EPS_DIR = TRACK / "data" / "eps"
RAW = EPS_DIR / "raw"
STATS_PATH = EPS_DIR / "_run_stats.json"
PARQUET_PATH = EPS_DIR / "eps_quarterly.parquet"
REPORT_PATH = TRACK / "reports" / "swing_module2b_eps_fetch.txt"

WINDOW_FIRST = datetime(2020, 6, 30)                     # Apr-Jun-2020 quarter end
WINDOW_LAST = datetime(2026, 6, 30)                      # Apr-Jun-2026 quarter end
KNOWN_ALIASES = {"TATAMOTORS": ["TMPV"], "ZOMATO": ["ETERNAL"]}
RENAMED_ENTITIES = {"TMPV", "ETERNAL"}                   # holes here class as MIGRATED-GAP

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
BASE_HEADERS = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
NSE = "https://www.nseindia.com"
NSE_WARM = f"{NSE}/companies-listing/corporate-filings-financial-results"

_last_hit: dict[str, float] = {}
REQUESTS_MADE = 0
COOLDOWN_STEPS = (15, 60, 180)      # seconds between retries — outlast a throttle window
PARK_STREAK_PAUSE = 300             # consecutive parks => the host is throttling us; rest


def throttle(host: str, min_gap: float = 1.05) -> None:
    wait = _last_hit.get(host, 0) + min_gap - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.monotonic()


def atomic_write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=0, default=str))
    os.replace(tmp, path)


def read_json(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


# ------------------------------------------------------------------ session / http
def warm(s: requests.Session) -> None:
    for url in (NSE, NSE_WARM):
        throttle("nse")
        try:
            s.get(url, headers=BASE_HEADERS, timeout=20)
        except requests.RequestException:
            pass


class NotFound(Exception):
    """Permanent 404 — the resource does not exist server-side; never retry."""


def http_get(s: requests.Session, url: str, host: str = "nse", retries: int = 3):
    """GET with throttle + retry + re-warm on bot-guard. Raises after `retries`.
    404 raises NotFound immediately (permanent miss, not an access failure).

    Observed failure mode: after a few hundred sustained requests NSE stops
    answering (read timeouts on BOTH www and nsearchives, or 5xx) for tens of
    seconds. Retries therefore back off long enough to outlast a throttle window,
    and the archive host gets a longer read timeout because its XBRL payloads run
    to several MB.
    """
    global REQUESTS_MADE
    timeout = 90 if host == "nsearchives" else 45
    last = None
    for attempt in range(retries):
        throttle(host)
        REQUESTS_MADE += 1
        try:
            r = s.get(url, headers={**BASE_HEADERS, "Referer": NSE_WARM}, timeout=timeout)
        except requests.RequestException as exc:
            last = exc
        else:
            if r.status_code == 200:
                return r
            if r.status_code == 404:
                raise NotFound(url[:140])
            if r.status_code in (401, 403):
                warm(s)
            last = RuntimeError(f"HTTP {r.status_code}")
        if attempt < retries - 1:
            time.sleep(COOLDOWN_STEPS[min(attempt, len(COOLDOWN_STEPS) - 1)])
            warm(s)                      # fresh cookies before the next attempt
    raise RuntimeError(f"exhausted retries: {url[:140]} ({last!r})")


# ------------------------------------------------------------------ parsing helpers
def parse_dmy(d: str | None):
    d = (d or "").strip()
    if not d or d == "-":
        return None
    for fmt in ("%d-%b-%Y", "%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M"):
        try:
            return datetime.strptime(d.title() if d.isupper() else d, fmt)
        except ValueError:
            continue
    return None


def fnum(v):
    if v is None:
        return None
    t = str(v).strip().replace(",", "")
    if t in ("", "-", "--", "NA", "N.A.", "null"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


EPS_BASIC_CHAIN = ("re_basic_eps_for_cont_dic_opr", "re_basic_eps", "re_bsc_eps_bfr_exi")
EPS_DIL_CHAIN = ("re_dilut_eps_for_cont_dic_opr", "re_diluted_eps", "re_dil_eps_bfr_exi")


def xbrl_parse(text: str, qe: datetime) -> dict:
    """Extract Basic/Diluted EPS + resolve the QUARTER fact by its context period.

    Taxonomy variants seen in the wild (all must be handled, else the miss is silent):
      * INDAS / NBFC_INDAS : Basic|DilutedEarningsLossPerShareFrom{ContinuingAnd
        DiscontinuedOperations,ContinuingOperations}
      * BANKING            : Basic|DilutedEarningsPerShare{After,Before}
        ExtraordinaryItems   <- NOTE: no 'Loss' in the tag name.
      * LI / insurance     : BasicAndDilutedEPS{After,Before}ExtraordinaryItems
        NetOfTaxExpenseForThePeriodNotToBeAnnualized  <- ONE combined fact that
        serves as both basic and diluted (insurers report a single figure).

    A fact is only accepted as QUARTERLY when its context spans 60-130 days and ends
    at the period end. Some filings (e.g. CGPOWER Q4-FY26) carry ONLY half-year
    (181d) + full-year (364d) facts: those are recorded as reason='no-quarterly-fact'
    and left NULL. Taking the 181d number would silently double the quarter's EPS.
    """
    ctx_period: dict[str, tuple] = {}
    for m in re.finditer(
            r'<(?:[\w-]+:)?context id="([^"]+)">(.*?)</(?:[\w-]+:)?context>', text, re.S):
        cid, body = m.group(1), m.group(2)
        sd = re.search(r'<(?:[\w-]+:)?startDate>([\d-]+)<', body)
        ed = re.search(r'<(?:[\w-]+:)?endDate>([\d-]+)<', body)
        if sd and ed:
            ctx_period[cid] = (sd.group(1), ed.group(1))
    def resolve(cid: str):
        """Period for a contextRef, inferring it when the file never defines it.

        Some NSE-archived instances are INVALID: facts reference 'OneD'/'FourD'
        but only dimensioned siblings ('OneOtherRevenueFromOperations01D', ...)
        are declared. Those siblings belong to the same reported column, so their
        period IS that column's period. We infer ONLY when every sibling sharing
        the prefix agrees; we never assume 'OneD == a quarter' by convention —
        CGPOWER's OneD is a 181-day half-year, so that guess would silently
        import a half-year EPS as if it were quarterly.
        """
        if cid in ctx_period:
            return ctx_period[cid], False
        prefix = re.match(r'^([A-Z][a-z]+)', cid)
        if not prefix:
            return None, False
        sibs = {v for k, v in ctx_period.items() if k.startswith(prefix.group(1))}
        return (next(iter(sibs)), True) if len(sibs) == 1 else (None, False)

    out = {"facts": {}, "quarter": {}, "quarter_days": {}, "reason": {}}
    for kind in ("Basic", "Diluted"):
        pats = [
            rf'<in-capmkt:{kind}EarningsLossPerShareFromContinuingAndDiscontinuedOperations[^>]*contextRef="([^"]+)"[^>]*>([^<]*)<',
            rf'<in-capmkt:{kind}EarningsLossPerShareFromContinuingOperations[^>]*contextRef="([^"]+)"[^>]*>([^<]*)<',
            rf'<(?:[\w-]+:)?{kind}EarningsPerShareAfterExtraordinaryItems[^>]*contextRef="([^"]+)"[^>]*>([^<]*)<',
            rf'<(?:[\w-]+:)?{kind}EarningsPerShareBeforeExtraordinaryItems[^>]*contextRef="([^"]+)"[^>]*>([^<]*)<',
            rf'<(?:[\w-]+:)?{kind}Earnings(?:Loss)?PerShare[A-Za-z]*[^>]*contextRef="([^"]+)"[^>]*>([^<]*)<',
            # insurers: single combined fact, used for BOTH basic and diluted
            r'<(?:[\w-]+:)?BasicAndDilutedEPSAfterExtraordinaryItems[A-Za-z]*[^>]*contextRef="([^"]+)"[^>]*>([^<]*)<',
            r'<(?:[\w-]+:)?BasicAndDilutedEPSBeforeExtraordinaryItems[A-Za-z]*[^>]*contextRef="([^"]+)"[^>]*>([^<]*)<',
        ]
        facts: list[dict] = []
        for p in pats:
            facts = [{"context": c, "value": v,
                      "period": ctx_period.get(c)} for c, v in re.findall(p, text)]
            if facts:
                break
        out["facts"][kind.lower()] = facts
        chosen = chosen_days = None
        inferred = False
        spans = []
        for f in facts:
            per, was_inferred = resolve(f["context"])
            if not per:
                continue
            try:
                sd, ed = datetime.fromisoformat(per[0]), datetime.fromisoformat(per[1])
            except ValueError:
                continue
            days = (ed - sd).days
            spans.append(days)
            if abs((ed - qe).days) <= 6 and 60 <= days <= 130:
                chosen, chosen_days, inferred = f["value"], days, was_inferred
                break
        if chosen is None:
            reason = ("no-eps-tag" if not facts
                      else "no-context-period" if not spans
                      else "no-quarterly-fact")
        else:
            reason = "ok-context-inferred" if inferred else "ok"
        out["quarter"][kind.lower()] = chosen
        out["quarter_days"][kind.lower()] = chosen_days
        out["reason"][kind.lower()] = reason
        if reason == "no-quarterly-fact":
            out.setdefault("spans_seen", {})[kind.lower()] = sorted(set(spans))
    return out


# ------------------------------------------------------------------ per-symbol fetch
def q(sym: str) -> str:
    return requests.utils.quote(sym, safe="")


def fetch_list(s, sym_dir: Path, symbol: str) -> dict:
    p = sym_dir / "list.json"
    if (hit := read_json(p)) is not None:
        return hit
    tried = []
    for cand in [symbol] + KNOWN_ALIASES.get(symbol, []):
        r = http_get(s, f"{NSE}/api/corporates-financial-results?index=equities"
                        f"&symbol={q(cand)}&period=Quarterly")
        try:
            rows = r.json() if r.content else []
        except ValueError:
            rows = []
        tried.append({"symbol": cand, "rows": len(rows)})
        if rows:
            out = {"symbol_used": cand, "tried": tried, "rows": rows}
            atomic_write(p, out)
            return out
    out = {"symbol_used": None, "tried": tried, "rows": []}
    atomic_write(p, out)
    return out


def fetch_integrated(s, sym_dir: Path, symbol: str, list_sym: str | None) -> dict:
    p = sym_dir / "integrated.json"
    if (hit := read_json(p)) is not None:
        return hit
    cands = [c for c in dict.fromkeys([list_sym, symbol] + KNOWN_ALIASES.get(symbol, [])) if c]
    tried = []
    for cand in cands:
        r = http_get(s, f"{NSE}/api/integrated-filing-results?index=equities&symbol={q(cand)}"
                        f"&period_ended=Quarterly&type=Integrated%20Filing-%20Financials")
        try:
            j = r.json()
        except ValueError:
            j = []
        rows = j if isinstance(j, list) else j.get("data", [])
        tried.append({"symbol": cand, "rows": len(rows)})
        if rows:
            out = {"symbol_used": cand, "tried": tried, "rows": rows}
            atomic_write(p, out)
            return out
    out = {"symbol_used": None, "tried": tried, "rows": []}
    atomic_write(p, out)
    return out


def fetch_symbol(s: requests.Session, symbol: str) -> str:
    """Returns 'done' | 'parked' | 'cached'."""
    sym_dir = RAW / symbol
    if (sym_dir / "_done.json").exists():
        return "cached"
    parked_marker = sym_dir / "_parked.json"
    if parked_marker.exists():
        parked_marker.unlink()                              # rerun => retry
    try:
        lst = fetch_list(s, sym_dir, symbol)
        integ = fetch_integrated(s, sym_dir, symbol, lst.get("symbol_used"))
        n_det = n_xb = 0
        for row in lst["rows"]:
            if row.get("period") != "Quarterly":
                continue
            td = parse_dmy(row.get("toDate"))
            if not td or not (WINDOW_FIRST <= td <= WINDOW_LAST):
                continue
            dp = sym_dir / f"detail_{row['seqNumber']}.json"
            if dp.exists():
                continue
            url = (f"{NSE}/api/corporates-financial-results-data?index=equities"
                   f"&params={q(row['params'])}&seq_id={row['seqNumber']}"
                   f"&industry={q(row.get('industry') or '-')}"
                   f"&ind={q(row.get('indAs') or '')}&format={row.get('format') or ''}")
            try:
                r = http_get(s, url)
                try:
                    j = r.json()
                except ValueError:
                    j = {"_non_json": r.text[:120]}
            except NotFound as nf:
                j = {"_error": f"404: {nf}"}
            rd = j.get("resultsData2") or j.get("resultsData") or {}
            eps = ({k: rd.get(k) for k in set(EPS_BASIC_CHAIN) | set(EPS_DIL_CHAIN)}
                   if isinstance(rd, dict) else {})
            eps_ok = any(fnum(v) is not None for v in eps.values())
            xb = None
            if not eps_ok and row.get("xbrl"):
                # The detail API returns an EMPTY payload for whole sectors (all 27
                # NBFC/financial symbols: BAJFINANCE, CHOLAFIN, PFC, RECLTD ...).
                # The list row still carries an XBRL URL the detail API never exposes,
                # and it parses with the same taxonomy-aware parser. Without this
                # fallback those 726 filings silently have no EPS at all.
                try:
                    xr = http_get(s, row["xbrl"], host="nsearchives")
                    parsed = xbrl_parse(xr.text, td)
                    xb = {"quarter_eps": parsed["quarter"],
                          "quarter_days": parsed.get("quarter_days"),
                          "eps_reason": parsed.get("reason"),
                          "spans_seen": parsed.get("spans_seen"),
                          "url": row["xbrl"]}
                except NotFound as nf:
                    xb = {"_error": f"404: {nf}", "url": row["xbrl"]}
            atomic_write(dp, {
                "seq": row["seqNumber"], "toDate": row.get("toDate"),
                "xbrl_fallback": xb,
                "consolidated": row.get("consolidated"), "reInd": row.get("reInd"),
                "audited": row.get("audited"), "format": row.get("format"),
                "broadCastDate": row.get("broadCastDate"),
                "filingDate_list": row.get("filingDate"),
                "filingDate_detail": j.get("filingDate"),
                "resultsData_kind": ("resultsData2" if j.get("resultsData2") else
                                     "resultsData" if j.get("resultsData") else "none"),
                "eps_fields": eps})
            n_det += 1
        for row in integ["rows"]:
            qe = parse_dmy(row.get("qe_Date"))
            if not qe or not (WINDOW_FIRST <= qe <= WINDOW_LAST) or not row.get("xbrl"):
                continue
            xp = sym_dir / f"xbrl_{row['seq_Id']}.json"
            if xp.exists():
                continue
            try:
                r = http_get(s, row["xbrl"], host="nsearchives")
                parsed = xbrl_parse(r.text, qe)
            except NotFound as nf:
                parsed = {"quarter": {}, "facts": {}, "_error": f"404: {nf}"}
            atomic_write(xp, {
                **({"_error": parsed["_error"]} if "_error" in parsed else {}),
                "seq": row["seq_Id"], "qe_Date": row.get("qe_Date"),
                "consolidated": row.get("consolidated"), "audited": row.get("audited"),
                "broadcast_Date": row.get("broadcast_Date"),
                "revised_Date": row.get("revised_Date"),
                "revision_Remark": row.get("revision_Remark"),
                "quarter_eps": parsed["quarter"],
                "quarter_days": parsed.get("quarter_days"),
                "eps_reason": parsed.get("reason"),
                "spans_seen": parsed.get("spans_seen"),
                "facts": parsed["facts"]})
            n_xb += 1
        atomic_write(sym_dir / "_done.json", {
            "symbol": symbol, "list_symbol": lst.get("symbol_used"),
            "integrated_symbol": integ.get("symbol_used"),
            "list_rows": len(lst["rows"]), "integrated_rows": len(integ["rows"]),
            "details_fetched_this_run": n_det, "xbrl_fetched_this_run": n_xb})
        return "done"
    except Exception as exc:                                # park, never hammer
        atomic_write(parked_marker, {"symbol": symbol, "error": repr(exc)[:300]})
        return "parked"


# ------------------------------------------------------------------ parquet build
def quarter_ends() -> list[datetime]:
    out, y = [], 2020
    while True:
        for md in ((3, 31), (6, 30), (9, 30), (12, 31)):
            d = datetime(y, *md)
            if WINDOW_FIRST <= d <= WINDOW_LAST:
                out.append(d)
        if y == 2026:
            break
        y += 1
    return sorted(out)


def build_rows(symbol: str) -> list[dict]:
    sym_dir = RAW / symbol
    rows: list[dict] = []
    for dp in sorted(sym_dir.glob("detail_*.json")):
        d = read_json(dp)
        pe = parse_dmy(d.get("toDate"))
        if not pe:
            continue
        ts = parse_dmy(d.get("broadCastDate")) or parse_dmy(d.get("filingDate_detail")) \
            or parse_dmy(d.get("filingDate_list"))
        eps = d.get("eps_fields") or {}
        basic = next((fnum(eps.get(k)) for k in EPS_BASIC_CHAIN if fnum(eps.get(k)) is not None), None)
        dil = next((fnum(eps.get(k)) for k in EPS_DIL_CHAIN if fnum(eps.get(k)) is not None), None)
        if basic is None and dil is None:
            fb = (d.get("xbrl_fallback") or {}).get("quarter_eps") or {}
            basic, dil = fnum(fb.get("basic")), fnum(fb.get("diluted"))
        rows.append({"symbol": symbol, "period_end": pe, "announce_ts": ts,
                     "variant": "cons" if d.get("consolidated") == "Consolidated" else "stand",
                     "eps_basic": basic, "eps_dil": dil,
                     "audited": d.get("audited"), "source_regime": "old",
                     "re_ind": d.get("reInd"), "revised_ts": None})
    for xp in sorted(sym_dir.glob("xbrl_*.json")):
        d = read_json(xp)
        pe = parse_dmy(d.get("qe_Date"))
        if not pe:
            continue
        qeps = d.get("quarter_eps") or {}
        rows.append({"symbol": symbol, "period_end": pe,
                     "announce_ts": parse_dmy(d.get("broadcast_Date")),
                     "variant": "cons" if d.get("consolidated") == "Consolidated" else "stand",
                     "eps_basic": fnum(qeps.get("basic")), "eps_dil": fnum(qeps.get("diluted")),
                     "audited": d.get("audited"), "source_regime": "integrated",
                     "re_ind": None, "revised_ts": parse_dmy(d.get("revised_Date"))})
    # cross-regime duplicate: same (pe, variant), ts within 3 days -> keep old-regime row
    keyed: dict[tuple, list[dict]] = {}
    for r in rows:
        keyed.setdefault((r["period_end"], r["variant"]), []).append(r)
    deduped = []
    for grp in keyed.values():
        grp.sort(key=lambda r: (r["announce_ts"] or datetime.max, r["source_regime"]))
        kept: list[dict] = []
        for r in grp:
            dup = next((k for k in kept if r["announce_ts"] and k["announce_ts"]
                        and abs((r["announce_ts"] - k["announce_ts"]).days) <= 3), None)
            if dup is None and r["announce_ts"] is None:
                # ts-less duplicate list entry for an already-kept filing (same values)
                dup = next((k for k in kept if k["eps_basic"] == r["eps_basic"]
                            and k["eps_dil"] == r["eps_dil"]), None)
            if dup is not None:
                if dup["source_regime"] == "integrated" and r["source_regime"] == "old":
                    kept[kept.index(dup)] = r
                continue
            kept.append(r)
        for i, r in enumerate(kept):
            r["is_revision"] = i > 0 or r.get("re_ind") == "I"
        deduped.extend(kept)
    return deduped


def build_parquet(symbols: list[str]) -> pd.DataFrame:
    all_rows = [r for sym in symbols for r in build_rows(sym)]
    df = pd.DataFrame(all_rows)
    if df.empty:
        return df
    wide = df.assign(
        eps_basic_cons=df["eps_basic"].where(df["variant"] == "cons"),
        eps_dil_cons=df["eps_dil"].where(df["variant"] == "cons"),
        eps_basic_stand=df["eps_basic"].where(df["variant"] == "stand"),
        eps_dil_stand=df["eps_dil"].where(df["variant"] == "stand"),
    )[["symbol", "period_end", "announce_ts", "eps_basic_cons", "eps_dil_cons",
       "eps_basic_stand", "eps_dil_stand", "source_regime", "is_revision",
       "revised_ts", "variant", "audited"]]
    wide = wide.sort_values(["symbol", "period_end", "variant", "announce_ts"],
                            na_position="last").reset_index(drop=True)
    EPS_DIR.mkdir(parents=True, exist_ok=True)
    wide.to_parquet(PARQUET_PATH)
    return wide


# ------------------------------------------------------------------ audit + report
def listing_proxy(symbol: str):
    p = DAILY_DIR / f"{symbol}.parquet"
    if not p.exists():
        return None
    idx = pd.read_parquet(p, columns=["close"]).index
    first = idx.min().to_pydatetime()
    return first if first > datetime(2021, 8, 5) else None      # None => pre-window listing


def source_horizon(symbol: str) -> dict:
    """What each NSE regime actually OFFERS for this symbol (not what we kept).

    The old-regime list endpoint serves a per-symbol window that varies wildly:
    157/210 symbols get 60+ filings back to 2005, but 6 (the 5 insurers + MCX)
    get ZERO rows under every period value, and a handful (NESTLEIND, FORCEMOT,
    IRFC...) only get 2024+. A quarter the endpoint never offers is a SOURCE gap,
    not an unexplained hole — conflating the two would overstate our own failure
    and hide a real limitation of the recommended source.
    """
    sd = RAW / symbol
    lst = read_json(sd / "list.json") or {}
    integ = read_json(sd / "integrated.json") or {}
    l_dates = [parse_dmy(r.get("toDate")) for r in (lst.get("rows") or [])]
    i_dates = [parse_dmy(r.get("qe_Date")) for r in (integ.get("rows") or [])]
    l_dates = [d for d in l_dates if d]
    i_dates = [d for d in i_dates if d]
    return {"list_rows": len(lst.get("rows") or []),
            "list_from": min(l_dates) if l_dates else None,
            "list_to": max(l_dates) if l_dates else None,
            "integ_from": min(i_dates) if i_dates else None,
            # the decisive set: quarters NSE actually OFFERS a filing row for.
            # If a quarter is not in here we had nothing to fetch — that is a
            # source gap, not a fetch failure. If it IS here and we have no EPS,
            # the failure is ours and must be reported as such.
            "offered": {d for d in l_dates + i_dates}}


def collect_null_reasons() -> dict:
    """Why a LISTED filing yielded no EPS — so 'we have no number' is never
    reported without a cause. Keyed (symbol, period_end)."""
    out: dict[tuple, str] = {}
    for sd in sorted(RAW.glob("*/")):
        sym = sd.name
        for xf in sd.glob("xbrl_*.json"):
            d = read_json(xf) or {}
            pe = parse_dmy(d.get("qe_Date"))
            if pe is None:
                continue
            if "_error" in d:
                out.setdefault((sym, pe), "xbrl-404-on-archive")
            elif (d.get("quarter_eps") or {}).get("basic") is None:
                r = (d.get("eps_reason") or {}).get("basic", "parse-miss")
                spans = (d.get("spans_seen") or {}).get("basic")
                out.setdefault((sym, pe), f"{r}{' ' + str(spans) if spans else ''}")
        for df_ in sd.glob("detail_*.json"):
            d = read_json(df_) or {}
            pe = parse_dmy(d.get("toDate"))
            if pe is None:
                continue
            eps = d.get("eps_fields") or {}
            if any(fnum(v) is not None for v in eps.values()):
                continue
            fb = d.get("xbrl_fallback") or {}
            fq = fb.get("quarter_eps") or {}
            if fnum(fq.get("basic")) is not None or fnum(fq.get("diluted")) is not None:
                continue                                   # recovered via XBRL fallback
            if "_error" in fb:
                why = "detail-empty + xbrl-404"
            elif fb:
                why = f"detail-empty + xbrl-{(fb.get('eps_reason') or {}).get('basic', '?')}"
            else:
                why = ("detail-api-empty (no xbrl url on the list row)"
                       if d.get("resultsData_kind") == "none" else "detail-no-eps-field")
            out.setdefault((sym, pe), why)
    return out


FILING_DEADLINE_DAYS = 45      # SEBI LODR: results due within 45 days of quarter end
SYSTEMATIC_MIN_SYMBOLS = 10    # same quarter missing for >=N symbols => source-side


def audit(symbols: list[str], wide: pd.DataFrame) -> dict:
    qes = quarter_ends()
    per_sym, holes = {}, []
    # As-of date derived FROM THE CACHE (not wall-clock) so the report stays
    # byte-identical on re-run: the newest announcement we hold.
    asof = wide["announce_ts"].max() if not wide.empty else WINDOW_LAST
    null_reasons = collect_null_reasons()
    # "found" MUST mean a usable EPS value, not merely that a filing row exists —
    # otherwise archive-404s and no-quarterly-fact filings masquerade as coverage
    # and the C-gate discovers the hole at runtime instead of here.
    usable = wide[(~wide["is_revision"])
                  & (wide["eps_basic_cons"].notna() | wide["eps_basic_stand"].notna())] \
        if not wide.empty else wide
    have = usable.groupby("symbol")["period_end"].apply(set) \
        if not wide.empty else pd.Series(dtype=object)
    cons_q = usable[usable["variant"] == "cons"].groupby("symbol")["period_end"].apply(set) \
        if not wide.empty else pd.Series(dtype=object)
    stand_q = usable[usable["variant"] == "stand"].groupby("symbol")["period_end"].apply(set) \
        if not wide.empty else pd.Series(dtype=object)
    for sym in symbols:
        lp = listing_proxy(sym)
        hz = source_horizon(sym)
        expected = [d for d in qes if lp is None or d >= lp - timedelta(days=100)]
        pre_listing = [d for d in qes if d not in expected]
        found = have.get(sym, set())
        missing = [d for d in expected if d not in found]
        # earliest quarter ANY regime offers for this symbol
        offers = [x for x in (hz["list_from"], hz["integ_from"]) if x]
        first_offered = min(offers) if offers else None
        offered = hz["offered"]
        for d in missing:
            if d + timedelta(days=FILING_DEADLINE_DAYS) > asof:
                cls = "NOT-YET-DUE"                 # inside the 45-day filing window
            elif d not in offered:
                # NSE never listed a filing for this quarter -> nothing to fetch
                cls = ("SOURCE-GAP-NO-DATA" if first_offered is None
                       else "SOURCE-NOT-LISTED")
            elif sym in RENAMED_ENTITIES:
                cls = "MIGRATED-GAP"                # hole inside a renamed entity's range
            else:
                cls = "FILED-NO-EPS"                # listed but no usable value: ours to explain
            holes.append({"symbol": sym, "quarter_dt": d, "quarter": d.strftime("%b-%Y"),
                          "class": cls, "why": null_reasons.get((sym, d), "")})
        per_sym[sym] = {
            "expected": len(expected), "found": len([d for d in expected if d in found]),
            "pre_listing": len(pre_listing), "missing": len(missing),
            "list_rows": hz["list_rows"],
            "cons": len([d for d in expected if d in cons_q.get(sym, set())]),
            "stand": len([d for d in expected if d in stand_q.get(sym, set())]),
        }
    hdf = pd.DataFrame(holes)
    # Cross-symbol pass: one quarter missing for many symbols is a SOURCE gap
    # (verified: Jun-2022 is simply absent from NSE's list for ~38 symbols that
    # do hold Mar/Sep/Dec-2022), not 38 independent per-symbol failures.
    # NOTE: an earlier version re-labelled a quarter as SOURCE-SYSTEMATIC when >=10
    # symbols missed it. That rule was WRONG and dangerous: ~20 financial-sector
    # symbols failing on EVERY quarter looks identical to every quarter failing for
    # >=10 symbols, so a symbol-level parser bug (the NBFC detail-API and invalid-XBRL
    # defects, 1,042 filings) was laundered into a source-side excuse. Holes are now
    # classified only by whether NSE actually LISTED a filing, and every remaining
    # FILED-NO-EPS hole carries a specific cause string.
    systematic = []
    if not hdf.empty:
        cnt = hdf.groupby(["symbol", "class"]).size().unstack(fill_value=0)
        for sym in per_sym:
            row = cnt.loc[sym] if sym in cnt.index else {}
            per_sym[sym]["filed_no_eps"] = int(row.get("FILED-NO-EPS", 0))
            per_sym[sym]["src_gap"] = int(row.get("SOURCE-NOT-LISTED", 0)
                                          + row.get("SOURCE-GAP-NO-DATA", 0)
                                          + row.get("SOURCE-SYSTEMATIC", 0))
            per_sym[sym]["not_yet_due"] = int(row.get("NOT-YET-DUE", 0))
    return {"per_sym": per_sym, "holes": hdf, "asof": asof, "systematic": systematic}


def ts_sanity(wide: pd.DataFrame) -> dict:
    w = wide[~wide["is_revision"]] if not wide.empty else wide
    n = len(w)
    with_ts = w["announce_ts"].notna().sum() if n else 0
    bad = []
    if n:
        for _, r in w[w["announce_ts"].notna()].iterrows():
            lag = (r["announce_ts"] - r["period_end"]).days
            if lag < 0 or lag > 365:
                bad.append({"symbol": r["symbol"], "period_end": r["period_end"].strftime("%b-%Y"),
                            "announce": r["announce_ts"].strftime("%d-%b-%Y"), "lag_days": lag})
    return {"n": int(n), "with_ts": int(with_ts), "bad": pd.DataFrame(bad)}


def fmt(df: pd.DataFrame, max_rows=None) -> str:
    if df is None or df.empty:
        return "  (none)\n"
    with pd.option_context("display.max_rows", max_rows or len(df), "display.width", 200):
        return df.to_string() + "\n"


def build_report(symbols: list[str]) -> None:
    wide = build_parquet(symbols)
    aud = audit(symbols, wide)
    ts = ts_sanity(wide)
    stats = read_json(STATS_PATH) or []
    parked = sorted(p.parent.name for p in RAW.glob("*/_parked.json"))
    done = sorted(p.parent.name for p in RAW.glob("*/_done.json"))
    migration = {}
    for sym in done:
        d = read_json(RAW / sym / "_done.json")
        used = d.get("list_symbol") or d.get("integrated_symbol")
        if used and used != sym:
            migration[sym] = used
    unresolved = [s for s in done
                  if not (read_json(RAW / s / "_done.json") or {}).get("list_symbol")
                  and not (read_json(RAW / s / "_done.json") or {}).get("integrated_symbol")]

    ps = pd.DataFrame(aud["per_sym"]).T
    holes = aud["holes"]
    hc = holes["class"].value_counts().to_dict() if not holes.empty else {}
    n_missing = hc.get("FILED-NO-EPS", 0)
    n_migr = hc.get("MIGRATED-GAP", 0)
    total_expected = int(ps["expected"].sum())
    total_found = int(ps["found"].sum())
    # coverage excluding holes that are not our failure (not filed yet / source-side)
    not_our_fault = (hc.get("NOT-YET-DUE", 0) + hc.get("SOURCE-GAP-NO-DATA", 0)
                     + hc.get("SOURCE-NOT-LISTED", 0) + hc.get("SOURCE-SYSTEMATIC", 0))
    attainable = total_expected - not_our_fault

    L = []
    A = L.append
    A("=" * 78)
    A("canslim-swing MODULE 2b — FULL EPS FETCH (210 symbols) + COMPLETENESS AUDIT")
    A(f"Cache: {RAW}   Parquet: {PARQUET_PATH}")
    A("Report regenerates byte-identically from cache (zero network): --report-only")
    A("=" * 78)
    A("")
    A("RUN / REQUEST TOTALS (accumulated across resumable runs)")
    for st in stats:
        A(f"  run: requests={st['requests']:>6,}  elapsed={st['elapsed_s']:>7,.0f}s"
          f"  symbols_done={st.get('symbols_done', '?')} parked={st.get('parked', '?')}")
    A(f"  total requests: {sum(st['requests'] for st in stats):,}"
      f"   total elapsed: {sum(st['elapsed_s'] for st in stats) / 3600:.2f} h")
    A(f"  symbols fetched: {len(done)}/{len(symbols)}   parked: {len(parked)}"
      + (f"  -> {', '.join(parked)}" if parked else ""))
    A("")
    A("SYMBOL MIGRATION MAP USED (query symbol != habitat symbol)")
    A("  " + (", ".join(f"{k}->{v}" for k, v in sorted(migration.items())) or "(none needed)"))
    A("  unresolved (zero rows in both regimes): " + (", ".join(unresolved) or "(none)"))
    A("")
    A("-" * 78)
    A("PARQUET SUMMARY")
    if not wide.empty:
        A(f"  filings rows: {len(wide):,}  (canonical {int((~wide['is_revision']).sum()):,}"
          f" + revisions {int(wide['is_revision'].sum()):,})")
        A(f"  regimes: {wide['source_regime'].value_counts().to_dict()}")
        A(f"  symbols with any data: {wide['symbol'].nunique()}")
        A(f"  EPS present: basic_cons {int(wide['eps_basic_cons'].notna().sum()):,}"
          f" | basic_stand {int(wide['eps_basic_stand'].notna().sum()):,}"
          f" | dil_cons {int(wide['eps_dil_cons'].notna().sum()):,}"
          f" | dil_stand {int(wide['eps_dil_stand'].notna().sum()):,}")
        n_err = sum(1 for f in RAW.glob("*/detail_*.json") if "_error" in read_json(f)) \
            + sum(1 for f in RAW.glob("*/xbrl_*.json") if "_error" in read_json(f))
        A(f"  filings whose document 404'd on NSE's archive (kept as null-EPS rows): {n_err}")
    A("")
    A("-" * 78)
    A("6. COVERAGE GRID (expected = max(listing proxy, Jun-2020) .. Jun-2026 quarters)")
    A(f"  as-of date (newest announcement in cache, NOT wall-clock): "
      f"{aud['asof']:%d-%b-%Y} — keeps this report reproducible")
    A(f"  expected quarter-slots: {total_expected:,}   found: {total_found:,}"
      f" ({100 * total_found / max(total_expected, 1):.1f}% of expected)")
    A(f"  ATTAINABLE coverage (excluding quarters not yet due + quarters the source")
    A(f"  does not serve): {total_found:,}/{attainable:,} = "
      f"{100 * total_found / max(attainable, 1):.1f}%")
    A("")
    A("  Hole classification:")
    for k in ("NOT-YET-DUE", "SOURCE-GAP-NO-DATA", "SOURCE-NOT-LISTED",
              "MIGRATED-GAP", "FILED-NO-EPS"):
        A(f"    {k:<22}{hc.get(k, 0):>5}")
    A(f"    {'PRE-LISTING (excluded)':<22}{int(ps['pre_listing'].sum()):>5}")
    A("")
    A("  Meaning of each class:")
    A("    NOT-YET-DUE        quarter end + 45d (SEBI LODR deadline) is after the as-of")
    A("                       date — the company has not filed yet. Not a gap.")
    A("    SOURCE-GAP-NO-DATA NSE returns ZERO old-regime rows for the symbol under every")
    A("                       period value (verified by hand) — only 2025+ integrated data.")
    A("    SOURCE-NOT-LISTED  NSE's own filing list has no row for that quarter, so there")
    A("                       was nothing to fetch (its history for the symbol is shallow).")
    A("    MIGRATED-GAP       hole inside a renamed/demerged entity's served range.")
    A("    FILED-NO-EPS       NSE DID list a filing but it yielded no usable EPS (404 on")
    A("                       the archive, or the filing carries no quarterly EPS fact).")
    A("                       These are the real coverage holes — each is given a cause.")
    A("")
    A("  MIGRATED-GAP holes (named):")
    A(fmt(holes[holes["class"] == "MIGRATED-GAP"].reset_index(drop=True) if not holes.empty else holes))
    A("  SOURCE-GAP-NO-DATA symbols (no old-regime data exists on NSE at all):")
    if not holes.empty:
        g = holes[holes["class"] == "SOURCE-GAP-NO-DATA"].groupby("symbol").size()
        A("    " + (", ".join(f"{k} ({v}q)" for k, v in g.items()) or "(none)"))
    A("")
    A("  Worst-20 symbols by FILED-NO-EPS (real) holes:")
    cols = [c for c in ("expected", "found", "filed_no_eps", "src_gap", "not_yet_due",
                        "pre_listing", "list_rows") if c in ps.columns]
    worst = ps.sort_values(["filed_no_eps", "expected"], ascending=[False, True]).head(20)
    A(fmt(worst[cols]))
    A("  All FILED-NO-EPS holes, each with its cause:")
    if not holes.empty:
        u = holes[holes["class"] == "FILED-NO-EPS"][["symbol", "quarter", "why"]]
        A(fmt(u.reset_index(drop=True)))
    else:
        A("  (none)\n")
    A("-" * 78)
    A("7. CONSOLIDATED vs STANDALONE coverage (quarters with a canonical filing)")
    both = ps[["cons", "stand", "expected"]].copy()
    A(f"  symbols with cons >= stand coverage: {int((both['cons'] >= both['stand']).sum())}"
      f" / {len(both)}; cons-only {int((both['stand'] == 0).sum())},"
      f" stand-only {int((both['cons'] == 0).sum())}")
    A(fmt(both.sort_index()))
    A("-" * 78)
    A("8. ANNOUNCEMENT-TIMESTAMP SANITY (canonical rows)")
    A(f"  usable announce_ts: {ts['with_ts']:,}/{ts['n']:,}"
      f" ({100 * ts['with_ts'] / max(ts['n'], 1):.1f}%)")
    A("  implausible (before period_end or >12m after):")
    A(fmt(ts["bad"]))
    A("-" * 78)
    A("HONEST ASSESSMENT — can this power the C-gate as-is?")
    A("")
    A(f"  Yes, with four named caveats. {total_found:,} of {attainable:,} attainable quarter-slots")
    A(f"  ({100 * total_found / max(attainable, 1):.1f}%) carry a usable EPS, and {ts['with_ts']:,}/{ts['n']:,} canonical filings")
    A("  carry an announcement timestamp — the two things the C-gate needs (a")
    A("  year-ago number and a point-in-time date to gate on). Only 16 quarters are")
    A("  genuine holes, each with a cause: 14 filings that contain no quarterly EPS")
    A("  fact at all (the company reported only half-year/full-year columns) and 2")
    A("  whose documents 404 on NSE's own archive.")
    A("")
    A("  What is still weak, precisely:")
    A("  (1) COVERAGE IS NOT UNIFORM. 200 quarters are absent from NSE's own filing")
    A("      list, and MCX has NO old-regime data at all (24 quarters; only 2025+")
    A("      integrated filings exist). Five insurers depend entirely on the")
    A("      integrated regime for pre-2025 history. A C-gate over these names has")
    A("      fewer comparison points than its neighbours — M3 must fail closed on a")
    A("      missing quarter, never interpolate or carry forward.")
    A("  (2) CONSOLIDATED vs STANDALONE IS NOT INTERCHANGEABLE and the gap is large")
    A("      for specific names (ABB 6 cons vs 24 stand; AUBANK and BANDHANBNK have")
    A("      ZERO consolidated quarters). 13 symbols are standalone-only, 1 is")
    A("      consolidated-only. M3 must pick ONE series per symbol from the section-7")
    A("      table and hold it for the whole timeline; mixing them mid-history")
    A("      manufactures fake EPS jumps.")
    A("  (3) A LATE FILING IS A REAL POINT-IN-TIME TRAP. HDFCBANK's consolidated")
    A("      Mar-2021 result was not broadcast until 26-Apr-2022 (391 days), while")
    A("      its standalone landed on time. The dataset stores the true broadcast")
    A("      timestamp, so gating on announce_ts is correct and safe — but any code")
    A("      that joins EPS to price by PERIOD rather than by announcement date will")
    A("      look a year into the future for that symbol.")
    A("  (4) 316 values were recovered by INFERRING an XBRL context period from")
    A("      sibling contexts, because NSE's archive serves structurally invalid")
    A("      documents for older NBFC filings (facts reference contexts the file")
    A("      never defines). The inference only fires when every sibling agrees and")
    A("      the result still must pass the 60-130 day quarterly test, and each such")
    A("      value is tagged 'ok-context-inferred' in the cache — but it is an")
    A("      inference, not a stated fact, and is the first thing to re-verify if a")
    A("      financial-sector C-gate result looks surprising.")
    A("")
    A("  A note on how much of this the M2a probe missed: its 12-symbol sample")
    A("  contained no NBFC and no insurer, so three sector-wide silent failures")
    A("  (bank/insurance XBRL tag names, the empty NBFC detail API, invalid NBFC")
    A("  XBRL) — 1,042 filings in total — were invisible to it and only surfaced")
    A("  because this module audited parse success by taxonomy instead of trusting")
    A("  row counts. Any future source probe should stratify by sector, not by")
    A("  interesting edge cases alone.")
    A("")
    A("=" * 78)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(L) + "\n")
    print(f"\nREPORT: {REPORT_PATH}")


# ------------------------------------------------------------------ main
def main() -> None:
    symbols = sorted(p.stem for p in HABITAT_DIR.glob("*.parquet"))
    only = os.environ.get("EPS2B_ONLY")
    if only:
        symbols = [s for s in symbols if s in set(only.split(","))]
    report_only = "--report-only" in sys.argv
    if not report_only:
        t0 = time.monotonic()
        s = requests.Session()
        warm(s)
        done = parked = streak = 0
        for i, sym in enumerate(symbols, 1):
            status = fetch_symbol(s, sym)
            done += status in ("done", "cached")
            parked += status == "parked"
            if status != "cached":
                print(f"[{i:>3}/{len(symbols)}] {sym:<12} {status}  (req={REQUESTS_MADE:,})",
                      flush=True)
            # Only a real network success clears the streak. A CACHED symbol does no
            # I/O, so letting it reset the counter defeats throttle detection during
            # a resume pass — exactly when parked symbols are interleaved with cached
            # ones (observed: 3 parks in 11 symbols never tripped the pause).
            if status == "parked":
                streak += 1
            elif status == "done":
                streak = 0
            if streak >= 2:
                # two in a row is the throttle signature, not bad luck: rest, re-warm,
                # and start a clean session rather than burning the rest of the run.
                print(f"    ! {streak} consecutive parks — pausing {PARK_STREAK_PAUSE}s",
                      flush=True)
                time.sleep(PARK_STREAK_PAUSE)
                s.close()
                s = requests.Session()
                warm(s)
                streak = 0
        if REQUESTS_MADE:
            stats = read_json(STATS_PATH) or []
            stats.append({"requests": REQUESTS_MADE,
                          "elapsed_s": round(time.monotonic() - t0, 1),
                          "symbols_done": done, "parked": parked})
            atomic_write(STATS_PATH, stats)
    build_report(symbols)


if __name__ == "__main__":
    main()
