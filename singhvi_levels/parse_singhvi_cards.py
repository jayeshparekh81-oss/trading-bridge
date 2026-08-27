#!/usr/bin/env python3
"""Module S1-LOCAL — parse manually-saved zeebiz "Anil Singhvi strategy" pages
into numbers-only S0-schema card JSON. STRICTLY OFFLINE: reads local HTML files
only, makes ZERO network calls (the publisher's robots.txt disallows AI crawling;
the founder saves pages himself in his own browser as a reader).

Input : singhvi_levels/backtest_hist/singhvi_actual/raw_pages/*.htm[l]
Output: .../cards/<YYYY-MM-DD>.json   (one pre-market card per trading day)
        .../manifest.json            (resume state; only new/changed files reparse)

Stores NUMBERS/labels only — never article prose/headlines.
"""

from __future__ import annotations

import argparse
import hashlib
import html as _html
import json
import random
import re
import sys
from datetime import time as dtime
from pathlib import Path

PARSER_VERSION = 2  # bump when extraction logic changes → invalidates cached parses
BASE = Path(__file__).resolve().parent / "backtest_hist" / "singhvi_actual"
RAW = BASE / "raw_pages"
CARDS = BASE / "cards"
MANIFEST = BASE / "manifest.json"

PREMARKET_CUTOFF = dtime(9, 15)  # published strictly before the 09:15 open = card
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


# ── HTML → text ─────────────────────────────────────────────────────────────

def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    raw = _html.unescape(raw)
    raw = raw.replace("–", "-").replace("—", "-").replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"[ \t ]+", " ", raw)


def _n(s: str) -> int:
    return int(s.replace(",", "").strip())


def _range(m: re.Match, a: int, b: int):
    return [_n(m.group(a)), _n(m.group(b))]


# A full index level: comma-grouped (25,475) OR a plain 4-6 digit run (23125),
# with digit boundaries so a comma-less number is never truncated to a prefix.
R = r"(?<!\d)(\d{1,3}(?:,\d{3})+|\d{4,6})(?!\d)"
RNG = R + r"\s*-\s*" + R                        # low-high range


def _targets(seg: str):
    m = re.search(r"targets? of\s+(.+?)(?:[.;]|$)", seg, re.I)
    if not m:
        return []
    return [_n(x) for x in re.findall(R, m.group(1))]


# ── Date + publish time ─────────────────────────────────────────────────────

def detect_datetime(text: str, raw: str):
    """Return (date 'YYYY-MM-DD', published dtime, source) or (None, None, reason)."""
    m = re.search(r"Published:\s*(\d{1,2}):(\d{2})\s*([AP]M)[, ]+([A-Za-z]{3,})\.?\s+(\d{1,2}),\s*(\d{4})", text, re.I)
    if m:
        hh, mm, ap, mon, dd, yy = m.groups()
        hh, mm = int(hh), int(mm)
        if ap.upper() == "PM" and hh != 12:
            hh += 12
        if ap.upper() == "AM" and hh == 12:
            hh = 0
        mon_i = MONTHS.get(mon[:3].lower())
        if mon_i:
            return f"{int(yy):04d}-{mon_i:02d}-{int(dd):02d}", dtime(hh, mm), "published_line"
    # fallback: meta published_time
    m = re.search(r'article:published_time"\s*content="(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})', raw)
    if m:
        y, mo, d, hh, mm = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}", dtime(hh, mm), "meta"
    return None, None, "no_date"


def is_hindi(raw: str, text: str) -> bool:
    if re.search(r'/hindi/', raw) or re.search(r'lang="hi"', raw):
        return True
    if re.search(r'[ऀ-ॿ]', text):  # Devanagari
        return True
    return bool(re.search(r"\bsupport zone, below that\b", text, re.I))


# ── English card parser ─────────────────────────────────────────────────────

