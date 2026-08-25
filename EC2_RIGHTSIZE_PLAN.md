# EC2 RIGHT-SIZE PLAN — c7i-flex.large → t3.medium

**Status: PREPARATION ONLY.** Everything below was verified READ-ONLY over SSH on 2026-07-31.
**Nothing was changed, stopped, started, or resized.** The resize itself is a **console action for
Jayesh** (my AWS creds are `macmini_backup_reader`, S3-scoped — `ec2:*` is denied).

**Bottom line: this resize is SAFE and simple.** Same architecture, Elastic IP (so the Dhan
whitelist and DNS survive), every container set to auto-restart, and the box is ~98% idle. Expected
saving ≈ **50% of compute** (~$0.086/hr → ~$0.042/hr list ≈ **₹2.5–3k/mo**), plus the retention
change finally taking effect (§4).

---

## 1. RESIZE VALIDITY — ✅ VALID (simple stop → change type → start)

| check | current box | t3.medium | verdict |
|---|---|---|---|
| Architecture | **x86_64** (`uname -m`) | x86_64 | ✅ same — **no AMI change** |
| Hypervisor | Nitro (`systemd-detect-virt: amazon`, c7i-flex is Nitro-only) | Nitro | ✅ |
| Root device | **EBS**, `/dev/nvme0n1p1`, NVMe | EBS/NVMe | ✅ |
| Virtualization | HVM | HVM | ✅ |
| ENA / NVMe drivers | present (NVMe root is mounted and booting) | required | ✅ |
| Instance store | **none** (`lsblk`: only the 100 G EBS) | n/a | ✅ nothing lost on stop |
| vCPU / RAM | 2 / 3.7 GiB usable | 2 / **4 GiB** | ✅ slight RAM *gain* |
| AMI | `ami-05d2d839d4f73aafb` | unchanged | ✅ |

**Flex-family note:** `c7i-flex` is a *constrained-burst* family (sustained ~40% baseline, not
designed for 100% pinning). Moving **off** flex to `t3` has no special restriction — the constraint
would only matter moving *to* a flex type. Both are burstable-style; see §3 for the credit maths.

**t4g/ARM is explicitly NOT this path** — that would require rebuilding every Docker image for
`arm64`. This plan is the simple same-architecture x86 resize.

---

## 2. AUTO-START AFTER STOP/START — ✅ EVERYTHING COMES BACK BY ITSELF

Verified directly:

```
docker           enabled   (systemctl is-enabled)
containerd       enabled
```
| container | restart policy |
|---|---|
| trading_bridge_backend | `unless-stopped` |
| trading_bridge_postgres | `unless-stopped` |
| trading_bridge_redis | `unless-stopped` |
| trading_bridge_celery_worker | `unless-stopped` |
| trading_bridge_celery_beat | `unless-stopped` |
| orderflow_recorder | `unless-stopped` |
| orderflow_depth_recorder | `unless-stopped` |

**All 7 running containers are `unless-stopped`, and Docker itself starts at boot → no manual
start command is required after the resize.**

Supporting checks:
- No systemd unit exists for the app or recorders — **Docker restart policies are the only boot
  mechanism**, and they are correctly set.
- `/etc/fstab` mounts by **LABEL** (`cloudimg-rootfs`, `BOOT`, `UEFI`) — not by device name — so a
  device-name change cannot break the boot.
- Swap is a **file** (`/swapfile`, in fstab), not a partition → survives the resize untouched.
- Clock is UTC and NTP-synchronized → cron timings stay correct.

