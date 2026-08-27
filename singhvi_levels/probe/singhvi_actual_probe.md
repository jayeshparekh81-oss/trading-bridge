# Module S0 — Feasibility Probe: Anil Singhvi's published daily levels (zeebiz)

**Date of probe:** 2026-07-31 · **Scope:** READ-ONLY reconnaissance. No backtest, no crawl, no git.
**Method:** search + a handful of polite, spaced, normal-browser page loads (7 zeebiz page reads total).

## VERDICT — **GO** (with scoped caveats)

A real multi-month dataset of Singhvi's *own* published Nifty + Bank Nifty pre-market
day-trading cards is **assemblable and cleanly parseable**. The card is published **pre-market
(~8:57–9:10 AM IST)** as structured, labelled text (support/strong-buy/higher/sell zones +
explicit SL + full target ladders for both indices), and the **format is stable from at least
Oct-2024 → Jan-2026** (identical field layout across a 21-month span). Both English and Hindi
carry it.

**Realistic depth:** confirmed **≥ Oct 2024 (~21 months / ~430 trading days)** at full-card
fidelity; the series clearly extends further back (older articles + a multi-year Hindi video
series exist), but full-card format stability **before Oct 2024 is unverified** — probe 2–3
spaced 2023/2022 dates before committing to a multi-year claim.

**Parsers needed:** (1) an English pre-market "Market Strategy" article parser (primary,
deterministic/regex); (2) a listing enumerator over the paginated topic pages to collect daily
URLs **and filter out non-card variants**; (3) optional Hindi parser as a cross-check.

---

## 1) Archive, URL pattern, cadence, publish time

**Topic/archive listing:** `https://www.zeebiz.com/topics/anil-singhvi-strategy` (paginated 1..5+).

**Article URL pattern** (slug varies, numeric ID at the end):
- 2025–26: `https://www.zeebiz.com/market-news/news-anil-singhvi-market-strategy-<month>-<day>-...-<ID>`
- 2024:    `https://www.zeebiz.com/markets/stocks/news-anil-singhvi-...-<ID>`
- IDs are roughly site-sequential and increment ~daily within the series (Nov-2025 run:
  383635 → 383703 → 383849 → 383941 → 384038 → 384122 → 384226 …), consistent with per-trading-day publishing.

**Cadence:** **Daily, per trading day.** The Nov-2025 stretch is dense and contiguous
(12,13,14,17,19,20,21,24,25,26,27,28, Dec 1,3), with weekends/holidays skipped — the expected
trading-calendar pattern.

**Publish TIME = PRE-MARKET.** Confirmed across dates:
| Date | Article | Published (IST) | Updated |
|---|---|---|---|
| Oct 15, 2024 | Market Strategy (Eng) | **9:07 AM** | 9:10 AM |
| Jan 19, 2026 | Market Strategy (Eng) | **8:57 AM** | 9:20 AM |
| May 13, 2026 | Market Strategy (Hindi) | **8:57 AM** | 9:10 AM |

All before the 09:15 open → usable as a same-day, no-look-ahead signal.

**Format drift:** the core pre-market card is **stable Oct-2024 → Jan-2026** (identical fields).
In 2026 the topic feed ALSO carries non-card variants — mid-session updates and post-market
"final trade" recaps (e.g. Jul-27-2026 id 399437, published **2:49 PM**). These are NOT the
full card (no target ladders) but do recap the morning zones ("What market guru said in
morning"). **The crawler must filter these out** (by publish-time ≈ pre-market and/or by
detecting the target-ladder structure).

**Spaced dates actually fetched:** Jul-27-2026 (intraday variant), Jan-19-2026 (full card),
May-13-2026 (Hindi full card), Oct-15-2024 (full card, oldest checked).

---

## 2) One recent article parsed end-to-end (structured JSON)

Source: `.../news-anil-singhvi-market-strategy-jan-19-...-388113` — **Jan 19, 2026, 08:57 AM IST (pre-market)**.