def _seg(text: str, start_pat: str, end_pats):
    s = re.search(start_pat, text, re.I)
    if not s:
        return ""
    sub = text[s.end():]
    ends = [re.search(p, sub, re.I) for p in end_pats]
    ends = [e.start() for e in ends if e]
    return sub[:min(ends)] if ends else sub


def parse_english(text: str) -> dict:
    c: dict = {"nifty50": {}, "niftybank": {}, "_flags": []}
    nf, bn = c["nifty50"], c["niftybank"]

    # Support + strong zones (anchored per index)
    m = re.search(r"support for the (?:headline )?Nifty ?50 index(?:[^.]*?)\bat\s+" + RNG +
                  r"\s*levels? and a (strong buy zone|strong(?:er)? support zone) at\s+" + RNG, text, re.I)
    if m:
        nf["support_zone"] = _range(m, 1, 2)
        nf["strong_zone"] = {"label": m.group(3).lower(), "range": _range(m, 4, 5)}
    m = re.search(r"(?:support for the Nifty Bank|For the Nifty Bank[^.]*?support)[^.]*?\bat\s+" + RNG +
                  r"\s*levels? and a (strong buy zone|strong(?:er)? support zone) at\s+" + RNG, text, re.I)
    if m:
        bn["support_zone"] = _range(m, 1, 2)
        bn["strong_zone"] = {"label": m.group(3).lower(), "range": _range(m, 4, 5)}

    # Higher zone + sell/profit-booking/blue-sky (anchored on headline vs banking index)
    for pat in (  # "headline index ... higher zone ..." (Jan) and "higher zone for the headline index ..." (Oct)
        r"headline index[^.]*?higher zone[^.]*?at\s+" + RNG + r"\s*levels? and a (strong sell zone|profit-?booking zone) at\s+" + RNG,
        r"higher zone for the headline index[^.]*?at\s+" + RNG + r"\s*levels? and a (strong sell zone|profit-?booking zone) at\s+" + RNG,
    ):
        m = re.search(pat, text, re.I)
        if m:
            nf["higher_zone"] = _range(m, 1, 2)
            nf["sell_zone"] = {"label": m.group(3).lower(), "range": _range(m, 4, 5)}
            break
    m = re.search(r"banking index[^.]*?higher zone[^.]*?at\s+" + RNG + r"\s*levels?", text, re.I)
    if m:
        bn["higher_zone"] = _range(m, 1, 2)
        tail = text[m.end():m.end() + 160]
        ms = re.search(r"(strong sell zone|profit-?booking zone) at\s+" + RNG, tail, re.I)
        mb = re.search(r"blue-?sky zone.{0,20}?above the\s+" + R + r"\s*mark", tail, re.I)
        if ms:
            bn["sell_zone"] = {"label": ms.group(1).lower(), "range": [_n(ms.group(2)), _n(ms.group(3))]}
        if mb:
            bn["blue_sky_above"] = _n(mb.group(1))

    # Existing long / short SLs
    for side, key in (("long", "existing_long_sl"), ("short", "existing_short_sl")):
        seg = _seg(text, r"existing " + side + r" positions", [r"existing (?:long|short) positions", r"new positions", r"For new positions"])
        mn = re.search(r"Nifty (?:intraday and closing|intraday|closing) stop loss at\s+" + R, seg, re.I)
        mb = re.search(r"Nifty Bank (?:intraday and closing|intraday|closing) stop loss at\s+" + R, seg, re.I)
        if mn:
            nf[key] = _n(mn.group(1))
        if mb:
            bn[key] = _n(mb.group(1))

    # New positions — Nifty block
    nseg = _seg(text, r"new positions in Nifty ?50", [r"new positions in Nifty Bank", r"How to trade", r"Stocks in F&O"])
    _parse_new_positions(nseg, nf, "Nifty")
    # New positions — Nifty Bank block
    bseg = _seg(text, r"new positions in Nifty Bank", [r"How to trade", r"Stocks in F&O", r"ALSO READ"])
    _parse_new_positions(bseg, bn, "Nifty Bank")
    return c


