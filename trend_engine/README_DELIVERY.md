# Module-0 · NSE Delivery-% DNA

Does NSE **delivery-%** (deliverable qty as a share of traded volume) carry
forward-return information that plain OHLCV does not? This module builds the data
foundation + a clean feature and takes **one honest first look**. It contains
**no strategy, no thresholds, no PF/Sharpe** — that's deliberate and deferred.

Standalone: `requests` + `pandas` + `pyarrow`. No app imports, no creds, no order
paths. Source is the **public** NSE daily archive.

## Pipeline

```bash
# 1. Acquire — loops trading days, caches each raw archive CSV, assembles tidy parquet.
#    Resumable: a cached day is never re-fetched. Holidays 404 → skipped+counted.
python trend_engine/fetch_nse_delivery.py                 # last 3 years (default)
python trend_engine/fetch_nse_delivery.py --years 5       # extend window later
python trend_engine/fetch_nse_delivery.py --dry-run       # plan only

# 2. Feature — corp-action-adjusted returns + self-calibrating delivery spike.
python trend_engine/delivery_feature.py

# 3. First look — coverage + spike-vs-non-spike + decile buckets + early/late split.
python trend_engine/run_delivery_firstlook.py
```

## Artifacts (all under gitignored `data/`)

| file | what |
|------|------|
| `nse_bhav_raw/DDMMYYYY.csv` | per-day raw archive cache (resume source) |
| `nse_delivery.parquet` (+ `.csv`) | tidy table: `date, symbol, prev_close, open, close, ttl_trd_qnty, deliv_qty, deliv_per` |
| `delivery_feature.parquet` | above + `adj_close, ret_1d, fwd_ret_1d, fwd_ret_5d, deliv_pct_60, spike` |
| `delivery_firstlook_report.txt` | captured corp-action scan + EDA report |

## Design decisions worth knowing

- **Universe** — current Nifty-50, hardcoded in `fetch_nse_delivery.py` (auditable,
  no cherry-pick). Survivorship bias accepted for module-0; `TATAMOTORS` ends
  mid-window (2025-26 demerger/rename) → short series, flagged in coverage.
  TODO: point-in-time membership.
- **Delivery source of truth** — `sec_bhavdata_full`'s `DELIV_QTY`/`DELIV_PER`,
  `SERIES == EQ` only.
- **Corp-action hygiene** — `PREV_CLOSE` in this archive is the **raw** prior
  close (verified: NESTLEIND 1:10 split shows `prev_close=27116`, `open=2754`), so
  an un-adjusted split fakes a ~-90% return. We detect the ex-date open-gap and
  back-adjust prior bars **only** on a clean round split/bonus ratio; ambiguous
  gaps are left unadjusted and surface in the ±20% eyeball flag. Delivery-% is a
  ratio (split-neutral); only the **return** series is adjusted.
  - Ratio-alone cannot separate a 1:3 bonus (−25%) from a ~−23% news gap
    (Adani). We keep the conservative table and **flag** rather than mis-adjust:
    `POWERGRID 2023-09-12` (likely 1:3 bonus) and `TATAMOTORS 2025-10-14`
    (demerger) stay unadjusted — ~12 forward-return obs out of 38,352 (0.03%),
    immaterial to the pooled look. TODO: real corporate-actions calendar.
- **Feature** — `deliv_pct_60` = percentile-rank of today's `DELIV_PER` within its
  own trailing 60 trading days (mid-rank / `percentileofscore(kind='mean')`, so a
  flat series sits at 0.5, not a false 1.0). `spike = deliv_pct_60 >= 0.90`
  (top decile vs the stock's OWN recent history — self-calibrating, no magic
  number). Undefined during the 60-day warm-up → `spike` is NA (nullable bool),
  never a silent `False` that would pollute the non-spike baseline.
- **No look-ahead** — the spike flag/percentile use `DELIV_PER` only up to and
  including day `t`; forward returns look strictly at `t+1..t+N`; both are
  computed per-symbol so nothing crosses a symbol boundary.

## Deferred to later modules (TODOs, not done here)

(a) point-in-time universe · (b) real transaction costs · (c) shuffle /
cross-sectional-neutral null test (is any gap just market beta on high-delivery
days?) · (d) any strategy / signal / sizing logic.
