# TRADETRI — Rules for Claude Code
## PRODUCTION SAFETY (read first)
- BSE Ltd strategy (89423ecc) is LIVE REAL MONEY on Dhan.
- is_paper, strategy_executor, direct_exit.py, webhook, kill_switch,
  broker adapters (dhan.py/fyers.py), strategies migrations:
  NEVER modify without me confirming is_paper=false first.
- FUTURES = NRML only. MIS/INTRADAY forbidden for F&O.
## PROTECTED ZONES (never touch unless I name them)
- R:R block, Brahmastra trail, entry/exit logic, JSON builder.
- Surgical fixes only, zero scope creep. Unsure → STOP and ask.
## WORKFLOW
- One module per task. Never one-shot. Plan first, edit after I approve.
- Work on a branch, never commit to main directly.
- Show actual diff before commit. Run FULL test suite, not subset.
- Two deploy hard-stops max: before migrations, before container restart.
- I gate every deploy. See CONVENTIONS.md for code organization.
## Operating discipline (how to work — minimizes mistakes)
Follow on EVERY task:
1. Read `docs/CUSTOMER_PLATFORM.md` (for customer-platform work) + the relevant code BEFORE writing anything — understand current state first.
2. New branch per task; never commit to `main`; never deploy without explicit founder approval (reinforces WORKFLOW above).
3. Scope tightly — change only what the task asks: no drive-by refactors, no mass reformatting, no touching unrelated files (extends PROTECTED ZONES' "surgical, zero scope creep").
4. Never touch sacred files without explicit authorization (the list lives in PRODUCTION SAFETY + PROTECTED ZONES).
5. VERIFY before claiming done — run existing tests + lint and confirm the change actually does what was asked; never assert "fixed/working" on assumption.
6. Report HONESTLY — what you did, what you did NOT do, any failures, any pre-existing issues (clearly separated from your changes), anything uncertain. Never hide or gloss a failure.
7. If a task is ambiguous, or would touch a sacred / live-money path, STOP and ask — don't guess (see PROTECTED ZONES' "Unsure → STOP and ask").
8. Small, reviewable changes — one logical change per branch.
## PROJECT DOCS
- Customer-platform work → read docs/CUSTOMER_PLATFORM.md first.
