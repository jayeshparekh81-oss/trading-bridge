# One checkout, two sessions — the procedure

## What went wrong (2026-09-04)

Two Claude sessions shared this working directory. The reflog:

```
c119e127 HEAD@{2026-09-04 21:46:47}: checkout: moving from feat/cutover-26-reprice-rule to feat/customer-lane-full
d66f42d0 HEAD@{2026-09-04 21:49:10}: commit: fix(cutover-26): verifier catches ...
```

A cutover-26 session had uncommitted work in the tree. The customer-lane session
switched the shared checkout to its own branch at 21:46:47. The dirty files came
across (git only refuses a switch that would *overwrite* local changes). 2m23s
later the cutover-26 session committed — onto `feat/customer-lane-full`.

Nothing was lost that time: `d66f42d0` was later also reachable from
`feat/cutover-26-reprice-rule`, which the founder merged to `main` as `fd321aa2`.
**The next occurrence may not be so lucky, and it can carry work in either
direction.**

## The fix: one worktree per session (do this)

```bash
git worktree add ../tb-<task-name> -b feat/<task-name>
cd ../tb-<task-name>
```

Each session gets its own directory and its own HEAD. Branch switches in one
cannot touch another. Remove it when done:

```bash
git worktree remove ../tb-<task-name>
```

Never `git switch` in `~/projects/trading-bridge` while another session is
working there.

## The backstop: hooks that fail closed

Because git has no `pre-checkout` hook, the guard is split in two:

- **`.githooks/post-checkout`** — on a branch switch, records the files that
  came across into `.git/CHECKOUT_CARRIED` and prints a warning. It only
  records; it cannot undo a switch that already happened.
- **`.githooks/pre-commit`** — **refuses** any commit whose staged files
  intersect that carried set, and prints the recovery commands.

Enable (once per clone; it is local config, not committed):

```bash
git config core.hooksPath .githooks
```

### What the guard will and will not do

- It **refuses only**. It never stashes, resets, checks out, or discards
  anything. Your edits stay exactly where they are, still staged.
- It blocks **only** files that were already dirty before the switch.
  Unrelated work on the same branch commits normally.
- It is not a lock. Two sessions writing the *same file* at the *same time*
  is still a race — worktrees are the real fix.

### Deliberate override

If the carried work genuinely belongs on the current branch:

```bash
rm .git/CHECKOUT_CARRIED
```

That is a deliberate act, and the point: the default is refusal.

## Recovery when it fires

```bash
git stash push -m carried -- <the files it named>
git switch <the branch it came from>
git stash pop
git commit ...
```

## Verified

Reproduced the 4 Sep sequence in a throwaway clone: the commit was refused with
exit code 1, the branch stayed at its base commit, the file kept its contents and
stayed staged, and an unrelated commit on the same branch was allowed.
