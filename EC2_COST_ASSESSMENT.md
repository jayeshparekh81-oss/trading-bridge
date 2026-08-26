# EC2 COST + RIGHT-SIZING ASSESSMENT (READ-ONLY, 2026-07-31)

Assessed live over SSH; **nothing was changed, stopped, resized or restarted.** Context: solo
founder, **zero customers**; the only genuinely always-on need today is Jayesh's own BSE trading
path. Platform + research are not 24/7-critical.

---

## 1. THE INSTANCE

| | |
|---|---|
| Type | **c7i-flex.large** (Intel Xeon Platinum 8488C, x86_64) |
| vCPU / RAM | **2 vCPU / 3.7 GiB** |
| Disk | **96 GB root EBS — 77 G used, 19 G free (81%)** |
| Region / AZ | ap-south-1a (Mumbai) · `i-0412d8e8e95452004` |
| Uptime | 20 days |
| Swap | 4 GiB configured, **1.9 GiB in use** |

*On-demand list price for c7i-flex.large in ap-south-1 is roughly **$0.0856/hr ≈ $62/mo ≈ ₹5.2k/mo**
compute, plus ~96 GB gp3 ≈ **$7.7/mo ≈ ₹650**, so on the order of **₹5–6k/mo** — **UNVERIFIED**, see §5.*

---

## 2. UTILIZATION — the box is ~98% idle

Real `sar` history (sysstat installed; server clock UTC, IST = +5:30), 2026-07-29→31:

| Window (IST) | CPU busy |
|---|---|
| Overnight / pre-open (05:40–09:10) | **~2%** |
| **Market hours (09:40–15:10)** | **13–18%**, one 31% blip |
| **15:40–16:20** | **40–91%** ← the daily spike |
| Post-17:00 → midnight | **~1.5%** |
| Right now (idle) | load **0.02 / 0.03 / 0.05** on 2 vCPU ≈ **1–2%** |

Peak RAM yesterday: **62%**. Live snapshot: 1.9 GiB used / 3.7 GiB, 1.8 GiB available.

**The single daily CPU spike is NOT trading — it's research.** Cron `20 10 * * 1-5` UTC (= 15:50
IST) runs `orderflow_engine make evening-pipeline`; that is the 72–91% burst. The trading path
never exceeds a low teens.

**Verdict: heavily over-provisioned.** Excluding one ~50-minute research job, the machine runs at
**1–18% CPU**. Container snapshot confirms where the weight sits:

| container | CPU | RAM |
|---|---|---|
| orderflow_depth_recorder | 0.00% | **497 MiB** (of a 1000 MiB cap) |
| trading_bridge_celery_worker | 0.03% | 451 MiB |
| orderflow_recorder | 0.00% | 92 MiB |
| trading_bridge_backend | 0.16% | 38 MiB |
| trading_bridge_postgres | 2.8% | **18 MiB** |
| trading_bridge_redis | 2.6% | 7 MiB |
| trading_bridge_celery_beat | 0.00% | 14 MiB |

**The entire live trading path — backend + Postgres + Redis + Celery worker + beat — is ~530 MiB
and ~3% CPU.** The two orderflow recorders (research) are the largest RAM consumers.

---

## 3. WHAT'S RUNNING

**LIGHT (the money path, must stay always-on):** `trading_bridge_backend` (FastAPI webhook),
`trading_bridge_postgres` (pg16), `trading_bridge_redis`, `trading_bridge_celery_worker` +
`_celery_beat`, and the **auto-login cron** `0 3 * * 1-5` UTC (08:30 IST) →
`scripts/auto_login.py`. Plus the new Python bridge (Mac-side today).

**HEAVY / RESEARCH (not customer-facing, not money-path):**
- `orderflow_recorder` + `orderflow_depth_recorder` (containers, 7 days up) — tick/depth capture.
- Cron `20 10 UTC` orderflow **evening-pipeline** ← the 40–91% CPU spike.
- Cron `50 3 UTC` orderflow morning watchdog; `20 3 UTC` singhvi_levels forward-test.
- `/home/ubuntu/btst_backtest` (1.4 G), `ic_backtest` (27 M), `bse_forensics_*`, `orderflow_review`.

⚠️ **Two health flags, unrelated to cost but noticed:** `trading_bridge_celery_beat` and
`_celery_worker` both report **(unhealthy)** — per prior notes this is a mis-configured healthcheck
(curl :8000 on a non-web container), not a real fault, but it means the healthcheck signal is
useless. And **1.9 GiB of swap is in use** despite 1.8 GiB RAM free — worth a look on a 3.7 GiB box.

---

## 4. SEPARATION — yes, and the disk is the real story

**Research and trading share one box, and research dominates every resource:**

| | disk |
|---|---|
| `/home/ubuntu/trading-bridge/orderflow_engine/data` | **57 G** |
| everything else combined (backend, venv, frontend, docs, backups, all research repos) | ~20 G |

Per-day orderflow capture is **5–11 GB/day**, `retention_days: 10` prunes nightly, and **every day
present is already S3-backed** (`backup.json` in each date dir — 2026-07-23 … 07-31 all marked
`S3-backed`). So the 96 GB volume exists **almost entirely to hold ~10 days of research ticks that
are already safely in S3**.