⚠️ **The one caveat of `unless-stopped`:** if a container is *manually* `docker stop`-ed before the
instance stop, it will **not** come back. All 7 are running right now, so as long as nothing is
manually stopped beforehand, all 7 return. (`docker compose up -d` is the fix if one doesn't.)

---

## 3. RAM & CPU — ✅ 4 GiB IS ENOUGH; t3.large NOT needed

**Memory (live reading):**
```
Mem:   total 3814 MB   used 2163   available 1650   buff/cache 1936
Swap:  total 4095 MB   used 2066   si=0  so=0     ← idle swap, NOT thrashing
```
- t3.medium gives **4096 MB vs 3814 MB today — a small *increase*, not a cut.**
- The 2 GB of swap-in-use looks alarming but `vmstat` shows **si=0 / so=0**: nothing is paging.
  Those are stale pages parked during some earlier peak (likely a backtest or the evening
  pipeline) and never reclaimed across 20 days of uptime. **A stop/start actually clears this.**
- Real working set: backend+Postgres+Redis+Celery ≈ **530 MiB**, plus the two recorders
  (depth ≈ 497 MiB capped at 1000 MiB, recorder ≈ 92 MiB) ≈ **~1.1 GiB of containers**.
  1650 MB available today with all of it running.

**Verdict: t3.medium (4 GiB) is safe. t3.large (8 GiB) is not necessary** — it would double the
cost to solve a problem the data says doesn't exist. If you'd rather have margin for future
backtests, t3.large remains a one-click change later using this same procedure.

**CPU credits (the one thing to sanity-check on a burstable):**
t3.medium earns **576 CPU-credits/day** (24/hr). Estimated daily consumption from the measured
profile — ~2% idle baseline ≈ 55, market hours 13–18% ≈ 108, evening pipeline ~70% for 50 min ≈ 70
— totals **≈ 233 credits/day, well under the 576 earned.** Comfortable margin, and t3 defaults to
**Unlimited mode** (never throttles; a small overage fee only if you exceeded the budget, which
this workload does not).

---

## 4. BONUS: THE RETENTION CHANGE LANDS ON RESTART

`orderflow_engine/config.yaml` on the host now says `retention_days: 4`, but the **running
container still has the baked-in `10`** — config.yaml is not bind-mounted (only `cache/` and
`data/` are) and is read once at startup.

**Starting the instance recreates the containers → they pick up `retention_days: 4`**, and the
next 16:05 IST sweep trims to a 4-day window: an extra **~15–20 GB freed**, bundled in for free.

Current disk after yesterday's cleanup: **57 G used / 40 G free (60%)** — no pressure either way.

---

## 5. STEP-BY-STEP (AWS Console — Jayesh)

**Before you start:** tell me, and I'll take a final pre-flight snapshot of container state so we
can compare after.

1. **(Recommended) Take an EBS snapshot** — EC2 → Volumes → select the 100 GB volume attached to
   `i-0412d8e8e95452004` → *Actions → Create snapshot*. Costs a few rupees; it's your undo button.
   Wait for it to reach `completed`.
2. **Stop the instance** — EC2 → Instances → select `i-0412d8e8e95452004` →
   *Instance state → Stop instance*. Wait for **Instance state = `stopped`** (~1 min).
   *Do not skip the wait — the type cannot be changed while stopping.*
3. **Change the type** — with it still selected → *Actions → Instance settings → Change instance
   type* → choose **`t3.medium`** → **Apply**.
   *(If `t3.medium` isn't listed, the instance isn't fully stopped yet — wait and retry.)*
4. **Start it** — *Instance state → Start instance*. Wait for **Instance state = `running`** and
   **Status checks = 2/2 passed** (~2–3 min).
5. **Confirm the IP did not change** — the Public IPv4 should still read **13.127.224.68**.
   It is an **Elastic IP** (verified: `ipv4-associations: 13.127.224.68`), so it persists across
   stop/start. **If it somehow shows a different IP, stop and tell me before anything else** —
   that would break the Dhan whitelist.
6. **Tell me it's up** — I'll run the SSH verification in §7.

### ROLLBACK (if anything looks wrong)
Identical procedure in reverse — **Stop → Change instance type → `c7i-flex.large` → Start.**
Takes ~5 minutes, no data loss (same EBS volume, same Elastic IP). If the volume itself were ever
damaged, restore the §5.1 snapshot to a new volume.

---

## 6. TIMING — do it market-closed

**Best window: Saturday or Sunday, any time.** Reasons:
- The orderflow recorders capture **09:07–15:35 IST on weekdays** — a resize during that window
  loses that day's tick capture (research data, not money, but avoidable).
- The live money-path webhook only matters 09:15–15:25 IST on trading days.
- The auto-login cron runs **08:30 IST Mon–Fri**; a weekend resize doesn't interact with it.
- Downtime is ~5 minutes total.

**Avoid:** weekday market hours, and 15:50–16:30 IST (the evening pipeline + retention sweep).

---

## 7. WHAT I VERIFY AFTER (SSH, read-only — you just tell me it's started)

1. `curl http://169.254.169.254/.../instance-type` → confirms **t3.medium**.
2. `free -m` → 4 GiB present; swap clean after the fresh boot.
3. `docker ps` → **all 7 containers Up** with `unless-stopped` intact.
4. **Money-path liveness (not assumed — proven):** backend `/health` → `{"status":"ok"}`,
   Postgres `pg_isready` → accepting connections, Redis → `PONG`, and celery worker/beat **logs
   showing tasks actually executing** (the "unhealthy" label is the known cosmetic healthcheck
   bug — I confirm liveness from the logs, not the label).
5. `docker exec orderflow_recorder grep retention_days /app/config.yaml` → should now read **4**.
6. `df -h /` → disk baseline, then confirm the 16:05 IST sweep trims to 4 days.
7. `uptime` / `sar` → new CPU baseline for a follow-up cost check.

---

## 8. NEEDS THE CONSOLE / UNVERIFIABLE BY ME
- **The resize itself** — `ec2:*` denied to my creds; entirely your console action.
- **Actual billing impact** — `ce:GetCostAndUsage` denied. The ~50% figure is list-price based
  (c7i-flex.large ~$0.0856/hr vs t3.medium ~$0.0416/hr in ap-south-1); confirm in Cost Explorer.
- **Whether any Savings Plan / RI is already attached** — if one covers the current type, the
  saving maths changes; check *Billing → Savings Plans* before resizing.
- **EBS volume type** (gp2 vs gp3) — worth checking in the console while you're there; gp3 is
  ~20% cheaper than gp2 for the same size and is a separate free win.

---

### One-line summary for the console session
> Snapshot the volume → Stop → Change instance type to **t3.medium** → Start → confirm IP is still
> **13.127.224.68** and status checks 2/2 → ping me to verify. Rollback = same steps back to
> `c7i-flex.large`. Do it on a weekend.
