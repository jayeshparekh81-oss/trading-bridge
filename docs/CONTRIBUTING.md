# Contributing

This guide is for engineers (internal team or invited external) sending code changes to Trading Bridge / TradeTri. We're small, opinionated, and care a lot about correctness — those constraints shape everything below.

## Before you write code

Before writing code for anything non-trivial:

1. **Open an issue describing the change**, even if you intend to author the PR yourself. The issue is where alignment happens; the PR is where the code lands.
2. **Confirm the change isn't already in flight.** Phase docs in `docs/PHASE_*.md` show recent work; check `git log` on `main` for the last week.
3. **For backend changes touching brokers, kill switch, webhooks, strategy engine, or chart code**: pause and confirm with the maintainer first. These are marked "DO NOT TOUCH" in our internal context because they're load-bearing and changes need extra review.

## Code style

### Python (backend)

- **Black** for formatting, `ruff` for linting, both run via pre-commit.
- **Type hints required** on every public function. Internal helpers don't need them but it's good practice.
- **Async by default** for I/O — use `async def` and `await`; don't mix sync DB calls into async handlers.
- **Pydantic v2** for all request/response models. Keep models close to the endpoint that uses them.
- **SQLAlchemy 2.0 style** — `session.execute(select(...))` not legacy `session.query(...)`.
- **One broker per file** in `backend/app/brokers/`. The `BrokerInterface` ABC is the contract.

### TypeScript (frontend)

- **Prettier** for formatting (no Tailwind plugin — semantic class ordering doesn't help us).
- **ESLint** with the strict-type-checked profile.
- **No `any`** unless you leave a comment justifying it. Prefer `unknown` and narrow.
- **Server components by default** in App Router. Mark client components with `"use client"` explicitly.
- **Strict TS settings**: `noImplicitAny`, `strictNullChecks`, `noUncheckedIndexedAccess` all on.
- **Vitest** for unit tests, `@testing-library/react` for component tests.

### Comments

- Default: **no comments**. Well-named identifiers and types document themselves.
- Write a comment only when the WHY is non-obvious — a hidden constraint, a subtle invariant, a workaround for a specific bug.
- Never write a comment that just restates what the code does.

## Test requirements

PRs without tests will not be merged. The thresholds:

- **Backend**: every new endpoint needs at least one integration test in `backend/tests/integration/`. Unit tests for the business logic in `services/`. Aim for 90%+ branch coverage on new code.
- **Frontend**: every new component with non-trivial logic gets a Vitest test. Pages don't always need tests but should be smoke-tested via the dev server.
- **Phase F indicator additions**: structural tests in `frontend/tests/indicators/` (count, shape, bilingual content). See existing `wave-*-registry.test.ts` for the pattern.
- **No-mock rule for kill switch / broker tests**: integration tests that touch kill-switch or broker logic must run against a real (test) Redis and real (test) Postgres. Mocking these has burned us before.

Run the full suite before pushing:

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm run test
npm run typecheck
npm run lint
```

## Git hygiene

### Branches

- Feature branches off `origin/main`: `feat/<scope>-<short-description>`
- Fixes: `fix/<scope>-<short-description>`
- Docs: `docs/<topic>` or `chore/<topic>`
- One branch per logical change. Don't bundle unrelated work.

### Commits

- **Conventional commit prefix**: `feat`, `fix`, `docs`, `chore`, `test`, `refactor`, `content`.
- **Scope where useful**: `feat(brokers): ...` or `fix(kill-switch): ...`.
- **Per-item commits for content**: each new indicator, FAQ, template gets its own commit. Helps history-bisection later.
- **Co-Authored-By footer** for AI-assisted commits (when applicable).
- Never bundle a "fix typo" with a "rewrite kill switch" commit. Split them.

### Rebase, don't merge

- Before pushing, rebase your branch on top of latest `origin/main`.
- We use a linear history on `main`. Merge commits are noise.
- If rebase has conflicts, resolve them carefully — don't blanket-accept theirs/yours.

### Never force-push to main

- Force-push to `main` is blocked by branch protection. Don't try.
- Force-push to your own feature branches is fine; rebase + force is the normal pattern.

## Pull request process

1. Create the PR from your branch with a descriptive title. Use the PR template:
   - **Summary** — 1-3 bullets
   - **Why** — what problem this solves
   - **Test plan** — checklist of what was verified
   - **Risks** — what could break
2. **CI must pass.** Lint, type-check, tests. We don't merge red builds.
3. **At least one reviewer approval** for non-trivial changes. Trivial = doc typos, single-line bug fix with test.
4. **Squash on merge** — keeps `main` history tidy.
5. The reviewer or author squash-merges; nobody else.

## What we will reject

- PRs that disable tests to make them pass. Fix the underlying issue.
- PRs that add `--no-verify` or skip pre-commit hooks. If the hook fails, fix the cause.
- PRs that introduce a new dependency without justification. Every npm/pip package is supply-chain risk.
- PRs that touch the kill switch, broker code, or webhook flow without explicit pre-approval.
- PRs with unrelated changes bundled together. Split them.
- PRs without tests on new behavior.

## SEBI / compliance constraints

We operate under SEBI rules and have specific code-level guardrails:

- **No return guarantees** — never write code that claims, promises, or implies guaranteed returns.
- **No tip generation** — AlgoMitra and any future AI assistant must REFUSE to predict prices or recommend specific trades.
- **No custody** — funds must never leave the user's broker. Don't add code that holds, transfers, or stores client money.
- **Audit trail** — every state-changing action gets a row in the audit table. Don't add code paths that bypass this.

Violating these isn't just "bad practice" — it's regulatory risk for the company and personal risk for the founder.

## Local development setup

```bash
# Clone
git clone git@github.com:jayeshparekh81-oss/trading-bridge.git
cd trading-bridge

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # Edit secrets
docker-compose up -d postgres redis
alembic upgrade head
python -m scripts.seed_dev
uvicorn app.main:app --reload

# Frontend (in another terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 for the web app and http://localhost:8000/docs for the API.

## Reporting bugs / asking questions

- **Internal team**: just ping the maintainer directly.
- **External contributors**: open a GitHub issue with the bug template. Include the `request_id` from any API response that's relevant.

## Code of conduct (informal)

- Default to kindness in PR reviews. Disagree on substance, not style.
- Don't ship code you wouldn't be willing to maintain at 2am during an incident.
- Honesty over hype. If something doesn't work, say so.
- L&T engineer quality bar: would you be proud to ship this?
