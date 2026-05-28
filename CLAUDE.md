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