def _parse_new_positions(seg: str, idx: dict, name: str):
    np_: dict = {}
    # Primary (conservative): "The best range to buy/sell <idx> is A-B with a stop loss at S ..." OR "(Buy|Sell) <idx> with a stop loss at S ..."
    m = re.search(r"best range to (buy|sell) " + re.escape(name) + r" is\s+" + RNG + r" with a stop loss at\s+" + R, seg, re.I)
    if m:
        np_["primary"] = {"direction": m.group(1).lower(), "range": [_n(m.group(2)), _n(m.group(3))],
                          "stop_loss": _n(m.group(4)), "targets": _targets(seg[m.start():m.start() + 220])}
    else:
        m = re.search(r"\b(Buy|Sell) " + re.escape(name) + r" with a stop loss at\s+" + R, seg, re.I)
        if m:
            np_["primary"] = {"direction": m.group(1).lower(), "range": None,
                              "stop_loss": _n(m.group(2)), "targets": _targets(seg[m.start():m.start() + 220])}
    # Aggressive buy / sell (may be one or both)
    for mm in re.finditer(r"Aggressive traders (?:can )?(buy|sell) " + re.escape(name) +
                          r" in the\s+" + RNG + r" range with a strict stop loss at\s+" + R, seg, re.I):
        d = mm.group(1).lower()
        np_[f"aggressive_{d}"] = {"range": [_n(mm.group(2)), _n(mm.group(3))],
                                  "stop_loss": _n(mm.group(4)), "targets": _targets(seg[mm.start():mm.start() + 240])}
    ms = re.search(r"blue-?sky zone above the\s+" + R + r"\s*mark", seg, re.I)
    if ms:
        np_["blue_sky_above"] = _n(ms.group(1))
    if np_:
        idx["new_positions"] = np_


# ── Hindi card parser (English zone labels inline) ──────────────────────────

def parse_hindi(text: str) -> dict:
    c: dict = {"nifty50": {}, "niftybank": {}, "_flags": ["hindi_source"]}
    for key, idx in (("Nifty", c["nifty50"]), ("Bank Nifty", c["niftybank"])):
        m = re.search(re.escape(key) + r"\s+" + RNG + r" support zone, below that\s+" + RNG + r" strong Support zone", text, re.I)
        if m:
            idx["support_zone"] = _range(m, 1, 2)
            idx["strong_zone"] = {"label": "strong support zone", "range": _range(m, 3, 4)}
        m = re.search(re.escape(key) + r"\s+" + RNG + r" higher zone, above that\s+" + RNG + r" Profit booking Zone", text, re.I)
        if m:
            idx["higher_zone"] = _range(m, 1, 2)
            idx["sell_zone"] = {"label": "profit booking zone", "range": _range(m, 3, 4)}
        m = re.search(re.escape(key) + r" Intraday SL\s+" + R + r" and Closing SL\s+" + R, text, re.I)
        if m:
            idx["existing_long_sl"] = _n(m.group(1))
            idx["existing_long_closing_sl"] = _n(m.group(2))
    if not c["nifty50"].get("new_positions") and not c["niftybank"].get("new_positions"):
        c["_flags"].append("hindi_new_positions_absent")
    return c


# ── completeness ────────────────────────────────────────────────────────────

def completeness(card: dict) -> list[str]:
    miss = []
    for idx in ("nifty50", "niftybank"):
        d = card.get(idx, {})
        for f in ("support_zone", "higher_zone"):
            if f not in d:
                miss.append(f"{idx}.{f}")
        if "new_positions" not in d:
            miss.append(f"{idx}.new_positions")
    return miss


# ── per-file processing ─────────────────────────────────────────────────────

