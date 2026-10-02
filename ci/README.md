# CI baseline gate

The CI workflow (`.github/workflows/ci.yml`) is **calibrated green**: it passes
on the repository exactly as it is today, while still catching genuinely new
breakage. It does this without reformatting or touching a single source file.

## What blocks vs. what reports

| Check | Job | Behavior |
|-------|-----|----------|
| `pytest` (backend) | backend | **Blocking** — but only on _new_ failures (see below) |
| `ruff check` | backend | Report-only (`continue-on-error`) |
| `ruff format --check` | backend | Report-only |
| `mypy` | backend | Report-only |
| `eslint` | frontend | Report-only |
| `tsc --noEmit` | frontend | Report-only |
| `prettier --check` | frontend | Report-only |
| `vitest` (frontend) | frontend | **Blocking** — but only on _new_ failures (see below) |

Lint / type / format are report-only on purpose. The current code carries a
legacy backlog (ruff ~353 findings, `mypy strict=true`, eslint 67 errors, tsc
errors in test files, source not Prettier-formatted). Making any of these
blocking today would either require a repo-wide reformat (forbidden) or block
every PR. They run so the backlog is **visible in the logs**, then get
ratcheted to blocking later.

## The pytest baseline gate

`ci/check_pytest_baseline.sh` runs the full backend suite and diffs the set of
failing/erroring test nodeids against the allow-list `ci/known_failures.txt`:

- **New failure** (failing now, not in the allow-list) → exit 1, build fails.
- **Known failure** (failing now, in the allow-list) → tolerated.
- **Fixed** (in the allow-list, now passing) → a `::notice::` reminds you to
  delete that line (which locks the win — it then becomes a hard floor).

Baseline snapshot (captured 2026-05-28, `main @ de8100b`):
`44 failed, 4189 passed, 4 skipped, 1 xfailed` of 4237 collected.

The gate clears pyproject's coverage `addopts` (`-o addopts=""`) so it doesn't
depend on coverage thresholds, and it never trusts pytest's own exit code — it
diffs nodeids. It also hard-fails if pytest produces no recognizable summary
(guards against a collection/import crash masquerading as "0 failures").

### Run it locally

```bash
# from the repo root
PYTEST_BIN=backend/.venv/bin/python ci/check_pytest_baseline.sh
```

### When you fix a known failure

Delete its line from `ci/known_failures.txt`. The gate will then treat any
future regression of that test as new and block it.

### When CI reports a "new" failure that is actually pre-existing

Add the nodeid to `ci/known_failures.txt` with a short justification comment.
Keep the list shrinking, not growing.

## The vitest baseline gate

`ci/check_vitest_baseline.sh` is the frontend twin of the pytest gate. It runs
the full vitest suite and diffs the set of failing test ids against the
allow-list `ci/known_failures_vitest.txt`, on exactly the same contract:

- **New failure** (failing now, not in the allow-list) → exit 1, build fails.
- **Known failure** (failing now, in the allow-list) → tolerated.
- **Fixed** (in the allow-list, now passing) → a `::notice::` reminds you to
  delete that line (which locks the win — it then becomes a hard floor).

Baseline snapshot (captured 2026-08-27, `main @ 0486fe1d`):
`4 failed, 979 passed` of 983 tests across 72 files.

Test ids are `<path-relative-to-frontend>::<full test name>`, e.g.
`tests/templates/TemplateCard.test.tsx::TemplateCard — active-equity state Clone & Use button is enabled and fires onClone`.

The gate runs vitest with both the `default` reporter (so the Actions log stays
readable) and the `json` reporter (which is what it diffs). It never trusts
vitest's own exit code. It hard-fails if no usable JSON report is produced, and
it records a file that fails to import as `<file>::<SUITE-LEVEL FAILURE>` —
without that, a suite that blows up at import time reports zero failed
assertions and would sail through the gate.

Note it runs `vitest run` **without** `--coverage`, so the per-directory
coverage thresholds in `vitest.config.ts` are not part of this gate.

### Run it locally

```bash
# from the repo root (deps must be installed: cd frontend && npm ci)
ci/check_vitest_baseline.sh
```

`npm test` in `frontend/` runs the plain suite without the baseline diff.

### When you fix a known failure

Delete its line from `ci/known_failures_vitest.txt`. The gate will then treat
any future regression of that test as new and block it.

## Ratchet plan (later, separate PRs)

1. Fix or scope `tsc --noEmit` (errors are in `tests/`) → make frontend type
   check blocking.
2. Auto-fix the `ruff --fix` / `eslint --fix` low-risk findings in a dedicated
   formatting-only PR, then make those blocking.
3. Run Prettier write once (dedicated PR), then make `prettier --check`
   blocking.
4. Lower `mypy` from `strict` only where needed, or run it on changed files,
   then make it blocking.
5. Pay down `ci/known_failures.txt` until it is empty, then delete the gate
   script and make `pytest` a plain blocking step.
6. Pay down `ci/known_failures_vitest.txt` (4 entries) the same way, then
   make `vitest run` a plain blocking step.
