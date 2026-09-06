# CP1 — DATA INVENTORY (counts only; streamed from S3, nothing stored locally)

Source: `s3://tradetri-orderflow-data-383136686940-ap-south-1-an/orderflow/r0/{date}/depth/{SYMBOL}_{security_id}.parquet`
(the real key layout; the task text's `{date}/depth/{INSTRUMENT}.parquet` has no security-id suffix — no such keys exist).
Bucket has 42 date prefixes (2026-07-09 .. 2026-09-04); in the window 2026-07-13 .. 2026-08-17: **26 dates**, and BOTH instruments have a consolidated depth object on every one → **52 objects, 432,940,963 bytes (0.403 GiB), 9,868,480 rows**.
Schema: **66 columns and deepest level 20 confirmed on all 52 objects** (every date, not a 3-date sample). `side` is 0/1; `recorder/depth_schema.py` says SIDE_BID=0, SIDE_ASK=1, and the data agrees on every session: 0 ordering violations (bid price_1 ≥ price_2, ask price_1 ≤ price_2) and bid1 < ask1 at bar end on all but 0–1 bars per session — except 2026-08-17 (below).
Security id in the file name and in the `security_id` column agree on every object; the feed rolled contracts between 07-28 and 07-29: NIFTY_FUT 61093→58072, BANKNIFTY_FUT 61088→58067 (the task's correction, 58067 not 58073, matches the post-roll id). Forward mid changes are computed within a session only, so the roll cannot leak into an outcome.
Leftover intraday `depth/parts/` objects exist on 07-14 (1,946/1,956) and 07-15 BANKNIFTY (10,399); the consolidated object was used, parts ignored.

| date | inst | rows | cols | L | sid | bid rows | bid span (IST) | ask rows | ask span (IST) | parts | bars w/ valid mid (of 4500) | crossed/locked bars |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-07-13 | NIFTY_FUT | 163,246 | 66 | 20 | 61093 | 81,623 | 09:07:57.442–14:33:04.245 | 81,623 | 09:07:57.442–14:33:04.245 | 0 | 3815 | 0 |
| 2026-07-13 | BANKNIFTY_FUT | 162,660 | 66 | 20 | 61088 | 81,330 | 09:07:57.442–14:33:04.245 | 81,330 | 09:07:57.442–14:33:04.245 | 0 | 3814 | 1 |
| 2026-07-14 | NIFTY_FUT | 185,696 | 66 | 20 | 61093 | 92,848 | 09:05:06.637–15:33:17.900 | 92,848 | 09:05:06.637–15:33:17.900 | 1946 | 4487 | 0 |
| 2026-07-14 | BANKNIFTY_FUT | 187,652 | 66 | 20 | 61088 | 93,826 | 09:05:03.633–15:33:16.710 | 93,826 | 09:05:03.633–15:33:16.710 | 1956 | 4500 | 0 |
| 2026-07-15 | NIFTY_FUT | 187,856 | 66 | 20 | 61093 | 93,928 | 09:07:34.755–15:33:04.288 | 93,928 | 09:07:34.755–15:33:04.288 | 0 | 4500 | 0 |
| 2026-07-15 | BANKNIFTY_FUT | 187,220 | 66 | 20 | 61088 | 93,610 | 09:15:00.491–15:33:04.288 | 93,610 | 09:15:00.491–15:33:04.288 | 10399 | 4500 | 1 |
| 2026-07-16 | NIFTY_FUT | 187,616 | 66 | 20 | 61093 | 93,808 | 09:07:46.401–15:33:01.181 | 93,808 | 09:07:46.401–15:33:01.181 | 0 | 4500 | 1 |
| 2026-07-16 | BANKNIFTY_FUT | 187,262 | 66 | 20 | 61088 | 93,631 | 09:07:46.401–15:32:59.603 | 93,631 | 09:07:46.401–15:32:59.603 | 0 | 4500 | 0 |
| 2026-07-17 | NIFTY_FUT | 187,496 | 66 | 20 | 61093 | 93,748 | 09:07:48.459–15:32:56.061 | 93,748 | 09:07:48.459–15:32:56.061 | 0 | 4500 | 0 |
| 2026-07-17 | BANKNIFTY_FUT | 187,024 | 66 | 20 | 61088 | 93,512 | 09:06:46.081–15:32:56.061 | 93,512 | 09:06:46.081–15:32:56.061 | 0 | 4500 | 0 |
| 2026-07-20 | NIFTY_FUT | 187,548 | 66 | 20 | 61093 | 93,774 | 09:07:03.786–15:33:17.001 | 93,774 | 09:07:03.786–15:33:17.001 | 0 | 4500 | 1 |
| 2026-07-20 | BANKNIFTY_FUT | 187,164 | 66 | 20 | 61088 | 93,582 | 09:15:00.396–15:33:15.377 | 93,582 | 09:15:00.396–15:33:15.377 | 0 | 4500 | 0 |
| 2026-07-21 | NIFTY_FUT | 187,752 | 66 | 20 | 61093 | 93,876 | 09:15:00.288–15:33:05.086 | 93,876 | 09:15:00.288–15:33:05.086 | 0 | 4500 | 0 |
| 2026-07-21 | BANKNIFTY_FUT | 187,438 | 66 | 20 | 61088 | 93,719 | 09:10:40.909–15:33:05.086 | 93,719 | 09:10:40.909–15:33:05.086 | 0 | 4500 | 0 |
| 2026-07-22 | NIFTY_FUT | 182,346 | 66 | 20 | 61093 | 91,173 | 09:25:15.212–15:33:23.192 | 91,173 | 09:25:15.212–15:33:23.192 | 0 | 4377 | 0 |
| 2026-07-22 | BANKNIFTY_FUT | 182,400 | 66 | 20 | 61088 | 91,200 | 09:25:15.212–15:33:23.192 | 91,200 | 09:25:15.212–15:33:23.192 | 0 | 4377 | 0 |
| 2026-07-23 | NIFTY_FUT | 187,666 | 66 | 20 | 61093 | 93,833 | 09:07:06.786–15:34:15.796 | 93,833 | 09:07:06.786–15:34:15.796 | 0 | 4500 | 0 |
| 2026-07-23 | BANKNIFTY_FUT | 187,646 | 66 | 20 | 61088 | 93,823 | 09:09:38.123–15:34:14.587 | 93,823 | 09:09:38.123–15:34:14.587 | 0 | 4500 | 0 |
| 2026-07-24 | NIFTY_FUT | 187,210 | 66 | 20 | 61093 | 93,605 | 09:15:00.379–15:33:16.379 | 93,605 | 09:15:00.379–15:33:16.379 | 0 | 4499 | 0 |
| 2026-07-24 | BANKNIFTY_FUT | 187,408 | 66 | 20 | 61088 | 93,704 | 09:07:52.451–15:33:16.379 | 93,704 | 09:07:52.451–15:33:16.379 | 0 | 4499 | 0 |
| 2026-07-27 | NIFTY_FUT | 187,466 | 66 | 20 | 61093 | 93,733 | 09:15:00.286–15:32:59.467 | 93,733 | 09:15:00.286–15:32:59.467 | 0 | 4500 | 0 |
| 2026-07-27 | BANKNIFTY_FUT | 187,652 | 66 | 20 | 61088 | 93,826 | 09:10:32.549–15:32:59.467 | 93,826 | 09:10:32.549–15:32:59.467 | 0 | 4500 | 0 |
| 2026-07-28 | NIFTY_FUT | 186,912 | 66 | 20 | 61093 | 93,456 | 09:07:24.551–15:33:10.153 | 93,456 | 09:07:24.551–15:33:10.153 | 0 | 4499 | 0 |
| 2026-07-28 | BANKNIFTY_FUT | 187,202 | 66 | 20 | 61088 | 93,601 | 09:07:24.376–15:33:10.153 | 93,601 | 09:07:24.376–15:33:10.153 | 0 | 4500 | 0 |
| 2026-07-29 | NIFTY_FUT | 149,838 | 66 | 20 | 58072 | 74,919 | 09:07:55.580–14:14:16.586 | 74,919 | 09:07:55.580–14:14:16.586 | 0 | 3590 | 0 |
| 2026-07-29 | BANKNIFTY_FUT | 149,468 | 66 | 20 | 58067 | 74,734 | 09:07:55.580–14:14:16.586 | 74,734 | 09:07:55.580–14:14:16.586 | 0 | 3590 | 1 |
| 2026-07-30 | NIFTY_FUT | 188,334 | 66 | 20 | 58072 | 94,167 | 09:07:42.522–15:33:07.381 | 94,167 | 09:07:42.522–15:33:07.381 | 0 | 4500 | 1 |
| 2026-07-30 | BANKNIFTY_FUT | 187,984 | 66 | 20 | 58067 | 93,992 | 09:15:00.180–15:33:07.381 | 93,992 | 09:15:00.180–15:33:07.381 | 0 | 4500 | 0 |
| 2026-07-31 | NIFTY_FUT | 199,406 | 66 | 20 | 58072 | 99,703 | 09:07:55.459–15:33:06.460 | 99,703 | 09:07:55.459–15:33:06.460 | 0 | 4500 | 0 |
| 2026-07-31 | BANKNIFTY_FUT | 198,966 | 66 | 20 | 58067 | 99,483 | 09:07:55.459–15:33:06.460 | 99,483 | 09:07:55.459–15:33:06.460 | 0 | 4500 | 0 |
| 2026-08-03 | NIFTY_FUT | 222,904 | 66 | 20 | 58072 | 111,452 | 09:07:16.434–15:35:04.434 | 111,452 | 09:07:16.434–15:35:04.434 | 0 | 4500 | 0 |
| 2026-08-03 | BANKNIFTY_FUT | 223,018 | 66 | 20 | 58067 | 111,509 | 09:07:16.434–15:35:04.434 | 111,509 | 09:07:16.434–15:35:04.434 | 0 | 4500 | 0 |
| 2026-08-04 | NIFTY_FUT | 189,824 | 66 | 20 | 58072 | 94,912 | 09:07:10.535–15:35:02.399 | 94,912 | 09:07:10.535–15:35:02.399 | 0 | 4500 | 0 |
| 2026-08-04 | BANKNIFTY_FUT | 189,754 | 66 | 20 | 58067 | 94,877 | 09:07:10.535–15:35:02.399 | 94,877 | 09:07:10.535–15:35:02.399 | 0 | 4500 | 0 |
| 2026-08-05 | NIFTY_FUT | 190,756 | 66 | 20 | 58072 | 95,378 | 09:07:14.502–15:35:04.702 | 95,378 | 09:07:14.502–15:35:04.702 | 0 | 4500 | 0 |
| 2026-08-05 | BANKNIFTY_FUT | 190,622 | 66 | 20 | 58067 | 95,311 | 09:07:14.502–15:35:04.702 | 95,311 | 09:07:14.502–15:35:04.702 | 0 | 4500 | 0 |
| 2026-08-06 | NIFTY_FUT | 190,402 | 66 | 20 | 58072 | 95,201 | 09:07:45.627–15:35:01.209 | 95,201 | 09:07:45.627–15:35:01.209 | 0 | 4500 | 0 |
| 2026-08-06 | BANKNIFTY_FUT | 190,078 | 66 | 20 | 58067 | 95,039 | 09:07:45.627–15:35:01.209 | 95,039 | 09:07:45.627–15:35:01.209 | 0 | 4500 | 0 |
| 2026-08-07 | NIFTY_FUT | 225,640 | 66 | 20 | 58072 | 112,820 | 09:07:58.384–15:35:00.583 | 112,820 | 09:07:58.384–15:35:00.583 | 0 | 4500 | 0 |
| 2026-08-07 | BANKNIFTY_FUT | 225,350 | 66 | 20 | 58067 | 112,675 | 09:07:58.384–15:35:00.583 | 112,675 | 09:07:58.384–15:35:00.583 | 0 | 4500 | 0 |
| 2026-08-10 | NIFTY_FUT | 219,428 | 66 | 20 | 58072 | 109,714 | 09:07:42.470–15:35:00.074 | 109,714 | 09:07:42.470–15:35:00.074 | 0 | 4500 | 0 |
| 2026-08-10 | BANKNIFTY_FUT | 218,914 | 66 | 20 | 58067 | 109,457 | 09:07:42.470–15:35:00.074 | 109,457 | 09:07:42.470–15:35:00.074 | 0 | 4500 | 0 |
| 2026-08-11 | NIFTY_FUT | 196,766 | 66 | 20 | 58072 | 98,383 | 09:07:38.595–15:35:01.004 | 98,383 | 09:07:38.595–15:35:01.004 | 0 | 4498 | 0 |
| 2026-08-11 | BANKNIFTY_FUT | 196,454 | 66 | 20 | 58067 | 98,227 | 09:07:38.595–15:35:01.004 | 98,227 | 09:07:38.595–15:35:01.004 | 0 | 4498 | 0 |
| 2026-08-12 | NIFTY_FUT | 190,682 | 66 | 20 | 58072 | 95,341 | 09:07:07.598–15:35:00.198 | 95,341 | 09:07:07.598–15:35:00.198 | 0 | 4500 | 0 |
| 2026-08-12 | BANKNIFTY_FUT | 190,252 | 66 | 20 | 58067 | 95,126 | 09:07:07.598–15:35:00.198 | 95,126 | 09:07:07.598–15:35:00.198 | 0 | 4500 | 0 |
| 2026-08-13 | NIFTY_FUT | 190,762 | 66 | 20 | 58072 | 95,381 | 09:07:59.422–15:35:01.026 | 95,381 | 09:07:59.422–15:35:01.026 | 0 | 4500 | 0 |
| 2026-08-13 | BANKNIFTY_FUT | 190,502 | 66 | 20 | 58067 | 95,251 | 09:07:59.422–15:35:01.026 | 95,251 | 09:07:59.422–15:35:01.026 | 0 | 4500 | 0 |
| 2026-08-14 | NIFTY_FUT | 189,876 | 66 | 20 | 58072 | 94,938 | 09:15:00.382–15:35:01.580 | 94,938 | 09:15:00.382–15:35:01.580 | 0 | 4500 | 0 |
| 2026-08-14 | BANKNIFTY_FUT | 189,738 | 66 | 20 | 58067 | 94,869 | 09:07:29.774–15:35:01.580 | 94,869 | 09:07:29.774–15:35:01.580 | 0 | 4500 | 0 |
| 2026-08-17 | NIFTY_FUT | 172,190 | 66 | 20 | 58072 | 86,095 | 09:48:23.211–15:35:01.395 | 86,095 | 09:48:23.211–15:35:01.395 | 0 | 4074 | 3371 |
| 2026-08-17 | BANKNIFTY_FUT | 173,034 | 66 | 20 | 58067 | 86,517 | 09:48:23.211–15:35:01.395 | 86,517 | 09:48:23.211–15:35:01.395 | 0 | 4099 | 4099 |

Coverage is visible and uneven: 07-13 ends 14:33, 07-29 ends 14:14, 08-17 starts 09:48, 07-22 starts 09:25; most sessions cover 09:05–15:33.

## 2026-08-17 — present but UNUSABLE as recorded (both instruments)
Ask side (side=1) carries **negative prices** (direct count): NIFTY_FUT price_1..price_6 < 0 on 70,193 of 86,095 ask rows (sample value −97.5; price_20 > 0 on all rows); BANKNIFTY_FUT price_1 < 0 on all 86,517 ask rows (sample −800.0; price_5, price_6, price_20 > 0). Bid side: 0 negative on either instrument. Consequence at bar end: bid1 ≥ ask1 ("crossed/locked") on 3,371 of 4,074 valid-mid bars (NIFTY) and 4,099 of 4,099 (BANKNIFTY); BANKNIFTY ask refills = 0. A mid-price cannot be formed from that book. **Excluded** from every later checkpoint. The background note "schema verified at both ends (07-13 and 08-17)" is true of the schema (66 cols, L20) but not of the values on 08-17.

## Disk
Free on the data volume BEFORE any read: 10.96 GiB of 228.3 GiB = **4.80%** — already below the 15% line before this run touched anything. Bytes needed locally for the raw tape: **0** (every object was streamed with pyarrow's S3 filesystem and never written to disk; verified: 0 raw parquet under the run directory). Outputs written by this run so far: 52 feature parquet = 4.4 MB. Free after: 10.28 GiB = 4.50%. Nothing was deleted, nothing will be. The gate text ("free disk after pull would drop below 15%") is about the pull's effect; this run pulls nothing, and the machine's pre-existing 4.8% is reported here as a machine-state finding, not softened.

## Self-check
`self-check found`: the first re-list compared against the wrong path segment (`r0` instead of the date) and re-listed 0 objects; `fixed by` indexing segment 3 and re-running: **52/52 re-listed, 0 missing, 0 size mismatch**, 0 raw parquet on local disk.

## Gate
Usable sessions with BOTH instruments: **25** (26 present − 08-17) ≥ 10 → GREEN on count. Disk: 0 bytes pulled; pre-existing 4.8% free reported. **CP1 GREEN** (with the disk state flagged).
