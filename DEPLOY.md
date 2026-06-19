# Deploy & Cutover Runbook

> Production runs the **live real-money BSE Ltd strategy `89423ecc`** (and CDSL
> `0252e82c`) on Dhan. Treat every step here as touching real money. When unsure,
> STOP and ask. See `CLAUDE.md` for the protected-zone rules.

Host: EC2 `13.127.224.68`, stack at `/home/ubuntu/trading-bridge`
(`docker compose`, containerd image store). Backend on port 8000.

---

## Source of truth

- **Prod now deploys from `main`** via an **immutable release tag**.
  - Current live tag: **`release-cutover-14`** → `a440f68` (B1 billing; alembic
    head `031_subscription_plans`; deployed 2026-06-19).
  - Current rollback anchor: image `trading_bridge_backend:pre-cutover-14`
    (= prior cutover-13 backend `9ff168d`). Restore with
    `docker tag …:pre-cutover-14 …:latest && docker compose up -d --no-deps backend celery_worker celery_beat`.
  - Cut a *new* tag for each cutover (`release-cutover-N`); never deploy a moving
    branch.
- The old **`deploy/3fixes_20260524_2121`** branch is **SUPERSEDED**. `main` is a
  strict superset of it (prod tip `837a3fe` is an ancestor of `main`).
- **Retention — keep all three rollback anchors through ONE clean Monday live
  session, then prune:**
  - branch `deploy/3fixes_20260524_2121`
  - rollback image `trading_bridge_backend:b244b4e6` (a.k.a. `:pre-cutover`)
  - git tag `prod-pre-cutover` → `837a3fe`

  Only after a clean Monday open on the new image should these be deleted/pruned.

---

## Cutover steps

Run prep (tag → checkout → build → **arm rollback**) ahead of time; do the
recreate + verify in the live window.

### 1. Tag the release (dev repo)
```bash
git tag release-cutover-N <main-HEAD>
git push origin release-cutover-N
```

### 2. On EC2 — fetch + checkout the tag (does NOT touch running containers)
```bash
cd /home/ubuntu/trading-bridge
git fetch origin --tags
git checkout release-cutover-N
```
If git complains about a locally-modified tracked file, confirm it is
byte-identical to the tag first (`git diff release-cutover-N -- <file>` empty),
then `git checkout -- <file>` and retry. (The `auto_login.py` lowercase-`dhan`
fix is already in `main`, so the tree should be clean.)

### 3. Build the new image (NO recreate)
```bash
docker compose build backend
```
Confirm green: TA-Lib builds from source (v0.6.4), deps install clean. The
running containers keep serving the OLD image.

### 4. ARM ROLLBACK — **before** any recreate
This host uses the **containerd image store**. When the build moves the
`:latest` tag, the old image is left with **no image record** — `docker tag` and
`docker commit` against it both **fail** (`No such image` / `content digest …
not found`). The only faithful capture is `export | import`:

```bash
P=$(docker exec trading_bridge_backend printenv PATH)
docker export trading_bridge_backend \
 | docker import \
     -c "ENV PATH=$P" -c 'WORKDIR /app' -c 'USER appuser' -c 'EXPOSE 8000' \
     -c 'CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--loop","uvloop","--http","httptools","--proxy-headers"]' \
     - trading_bridge_backend:pre-cutover
```
Rules:
- **Bake ONLY `PATH`.** Never bake the 45 runtime env vars / secrets — compose
  re-injects those at `up`.
- `docker export` reads a running container without pausing/restarting it.
- Verify: `docker image inspect trading_bridge_backend:pre-cutover` shows the
  right `Cmd` / `WorkingDir` / `User` / `ExposedPorts`, and an ephemeral
  `docker run --rm …:pre-cutover ls -la /app/app/main.py` shows app code present.

Do not proceed to recreate until `:pre-cutover` exists and is verified.

### 5. Recreate app containers ONLY
```bash
docker compose up -d --no-deps backend celery_worker celery_beat
```
**Leave `postgres` and `redis` untouched.** No migrations at cutover when DB head
already matches `main` head (currently `031_subscription_plans`). When the
cutover *does* carry a new migration, apply it before the recreate with a
transient container: `docker compose run --rm --no-deps backend alembic upgrade head`.