def process_file(path: Path) -> dict:
    raw = path.read_text(errors="replace")
    text = html_to_text(raw)
    date, pub, dsrc = detect_datetime(text, raw)
    rec = {"file": path.name, "date": date, "published": pub.strftime("%H:%M") if pub else None,
           "date_source": dsrc, "lang": "hi" if is_hindi(raw, text) else "en"}
    if date is None:
        rec["status"] = "failed"; rec["reason"] = "no_date_time_found"
        return rec
    if pub >= PREMARKET_CUTOFF:
        rec["status"] = "excluded_no_premarket"; rec["reason"] = f"published {pub.strftime('%H:%M')} >= 09:15 (recap/intraday variant)"
        return rec
    card = parse_hindi(text) if rec["lang"] == "hi" else parse_english(text)
    miss = completeness(card)
    if "nifty50.support_zone" in miss and "niftybank.support_zone" in miss:
        rec["status"] = "failed"; rec["reason"] = "no card zones found (not a full pre-market card?)"
        return rec
    card = {"date": date, "published_ist": rec["published"], "publish_window": "pre-market",
            "lang": rec["lang"], "source_file": path.name, **card}
    card["_missing"] = miss
    rec["status"] = "parsed"; rec["card"] = card; rec["missing"] = miss
    return rec


def cross_check(a: dict, b: dict) -> list[str]:
    """Compare numeric fields of two cards (same date); return mismatch notes."""
    notes = []
    for idx in ("nifty50", "niftybank"):
        for f in ("support_zone", "higher_zone"):
            va, vb = a.get(idx, {}).get(f), b.get(idx, {}).get(f)
            if va and vb and va != vb:
                notes.append(f"{idx}.{f}: {va} vs {vb}")
    return notes


# ── main ────────────────────────────────────────────────────────────────────

