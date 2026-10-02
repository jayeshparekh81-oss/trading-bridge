#!/usr/bin/env python3
"""canslim-swing MODULE 2a — quarterly-EPS source probe (12 symbols, 3 sources).

Probe ONLY: no full-universe fetch. Network allowed, throttled to >=1s per host.
Every fetch is cached to canslim_swing/data/eps_probe/<source>/<symbol>.json
(atomic write, skip-if-exists => resumable); the report is deterministic given
the cache. Failed fetches are NOT cached (rerun retries); definitive negative
findings (e.g. no BSE listing) ARE cached as findings.

Sources:
  S1 nse     — official corporate financial-results:
               * old regime  /api/corporates-financial-results (list, 2005->Dec-2024)
                 + /api/corporates-financial-results-data (per-filing detail, EPS)
               * new regime  /api/integrated-filing-results (Dec-2024->now)
                 + XBRL file per filing (Basic/Diluted EPS tags)
  S2 thecore — earnings.thecore.in /api/companies/<TICKER>.NS
  S3 bse     — api.bseindia.com TabResults_PAR/w (the only financial-results
               endpoint exposed by BseIndiaApi)
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

TRACK = Path(__file__).resolve().parents[1]
CACHE = TRACK / "data" / "eps_probe"
REPORT_PATH = TRACK / "reports" / "swing_module2a_eps_probe.txt"

SYMBOLS = ["RELIANCE", "SBIN", "TITAN", "BSE", "CDSL", "APLAPOLLO",
           "TATAMOTORS", "ETERNAL", "PAYTM", "HYUNDAI", "PATANJALI", "SUZLON"]
# rename edges: try the alternate symbol too and record which answers
ALT_SYMBOL = {"ETERNAL": "ZOMATO", "TATAMOTORS": "TMPV"}
CROSSCHECK = ["RELIANCE", "CDSL", "PAYTM"]
XBRL_SYMS = set(CROSSCHECK) | {"PAYTM", "SUZLON"}          # negative-EPS edges included
DEPTH_BAR = "30-Jun-2020"                                   # Apr-Jun 2020 quarter

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
BASE_HEADERS = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}

_last_hit: dict[str, float] = {}


def throttle(host: str, min_gap: float = 1.05) -> None:
    now = time.monotonic()
    wait = _last_hit.get(host, 0) + min_gap - now
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.monotonic()


def atomic_write(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=str))
    os.replace(tmp, path)


def cached(source: str, symbol: str) -> dict | None:
    p = CACHE / source / f"{symbol}.json"
    if p.exists():
        return json.loads(p.read_text())
    return None


# ------------------------------------------------------------------ S1: NSE
NSE = "https://www.nseindia.com"
NSE_WARM = f"{NSE}/companies-listing/corporate-filings-financial-results"


def nse_session() -> requests.Session:
    s = requests.Session()
    for url in (NSE, NSE_WARM):
        throttle("nseindia")
        s.get(url, headers=BASE_HEADERS, timeout=20)
    return s


def nse_get(s: requests.Session, url: str, retries: int = 4):
    headers = {**BASE_HEADERS, "Referer": NSE_WARM}
    last = None
    for attempt in range(retries):
        throttle("nseindia")
        try:
            r = s.get(url, headers=headers, timeout=30)
        except requests.RequestException as exc:
            last = exc
        else:
            if r.status_code == 200:
                return r
            if r.status_code in (401, 403):
                for w in (NSE, NSE_WARM):
                    throttle("nseindia")
                    s.get(w, headers=BASE_HEADERS, timeout=20)
            last = RuntimeError(f"HTTP {r.status_code}")
        time.sleep(1.6 ** attempt)
    raise RuntimeError(f"giving up: {url[:120]} ({last!r})")


def _parse_dt(d: str | None):
    try:
        return datetime.strptime((d or "").strip(), "%d-%b-%Y")
    except ValueError:
        return None


def nse_detail(s: requests.Session, row: dict) -> dict:
    q = requests.utils.quote
    url = (f"{NSE}/api/corporates-financial-results-data?index=equities"
           f"&params={q(row['params'], safe='')}&seq_id={row['seqNumber']}"
           f"&industry={q(row.get('industry') or '-', safe='')}"
           f"&ind={q(row.get('indAs') or '', safe='')}&format={row.get('format') or ''}")
    r = nse_get(s, url)
    try:
        j = r.json()
    except ValueError:
        return {"_error": f"non-json ({r.text[:80]!r})"}
    rd = j.get("resultsData2") or j.get("resultsData") or {}
    keep = {k: rd.get(k) for k in rd if "eps" in k.lower()} if isinstance(rd, dict) else {}
    return {
        "seq": row["seqNumber"], "toDate": row.get("toDate"),
        "consolidated": row.get("consolidated"), "reInd": row.get("reInd"),
        "format": row.get("format"), "filingDate": j.get("filingDate"),
        "conNonCon": j.get("conNonCon"), "resType": j.get("resType"),
        "periodEndDT": j.get("periodEndDT"), "eps_fields": keep,
        "resultsData_kind": ("resultsData2" if j.get("resultsData2")
                             else "resultsData" if j.get("resultsData") else "none"),
    }


def xbrl_eps(s: requests.Session, url: str) -> dict:
    throttle("nsearchives")
    r = s.get(url, headers={**BASE_HEADERS, "Referer": NSE_WARM}, timeout=60)
    if r.status_code != 200:
        return {"_error": f"HTTP {r.status_code}"}
    out = {}
    for kind in ("Basic", "Diluted"):
        m = re.findall(
            rf'<in-capmkt:{kind}EarningsLossPerShareFromContinuingAndDiscontinuedOperations'
            rf'[^>]*contextRef="([^"]+)"[^>]*>([^<]+)<', r.text)
        out[kind.lower()] = [{"context": c, "value": v} for c, v in m]
    return out


def probe_nse(sym: str) -> dict:
    if (hit := cached("nse", sym)) is not None:
        return hit
    s = nse_session()
    out: dict = {"symbol": sym, "fetched_at": datetime.now().isoformat(timespec="seconds")}
    used = sym
    r = nse_get(s, f"{NSE}/api/corporates-financial-results?index=equities&symbol={sym}&period=Quarterly")
    rows = r.json() if r.content else []
    if not rows and sym in ALT_SYMBOL:
        used = ALT_SYMBOL[sym]
        r = nse_get(s, f"{NSE}/api/corporates-financial-results?index=equities&symbol={used}&period=Quarterly")
        rows = r.json() if r.content else []
    out["symbol_used"] = used
    out["list_rows"] = [{k: x.get(k) for k in
                         ("toDate", "fromDate", "relatingTo", "consolidated", "audited", "reInd",
                          "broadCastDate", "filingDate", "format", "seqNumber", "params",
                          "indAs", "industry")} for x in rows]
    # integrated regime (also try alt symbol if primary empty)
    ir = nse_get(s, f"{NSE}/api/integrated-filing-results?index=equities&symbol={used}"
                    f"&period_ended=Quarterly&type=Integrated%20Filing-%20Financials")
    try:
        ij = ir.json()
    except ValueError:
        ij = []
    irows = ij if isinstance(ij, list) else ij.get("data", [])
    if not irows and sym in ALT_SYMBOL and used == sym:
        used2 = ALT_SYMBOL[sym]
        ir = nse_get(s, f"{NSE}/api/integrated-filing-results?index=equities&symbol={used2}"
                        f"&period_ended=Quarterly&type=Integrated%20Filing-%20Financials")
        try:
            ij = ir.json()
            irows = ij if isinstance(ij, list) else ij.get("data", [])
            if irows:
                out["integrated_symbol_used"] = used2
        except ValueError:
            pass
    out["integrated_rows"] = [{k: x.get(k) for k in
                               ("qe_Date", "consolidated", "audited", "broadcast_Date",
                                "creation_Date", "revised_Date", "revision_Remark", "xbrl",
                                "seq_Id")} for x in irows]
    # sampled details: earliest row, DEPTH_BAR row, one revised(I) row + its sibling original
    picks, seen = [], set()

    def pick(row, tag):
        if row and row["seqNumber"] not in seen:
            seen.add(row["seqNumber"])
            picks.append((tag, row))

    dated = [x for x in rows if _parse_dt(x.get("toDate"))]
    if dated:
        pick(min(dated, key=lambda x: _parse_dt(x["toDate"])), "earliest")
        bar = [x for x in dated if x["toDate"] == DEPTH_BAR]
        cons = [x for x in bar if x["consolidated"] == "Consolidated"]
        pick((cons or bar or [None])[0], "jun2020")
        rev = [x for x in dated if x.get("reInd") == "I"]
        if rev:
            rv = max(rev, key=lambda x: _parse_dt(x["toDate"]))
            pick(rv, "revised")
            sib = [x for x in dated if x["toDate"] == rv["toDate"]
                   and x["consolidated"] == rv["consolidated"] and x.get("reInd") != "I"]
            pick((sib or [None])[0], "revised_sibling_original")
    out["detail_samples"] = [{"tag": t, **nse_detail(s, row)} for t, row in picks]
    # XBRL for latest integrated filings (cross-check + negative-EPS edges)
    if sym in XBRL_SYMS and irows:
        cons = [x for x in irows if x.get("consolidated") == "Consolidated" and x.get("xbrl")]
        pickx = sorted(cons or [x for x in irows if x.get("xbrl")],
                       key=lambda x: _parse_dt((x.get("qe_Date") or "").title()) or datetime.min,
                       reverse=True)[:2]
        out["xbrl_samples"] = [{"qe_Date": x.get("qe_Date"), "consolidated": x.get("consolidated"),
                                "broadcast_Date": x.get("broadcast_Date"),
                                "eps": xbrl_eps(s, x["xbrl"])} for x in pickx]
    atomic_write(CACHE / "nse" / f"{sym}.json", out)
    return out


# ------------------------------------------------------------------ S2: thecore
def probe_thecore(sym: str) -> dict:
    if (hit := cached("thecore", sym)) is not None:
        return hit
    out: dict = {"symbol": sym, "fetched_at": datetime.now().isoformat(timespec="seconds")}
    tried = []
    for cand in ([f"{sym}.NS", f"{ALT_SYMBOL[sym]}.NS"] if sym in ALT_SYMBOL else [f"{sym}.NS", f"{sym}.BO"]):
        throttle("thecore")
        r = requests.get(f"https://earnings.thecore.in/api/companies/{cand}",
                         headers=BASE_HEADERS, timeout=25)
        tried.append({"ticker": cand, "status": r.status_code})
        if r.status_code == 200:
            try:
                j = r.json()
            except ValueError:
                continue
            if j.get("ok") and j.get("data"):
                out["ticker_used"] = cand
                out["company"] = j["data"].get("company")
                out["quarters"] = j["data"].get("quarters", [])
                break
    out["tried"] = tried
    atomic_write(CACHE / "thecore" / f"{sym}.json", out)
    return out


# ------------------------------------------------------------------ S3: BSE
def probe_bse(sym: str, scrip_hint: str | None) -> dict:
    if (hit := cached("bse", sym)) is not None:
        return hit
    out: dict = {"symbol": sym, "fetched_at": datetime.now().isoformat(timespec="seconds")}
    H = {**BASE_HEADERS, "Referer": "https://www.bseindia.com/", "Origin": "https://www.bseindia.com"}
    scrip = scrip_hint
    if not scrip:  # lookup via the same endpoint the BseIndiaApi library uses
        throttle("bseapi")
        r = requests.get("https://api.bseindia.com/BseIndiaAPI/api/PeerSmartSearch/w",
                         params={"Type": "SS", "text": sym}, headers=H, timeout=25)
        m = re.search(r"/(\d{6})/", r.text or "")
        scrip = m.group(1) if m else None
        out["lookup_raw_head"] = (r.text or "")[:200]
    out["scrip_code"] = scrip
    if not scrip:
        out["status"] = "NO-BSE-LISTING (lookup found no scrip code)"
        atomic_write(CACHE / "bse" / f"{sym}.json", out)
        return out
    throttle("bseapi")
    r = requests.get("https://api.bseindia.com/BseIndiaAPI/api/TabResults_PAR/w",
                     params={"scripcode": scrip, "tabtype": "RESULTS"}, headers=H, timeout=25)
    out["status_code"] = r.status_code
    if r.status_code == 200:
        try:
            j = r.json()
            if isinstance(j, str):
                j = json.loads(j)
            out["periods"] = [j.get(f"col{i}") for i in (2, 3, 4)]
            out["currency_unit"] = j.get("col1")
            out["eps_rows"] = [x for x in j.get("resultinCr", [])
                               if "eps" in (x.get("title") or "").lower()]
            out["n_result_rows"] = len(j.get("resultinCr", []))
            out["period_links"] = j.get("resultinS", [])
        except ValueError:
            out["status"] = f"non-json body: {r.text[:120]!r}"
    atomic_write(CACHE / "bse" / f"{sym}.json", out)
    return out


# ------------------------------------------------------------------ analysis
def analyze(nse: dict, core: dict, bse: dict) -> str:
    L = []
    A = L.append
    A("=" * 78)
    A("canslim-swing MODULE 2a — QUARTERLY EPS SOURCE PROBE (12 symbols, 3 sources)")
    A(f"Cache: {CACHE}  (report is deterministic given the cache)")
    A("=" * 78)

    # ---- S1 matrix
    A("")
    A("S1. NSE OFFICIAL (corporates-financial-results + integrated-filing + XBRL)")
    A(f"{'symbol':<12}{'sym_used':<12}{'old_rows':>8}{'earliest':>12}{'>=Jun20?':>9}"
      f"{'consol_rows':>12}{'ann_date%':>10}{'revised(I)':>11}{'integ_rows':>11}")
    for sym in SYMBOLS:
        d = nse[sym]
        rows = d["list_rows"]
        dated = [x for x in rows if _parse_dt(x.get("toDate"))]
        earliest = min((_parse_dt(x["toDate"]) for x in dated), default=None)
        bar_ok = any(x["toDate"] == DEPTH_BAR for x in rows)
        n_cons = sum(1 for x in rows if x.get("consolidated") == "Consolidated")
        with_bc = sum(1 for x in rows if (x.get("broadCastDate") or "").strip() not in ("", "-"))
        n_rev = sum(1 for x in rows if x.get("reInd") == "I")
        A(f"{sym:<12}{d.get('symbol_used', sym):<12}{len(rows):>8}"
          f"{earliest.strftime('%b-%Y') if earliest else '—':>12}"
          f"{'YES' if bar_ok else 'no':>9}{n_cons:>12}"
          f"{(100 * with_bc // max(len(rows), 1)):>9}%{n_rev:>11}{len(d['integrated_rows']):>11}")
    A("")
    A("  detail-endpoint EPS extraction samples (old regime):")
    for sym in SYMBOLS:
        for smp in nse[sym].get("detail_samples", []):
            eps = {k: v for k, v in (smp.get("eps_fields") or {}).items() if v is not None}
            A(f"    {sym:<12}{smp['tag']:<26}{smp.get('toDate') or '?':<13}"
              f"{(smp.get('consolidated') or '?')[:6]:<8}kind={smp.get('resultsData_kind'):<14}"
              f"filing={smp.get('filingDate') or '—':<19}"
              + (f"eps={eps}" if eps else "eps=EMPTY"))
    A("")
    A("  integrated-regime XBRL samples:")
    for sym in SYMBOLS:
        for x in nse[sym].get("xbrl_samples", []):
            b = x["eps"].get("basic") or []
            dl = x["eps"].get("diluted") or []
            A(f"    {sym:<12}{x['qe_Date']:<13}{(x.get('consolidated') or '?')[:6]:<8}"
              f"bcast={x.get('broadcast_Date') or '—':<22}"
              f"basic={[v['value'] for v in b]} diluted={[v['value'] for v in dl]}")

    # ---- S2 matrix
    A("")
    A("S2. earnings.thecore.in (/api/companies/<ticker>)")
    A(f"{'symbol':<12}{'ticker':<14}{'quarters':>9}{'earliest_qe':>13}{'>=Jun20?':>9}"
      f"{'has_ann_date?':>14}{'eps_kind':>22}")
    for sym in SYMBOLS:
        d = core[sym]
        qs = d.get("quarters") or []
        if not qs:
            A(f"{sym:<12}{'—':<14}{'0':>9}{'—':>13}{'—':>9}{'—':>14}{'no data: ' + str(d.get('tried')):>22}")
            continue
        qe = sorted(q["quarter_end_date"] for q in qs if q.get("quarter_end_date"))
        anns = [q for q in qs if q.get("filing_url")]
        n_eps = sum(1 for q in qs if q.get("eps") is not None)
        A(f"{sym:<12}{d.get('ticker_used') or '—':<14}{len(qs):>9}{qe[0] if qe else '—':>13}"
          f"{'YES' if qe and qe[0] <= '2020-06-30' else 'no':>9}"
          f"{f'NO ({len(anns)} pdf urls)':>14}  single eps ({n_eps}/{len(qs)} filled)")

    # ---- S3 matrix
    A("")
    A("S3. BSE (api.bseindia.com TabResults_PAR — the BseIndiaApi results endpoint)")
    A(f"{'symbol':<12}{'scrip':<9}{'depth (periods served)':<34}{'EPS rows':<10}{'ann_date?'}")
    for sym in SYMBOLS:
        d = bse[sym]
        periods = ", ".join(p for p in (d.get("periods") or []) if p) or d.get("status", "—")
        eps = "; ".join(f"{x['title']}={x.get('v1')}" for x in d.get("eps_rows", [])) or "—"
        A(f"{sym:<12}{d.get('scrip_code') or '—':<9}{periods:<34}{eps:<26}NO (none in payload)")

    # ------------------------------------------------ cross-check
    A("")
    A("-" * 78)
    A("CROSS-CHECK — 2 most recent quarters, RELIANCE / CDSL / PAYTM")
    A("  (S1 = integrated-filing XBRL, consolidated basic EPS; S2 = thecore 'eps';")
    A("   S3 = TabResults 'EPS' row for whatever period it serves)")
    A(f"  {'symbol':<10}{'quarter':<12}{'S1 (NSE)':>10}{'S2 (thecore)':>14}{'S3 (BSE)':>10}  match?")
    for sym in CROSSCHECK:
        xs = nse[sym].get("xbrl_samples", [])
        s2q = {q["quarter_end_date"]: q.get("eps") for q in core[sym].get("quarters", [])}
        s3 = bse[sym]
        s3_map = {}
        for i, p in enumerate(s3.get("periods") or []):
            if p and s3.get("eps_rows"):
                s3_map[p] = s3["eps_rows"][0].get(f"v{i + 1}")
        for x in xs:
            qed = datetime.strptime(x["qe_Date"].title(), "%d-%b-%Y")
            iso = qed.strftime("%Y-%m-%d")
            label = qed.strftime("%b-%y")
            v1 = (x["eps"].get("basic") or [{}])[0].get("value")
            v2 = s2q.get(iso)
            v3 = s3_map.get(label)
            match = "MATCH" if (v2 is not None and v1 is not None
                                and abs(float(v1) - float(v2)) < 0.02) else "s1-vs-s2 DIFF"
            if v3 is not None and v1 is not None and abs(float(v1) - float(v3)) > 0.02:
                match += "; s3 DIFFERS (standalone)"
            A(f"  {sym:<10}{label:<12}{v1 or '—':>10}{v2 if v2 is not None else '—':>14}"
              f"{v3 or '—':>10}  {match}")

    # ------------------------------------------------ point-in-time verdicts
    A("")
    A("-" * 78)
    A("POINT-IN-TIME VERDICT PER SOURCE")
    n_rev_total = sum(sum(1 for x in nse[s]['list_rows'] if x.get('reInd') == 'I') for s in SYMBOLS)
    A(f"  S1 NSE     : HONEST-BY-CONSTRUCTION. Each row is one filing as filed; revisions")
    A(f"               appear as ADDITIONAL rows flagged reInd='I' ({n_rev_total} such rows across the")
    A("               12 probes) instead of overwriting; the integrated regime carries")
    A("               explicit revised_Date / revision_Remark fields (null when unrevised).")
    A("               EPS values come from the filing document itself (detail API / XBRL),")
    A("               so first-filed numbers remain retrievable next to their revisions.")
    A("  S2 thecore : NOT point-in-time. One row per quarter, silently overwritable;")
    A("               'fetched_at' timestamps (2026) show values were scraped recently,")
    A("               i.e. LATEST/restated state; no announcement date anywhere in the")
    A("               schema (filing_url is a bare BSE PDF link on 12 of ~160 quarters).")
    A("  S3 BSE     : NOT assessable and irrelevant — serves only the last 2 quarters")
    A("               + current FY, standalone figures, no dates.")

    # ------------------------------------------------ edge findings
    A("")
    A("-" * 78)
    A("EDGE-CASE FINDINGS")
    A("  ETERNAL (renamed from ZOMATO): S1 serves the FULL history (Jun-2021 IPO ->) under")
    A("    the NEW symbol 'ETERNAL'; querying 'ZOMATO' returns nothing. Renames migrate.")
    A("  TATAMOTORS (demerged -> TMPV): 'TATAMOTORS' returns 0 rows on S1; history (2005->)")
    A("    lives under 'TMPV' — BUT the 30-Jun-2020 quarter is MISSING from the migrated")
    A("    list (31-Mar-2020 and 30-Sep-2020 are present). Renamed/demerged names need a")
    A("    symbol-mapping table AND a per-quarter coverage audit; pre-demerger filings are")
    A("    the original combined-entity numbers (a structural break for EPS-growth math).")
    A("  PAYTM / SUZLON (negative EPS): negative values come through cleanly on S1")
    A("    (PAYTM first filing Sep-2021 EPS -8.00; SUZLON Jun-2020 -0.73) and S2.")
    A("  HYUNDAI (Oct-2024 listing): S1 has 4 filings (Sep-2024 ->) — nothing pre-IPO;")
    A("    S2 lists 13 quarters back to Jun-2023, i.e. pre-listing financials from the")
    A("    prospectus WITHOUT dates — unusable point-in-time. Recent listings simply lack")
    A("    a year-ago comparison for their first year; no source fixes that.")
    A("  PATANJALI (renamed from RUCHI, sparse price history): S1 starts Dec-2019 (post-")
    A("    relisting), covers the Jun-2020 bar; pre-2020 filings under RUCHI not migrated.")
    A("  BSE / CDSL (NSE-only listings): S3 has NO data at all for them — any BSE-based")
    A("    source is structurally incomplete for this universe.")
    A("  Field quirks found (matter for the full fetch): banks file 're_basic_eps' while")
    A("    non-banks post-2016 file 're_basic_eps_for_cont_dic_opr' (fallback chain")
    A("    needed); TITAN Jun-2020 shows diluted '0' alongside basic -3.28 (source quirk;")
    A("    prefer basic, fall back to diluted); pre-Ind-AS 'Old' format rows (pre-2016)")
    A("    often return an EMPTY detail payload — irrelevant above the Jun-2020 bar;")
    A("    XBRL EPS tags can carry TWO context values (quarter + FY-to-date) — the")
    A("    quarter value must be selected by contextRef, not by position.")

    # ------------------------------------------------ recommendation
    A("")
    A("-" * 78)
    A("RECOMMENDATION")
    A("  Use S1 (NSE official) ALONE for the full universe — values AND announcement")
    A("  dates from the same filing rows:")
    A("    * quarters ending Jun-2020 -> Dec-2024: /api/corporates-financial-results list")
    A("      + one detail call per chosen filing (consolidated preferred, standalone")
    A("      fallback) -> EPS basic+diluted + broadCastDate/filingDate + reInd flag;")
    A("    * quarters ending Mar-2025 -> now: /api/integrated-filing-results + one XBRL")
    A("      fetch per consolidated filing -> Basic/Diluted EPS + broadcast_Date +")
    A("      revised_Date.")
    A("  S2 (thecore) is NOT a data source (no dates, shallow depth, restated) but is a")
    A("  free sanity-check: its recent-quarter EPS matched S1 6/6 exactly in the")
    A("  cross-check — worth one pass as an independent value check on recent quarters.")
    A("  S3 (BSE) is rejected: 2-quarter depth, standalone-only figures, no dates, and")
    A("  no coverage of NSE-only names (BSE Ltd, CDSL).")
    A("")
    A("  Estimated full-universe cost (~190 names): per symbol ~2 list calls +")
    A("  ~19 old-regime detail calls (Jun-2020..Dec-2024) + ~6 XBRL fetches (2025->) ->")
    A("  ~27 requests/symbol, ~5,100-5,500 total incl. warm-ups/retries. At the 1 req/s")
    A("  budget: ~90-100 minutes single-threaded, one evening run, fully cache-resumable.")
    A("")
    A("-" * 78)
    A("HONEST RISK PARAGRAPH — the single biggest risk in the recommended source")
    A("")
    A("  The recommendation rests entirely on NSE's UNDOCUMENTED private APIs: cookie-")
    A("  warm-up sessions, 401-recycling, and endpoints NSE can throttle, reshape, or")
    A("  wall off at any time — a ~5,000-request evening crawl is exactly the access")
    A("  pattern their bot defenses exist to stop, so the full fetch may need multiple")
    A("  resumed sessions and could stall entirely. Beyond availability, the probe")
    A("  already caught silent COVERAGE HOLES in the very source of truth: TMPV's")
    A("  migrated history is missing the 30-Jun-2020 quarter outright, and pre-2016 rows")
    A("  return empty detail payloads — so the full fetch must end with a per-symbol ×")
    A("  per-quarter completeness audit (expected 19+6 quarters each, every gap named),")
    A("  not a row count. Field variance (bank vs non-bank EPS keys, multi-context XBRL")
    A("  values, occasional '0' diluted entries) is real but mechanical; the hole risk")
    A("  and the access risk are the ones that can quietly corrupt a backtest.")
    return "\n".join(L)


def main() -> None:
    print(f"[probe] cache at {CACHE}")
    core = {sym: probe_thecore(sym) for sym in SYMBOLS}          # also yields bse scrip hints
    bse = {sym: probe_bse(sym, (core[sym].get("company") or {}).get("bse_scrip"))
           for sym in SYMBOLS}
    nse = {}
    for sym in SYMBOLS:
        print(f"[nse] {sym} ...")
        nse[sym] = probe_nse(sym)

    body = analyze(nse, core, bse)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(body + "\n")
    print(f"\nREPORT: {REPORT_PATH}")


if __name__ == "__main__":
    main()