### 6. Verify (empirical — the important part)
- Backend **healthy**; `curl localhost:8000/health` → `{"status":"ok"}`; startup
  logs show **no import/startup and no DB-connection errors**.
- **BSE `89423ecc` loaded, `is_paper=false` intact** (DB).
- **Dhan credential active under lowercase `dhan`**; auth path initializes with
  no error. (Real proof is the next auto_login run — see Token refresh.)
- **Kill switch armed**, daily-loss limit set (`kill_switch_config.enabled=t`,
  `max_daily_loss_inr` for the strategy owner).
- **Webhook registered**: `POST /api/webhook/strategy/{token}` (GET → `405`).
- **Celery worker + beat**: judge by **LOGS** (worker `ready`, tasks
  `succeeded`; beat `Sending due task`) — **NOT** the healthcheck.
- Tail all three containers ~2 min for delayed/runtime errors; `RestartCount=0`.

### 7. Rollback (if anything is genuinely wrong)
Startup error, BSE missing, Dhan auth failure, DB error, or crash loop →
```bash
docker tag trading_bridge_backend:pre-cutover trading_bridge_backend:latest
docker compose up -d --no-deps backend celery_worker celery_beat
```
Restores the live stack on the captured image (`b244b4e6`). Source-level safety
net: git tag `prod-pre-cutover` (`837a3fe`). Then report exactly what failed.

---

## Token refresh (Dhan)

- Cron **`0 3 * * 1-5`** runs `venv/bin/python3 scripts/auto_login.py` on
  **weekdays only**.
- It generates the Dhan TOTP **programmatically** (`pyotp.TOTP(secret).now()`,
  secret from `.env`) → `POST auth.dhan.co/app/generateAccessToken` → writes the
  fresh token under the **lowercase `dhan`** key (deactivate old, insert new).
  Fully automated; **no interactive OTP**.
- Dhan tokens last ~23h30m. **Weekends do not refresh** (expected) — a token
  minted Friday/Saturday lapses before Monday; the **Monday 03:00 cron** delivers
  the open-ready token (well before the 09:15 IST open).
- Manual trigger (e.g. to prove the write-path) = the exact cron command:
  ```bash
  /home/ubuntu/trading-bridge/venv/bin/python3 \
    /home/ubuntu/trading-bridge/scripts/auto_login.py
  ```
  Verify after: exactly one active `dhan` row, advanced `created_at` /
  `token_expires_at`, changed token hash, zero uppercase `DHAN` rows.

The lowercase key matters: the backend reads credentials via
`BrokerName.DHAN == "dhan"`. A token written under `"DHAN"` is invisible to the
live path — this is the bug the lowercase fix closed.

---

## Gotchas

- **Celery `unhealthy` is a false alarm.** The healthcheck `curl`s `:8000` on the
  worker/beat containers, which run no web server. They are fine if their **logs**
  show ready/scheduling. Don't roll back on this.
- **`scripts/auto_login.py` is a HOST script**, outside the Docker build context
  (`build.context: ./backend`). It is NOT in the image — it runs on the EC2 host
  via cron. Edits to it deploy by being on the checked-out tree, not by rebuild.
- **Prod build installs `.` only** (`pip install --prefix=/install "."` in
  `backend/Dockerfile`) — **no `[dev]` / `[crossval]` extras**. So `pandas-ta`
  (now in the `crossval` extra) never enters the prod image; it isn't imported by
  production code. `ta-lib==0.6.4` IS a core dep and is built from source in the
  image.
- **Fyers needs MANUAL login** (refresh-token flow, no daily auto-login). The
  auto_login summary will say `FYERS: MANUAL LOGIN REQUIRED` — that's not a Dhan
  problem and doesn't affect the BSE/Dhan live path.
- **F&O = NRML only.** MIS/INTRADAY is forbidden for futures/options.
- **No market-hours deploys.** Do the recreate outside 09:15–15:25 IST (weekend
  is ideal).