def validate_date(date: str) -> int:
    """Print one parsed card (JSON) next to the numbers found in its source file(s)."""
    card_path = CARDS / f"{date}.json"
    if not card_path.exists():
        print(f"no card for {date} (expected {card_path}). "
              f"Available: {sorted(p.stem for p in CARDS.glob('*.json'))}", file=sys.stderr)
        return 1
    card = json.loads(card_path.read_text())
    print("=" * 68)
    print(f"VALIDATE {date}  (OFFLINE)")
    print("=" * 68)
    print(json.dumps(card, indent=2, ensure_ascii=False))

    sources = card.get("source_files") or [card.get("source_file")]
    parsed_nums = sorted(set(_flatten_numbers(card)))
    raw_nums = sorted(set(n for f in sources if f for n in _raw_card_numbers((RAW / f).read_text(errors="replace"))))
    missing = [n for n in raw_nums if n not in set(parsed_nums)]
    print("\n" + "-" * 68)
    print(f"source file(s): {[f for f in sources if f]}")
    print(f"parsed   ({len(parsed_nums)}): {parsed_nums}")
    print(f"raw-page ({len(raw_nums)}): {raw_nums}")
    print(f"raw numbers NOT captured by parser: {missing or 'none'}")
    if card.get("_missing"):
        print(f"missing fields: {card['_missing']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse manually-saved zeebiz Singhvi cards (offline).")
    ap.add_argument("--validate", metavar="YYYY-MM-DD",
                    help="print one already-parsed card next to its source numbers, then exit")
    args = ap.parse_args()
    if args.validate:
        return validate_date(args.validate)

    CARDS.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"files": {}}
    files = sorted([p for p in RAW.glob("*") if p.suffix.lower() in (".html", ".htm")])

    parsed_recs, excluded, failed = [], [], []
    changed = 0
    per_date: dict[str, list[dict]] = {}

    for p in files:
        h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        prev = manifest["files"].get(p.name)
        if prev and prev.get("hash") == h and prev.get("pv") == PARSER_VERSION:
            rec = prev  # unchanged file + same parser version → reuse (resumable)
        else:
            rec = process_file(p); rec["hash"] = h; rec["pv"] = PARSER_VERSION; changed += 1
            manifest["files"][p.name] = rec
        if rec["status"] == "parsed":
            parsed_recs.append(rec)
            per_date.setdefault(rec["date"], []).append(rec)
        elif rec["status"] == "excluded_no_premarket":
            excluded.append(rec)
        else:
            failed.append(rec)

    # Write one card per date; cross-check when >1 source for a date.
    mismatches = []
    for date, recs in sorted(per_date.items()):
        recs_with_card = [r for r in recs if "card" in r]
        chosen = recs_with_card[0]["card"]
        if len(recs_with_card) > 1:
            for other in recs_with_card[1:]:
                notes = cross_check(chosen, other["card"])
                if notes:
                    mismatches.append({"date": date, "files": [chosen["source_file"], other["card"]["source_file"]], "notes": notes})
            # prefer the more complete card (fewest missing)
            chosen = min((r["card"] for r in recs_with_card), key=lambda cc: len(cc.get("_missing", [])))
            chosen = dict(chosen)
            chosen["source_files"] = [r["card"]["source_file"] for r in recs_with_card]
        (CARDS / f"{date}.json").write_text(json.dumps(chosen, indent=2, ensure_ascii=False))

    manifest["summary"] = {
        "raw_files": len(files), "reparsed_this_run": changed,
        "parsed": len(parsed_recs), "excluded_no_premarket": len(excluded),
        "failed": len(failed), "unique_dates": len(per_date), "mismatches": len(mismatches),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    # ── report ──
    dates = sorted(per_date)
    print("=" * 68)
    print("S1-LOCAL parse report  (OFFLINE — no network)")
    print("=" * 68)
    print(f"raw pages: {len(files)}  | reparsed this run: {changed}  (rest cached/resumed)")
    print(f"cards written: {len(dates)}  | excluded (no pre-market): {len(excluded)}  | failed: {len(failed)}")
    if dates:
        print(f"coverage span: {dates[0]} -> {dates[-1]}  ({len(dates)} card date(s))")
    if excluded:
        print("\nexcluded (variant/recap):")
        for r in excluded:
            print(f"  {r.get('date') or '?'}  {r['file']}  — {r['reason']}")
    if failed:
        print("\nfailed:")
        for r in failed:
            print(f"  {r['file']}  — {r.get('reason')}")
    if mismatches:
        print("\nEng/Hindi cross-check mismatches:")
        for m in mismatches:
            print(f"  {m['date']}: {m['notes']}")

    # validation: up to 5 random parsed cards vs raw numbers in their source file
    sample = random.sample(parsed_recs, min(5, len(parsed_recs))) if parsed_recs else []
    print("\n" + "-" * 68)
    print("VALIDATION — parsed numbers vs raw numbers on the page (numbers only)")
    print("-" * 68)
    for r in sample:
        card = r["card"]
        raw_nums = _raw_card_numbers((RAW / card["source_file"]).read_text(errors="replace"))
        parsed_nums = sorted(set(_flatten_numbers(card)))
        missing_from_parse = [n for n in raw_nums if n not in set(parsed_nums)]
        print(f"\n{card['date']} [{card['lang']}] {card['source_file']}")
        print(f"  parsed  ({len(parsed_nums)}): {parsed_nums}")
        print(f"  raw-page({len(raw_nums)}): {raw_nums}")
        print(f"  raw numbers NOT captured by parser: {missing_from_parse or 'none'}")
        if card.get("_missing"):
            print(f"  missing fields: {card['_missing']}")
    return 0


def _flatten_numbers(obj) -> list[int]:
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.startswith("_") or k in ("date", "published_ist", "publish_window", "lang", "source_file", "source_files"):
                continue
            out += _flatten_numbers(v)
    elif isinstance(obj, list):
        for v in obj:
            out += _flatten_numbers(v)
    elif isinstance(obj, int):
        out.append(obj)
    return out


def _raw_card_numbers(raw: str) -> list[int]:
    """Index-level-magnitude numbers on the page (validation aid only — magnitude
    filter drops nav/PCR/percent noise; real pages may add a few prose spot values)."""
    text = html_to_text(raw)
    nums = [_n(x) for x in re.findall(R, text)]
    return sorted(set(n for n in nums if 10000 <= n <= 100000))


if __name__ == "__main__":
    sys.exit(main())