At 81% full with 5–11 GB/day inflow and a 10-day window, headroom is thin — this is the one item
with an operational risk edge, not just a cost one (a full disk previously took the webhook down —
that's the known 9-Jul incident).

---

## 5. THE BILL — **UNVERIFIABLE, needs your console**

Local AWS creds resolve to `arn:aws:iam::383136686940:user/**macmini_backup_reader**`, which is
scoped to S3 backup reads only:
- `ce:GetCostAndUsage` → **AccessDenied**
- `ec2:DescribeInstances` → **UnauthorizedOperation**

So **actual spend, whether it's On-Demand vs Reserved/Savings-Plan, EBS type (gp2/gp3), snapshot
and S3 storage costs, and data-transfer are all UNVERIFIED.** Everything below is sized off list
prices; get the real numbers from Cost Explorer → *Services* + *Reservations* before committing.

---

## RECOMMENDATIONS (ranked by ₹ saved ÷ risk)

### R1 — Shrink the disk *first*: biggest, safest, lowest-effort win
The 96 GB volume is sized for research data that is already in S3. Cutting local retention
(`orderflow_engine/config.yaml: retention_days: 10` → e.g. **3–4**) brings local data to ~20–40 GB
and lets the volume drop toward **30–40 GB**, saving roughly **₹350–450/mo** *and* removing the
disk-full risk. **Caveat:** EBS volumes cannot be shrunk in place — this means creating a smaller
volume and migrating, so treat it as a planned maintenance action, not a quick toggle. Reducing
retention alone (no volume change) is free, instant, reversible, and buys the safety margin today.

### R2 — Right-size the instance: c7i-flex.large → ARM, ~50% off compute
Nothing here needs 2 modern x86 vCPUs. The workload is I/O-light, RAM-modest (peak 62%), and
bursty for <1 hr/day.
- **`t4g.medium`** (2 ARM vCPU, 4 GiB — *more* RAM than today, burstable): ≈ **$24/mo vs ~$62** →
  **~₹3.2k/mo saved**. CPU credits comfortably cover a 1–18% baseline plus a daily burst.
- **`t4g.small`** (2 vCPU, 2 GiB) is cheaper still (~$12/mo) but 2 GiB is tight against the current
  1.9 GiB working set + 497 MiB depth recorder — **only viable if research moves off (R4)**.
- **Effort/risk:** ARM means rebuilding Docker images for `arm64`. Postgres/Redis/Python all have
  clean ARM images; the risk is a stop/start migration window on the live path. Do it on a
  weekend/holiday with a snapshot taken first.

### R3 — Reserved Instance / Savings Plan on whatever stays always-on
Once right-sized, a **1-year no-upfront Compute Savings Plan is ~30–40% off**, 3-year up to ~60%.
On a `t4g.medium` that is ~₹800–1,000/mo more saved. **Do this only after R2** — committing to
today's oversized instance would lock in the waste. (Whether some commitment already exists is
part of what §5 can't see.)

### R4 — Split research off the money-path (the structural fix)
The trading path is **~530 MiB / ~3% CPU**. Research is everything heavy: both recorders, the
evening pipeline (40–91% CPU), and 57 GB of disk.
- **Trading box (always-on, small):** `t4g.small`/`t4g.micro`, or genuinely **₹0 on Oracle Cloud
  Always-Free ARM** (up to 4 ARM cores / 24 GB RAM — far more than needed), or a **$4–6/mo Mumbai
  VPS** (Vultr/DO/Linode). Would need to move: Postgres (a `pg_dump`/restore — the DB is tiny,
  18 MiB resident), Redis, the backend image, the auto-login cron, and the bridge.
- **⚠️ The real blocker is not compute — it's the Dhan IP whitelist.** The broker allowlist is
  pinned to this box's IP (13.127.224.68); any move needs the new static IP whitelisted *and
  verified live* before cutover, and a rollback path. That, plus DNS/TLS for `api.tradetri.com`,
  is the bulk of the migration effort — call it a **half-day of careful work with a real
  cutover risk on a live-money path**, not a casual change.
- **Research box:** run on-demand — start it for the evening pipeline / backtests, stop it
  otherwise. A stopped instance costs only its EBS. Given the pipeline is ~50 min/day, this is
  where the "**spot/on-demand**" saving genuinely applies.
- **NEVER put the live money-path on spot** — spot reclamation mid-session would drop signals.
  Research only.

### R5 — Free housekeeping (do anytime)
`docker system df` shows **1.9 GB reclaimable images + 2.3 GB build cache ≈ 4 GB** recoverable via
`docker system prune` — no cost change, but immediate disk relief on an 81%-full volume.

---

## Suggested order (lowest risk first)
1. **Today, free:** cut `retention_days` 10 → 3–4 and `docker system prune` → ~35–45 GB freed,
   disk-full risk gone.
2. **This week, read-only:** pull real Cost Explorer numbers (needs your console — §5) so R2/R3
   are decided on facts, not list prices.
3. **Planned window:** right-size to `t4g.medium` + shrink the volume (**~₹3.5k/mo**), then apply
   a Savings Plan (**~₹1k/mo more**).
4. **Only if you want the last ₹2–3k:** split research onto an on-demand box and move the trading
   path to a tiny/free host — gated on solving the **Dhan IP whitelist** cleanly.

**Realistic target: ₹5–6k/mo → ₹1–1.5k/mo** (steps 1–3), or **near-₹0 compute** if step 4's
whitelist migration is done carefully. With zero customers, steps 1–3 alone capture most of the
saving at very low risk.

---

### Unverifiable / to confirm
- Actual bill, On-Demand vs Reserved, EBS type, snapshot + S3 storage cost, data transfer (§5).
- Whether any Savings Plan/RI already applies to this account.
- Oracle Always-Free ARM capacity in the Mumbai region (frequently capacity-constrained).
- Exact ap-south-1 prices used above are list-price estimates, not your negotiated/actual rates.