```json
{
  "date": "2026-01-19",
  "published_ist": "08:57",
  "updated_ist": "09:20",
  "publish_window": "pre-market",
  "source_url": "https://www.zeebiz.com/market-news/news-anil-singhvi-market-strategy-jan-19-how-to-trade-nifty50-nifty-bank-hdfc-bank-icici-bank-today-388113",
  "nifty50": {
    "support_zone": [25475, 25600],
    "strong_support_zone": [25325, 25450],
    "higher_zone": [25665, 25775],
    "strong_sell_zone": [25800, 25900],
    "existing_long_sl": {"intraday": 25600, "closing": 25600},
    "existing_short_sl": {"intraday": 25900, "closing": 25900},
    "new_positions": {
      "primary":    {"direction": "sell", "range": null,           "stop_loss": 25825, "targets": [25600, 25550, 25500, 25475, 25425, 25375]},
      "aggressive": {"direction": "buy",  "range": [25375, 25475],  "stop_loss": 25300, "targets": [25550, 25600, 25625, 25665, 25700, 25735]}
    }
  },
  "niftybank": {
    "support_zone": [59575, 59775],
    "strong_buy_zone": [59325, 59500],
    "higher_zone": [60225, 60425],
    "blue_sky_zone_above": 60500,
    "existing_long_sl": 59700,
    "existing_short_sl": 60250,
    "new_positions": {
      "aggressive_buy":  {"range": [59575, 59800], "stop_loss": 59450, "targets": [60000, 60100, 60150, 60200, 60300, 60425], "blue_sky_above": 60500},
      "aggressive_sell": {"range": [60225, 60425], "stop_loss": 60550, "targets": [60100, 60000, 59800, 59575, 59525, 59450, 59325]}
    }
  },
  "context": {
    "trade_setup": {"global": "negative", "fii": "negative", "dii": "positive", "fno": "neutral", "sentiment": "cautious", "trend": "positive"},
    "pcr": {"nifty": 0.77, "niftybank": 1.12},
    "india_vix": 11.37,
    "fii_long_pct": 9.32
  },
  "stock_calls": [
    {"symbol": "ICICI Bank", "instrument": "futures", "action": "buy", "targets": [1425, 1436, 1450], "stop_loss": 1400},
    {"symbol": "HDFC Bank",  "instrument": "futures", "action": "buy", "targets": [942, 950],          "stop_loss": 917}
  ],
  "fno_ban": {"already": ["Sammaan Capital", "SAIL"], "new": [], "out": []}
}
```

**Parsing ambiguities / notes (real, must handle):**
- **Zones are RANGES** (two levels), never single points → store as `[lo, hi]`.
- **The primary "new position" direction VARIES by day.** Jan-19 led with a **SELL** for Nifty
  (no conservative "best range to buy"); Oct-15-2024 led with a **BUY** ("The best range to buy
  Nifty Bank is 51,475–51,675 …"). The parser must detect direction, not assume buy.
- **Target ladders**: usually 6 targets, occasionally 7 (Bank Nifty sell here had 7).
- **"Blue-sky zone above X"** = open-ended upside marker (no upper bound) — appears intermittently.
- **Numbers are comma-formatted** ("25,475") → strip commas.
- Bank Nifty on this day had **two aggressive** setups (buy + sell) and no single "best range";
  other days label one side "best range to buy/sell" and the other "aggressive". Normalize to
  `{primary, aggressive}` by direction.

---

## 3) Hindi version — parseability

Fetched `.../hindi/stock-markets/trade-setup-13-may-2026-...-255284` (May-13-2026, **08:57 AM**).
The Hindi article is **also a full card and equally parseable — arguably more explicitly
tagged**, because the level labels are written **in English inside the Hindi prose**:

- `Nifty 23150-23250 support zone, below that 23000-23125 strong Support zone`
- `Nifty 23465-23600 higher zone, above that 23675-23800 Profit booking Zone`
- `Bank Nifty 53025-53275 support zone, below that 52600-52775 strong Support zone`
- `Bank Nifty 54225-54450 higher zone, above that 54550-54775 Profit booking Zone`
- `Nifty Intraday SL 23300 and Closing SL 23125` …

**Which is more parseable:** roughly equal. English "Market Strategy (Date)" articles give the
cleanest **prose target-ladder** ("… for targets of A, B, C …"); Hindi gives the cleanest
**inline zone labels**. Recommendation: **English as the primary parser**, Hindi as a
cross-validation / gap-filler when an English day is missing. Note Hindi also has **video-only**
variants (`/hindi/india/video-...`) that carry no text card — filter those out.

---

## 4) Coverage estimate

- **Cards/week:** ~5 (one per trading day); dense and contiguous where sampled.
- **Visible gaps:** weekends + exchange holidays (expected, not data loss). No evidence of
  missing trading-day cards in the Nov-2025 sample.
- **Format changes:** core pre-market card **stable Oct-2024 → 2026**. The main risk is
  **variant contamination in 2026** (intraday + "final trade" articles share the topic tag) —
  a filtering problem, not a parsing-format problem. Pre-Oct-2024 fidelity: **unverified**.

---

## 5) What to build (if GO proceeds — NOT in this module)

1. **Listing enumerator** over `topics/anil-singhvi-strategy` pagination → daily article URLs,
   filtering to pre-market full-card articles (publish-time ≈ 08:45–09:12 AM and/or
   target-ladder present).
2. **English card parser** (deterministic regex on labelled sentences) → the JSON schema above.
3. **Hindi parser** (cross-check / backfill) reusing the same numeric extraction.
4. **Politeness for the eventual backfill crawl** (rate-limit, cache, resume) — explicitly out
   of scope here; this probe made only spaced single reads.
5. **Before multi-year claims:** probe 2–3 spaced 2023/2022 dates to confirm format stability
   deeper than Oct-2024.

## Isolation / acceptance
- Wrote ONLY this file under `singhvi_levels/probe/`. No other files, no git, no branch change.
- Prod / research (`/home/ubuntu/trading-bridge-research`, crontabs, jobs) untouched.
- Fetches: 2 web searches + 7 spaced normal-browser page reads of zeebiz.com. No bulk crawl.
- Extracted **facts (numeric levels)** only; no substantial verbatim article prose reproduced.
```
