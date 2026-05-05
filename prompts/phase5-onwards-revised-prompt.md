You are a senior full-stack architect, trading systems engineer, quantitative backtesting engineer, AI product designer, QA lead, and codebase integration expert.

 

I am working on an existing live project called "Tradetri" at www.tradetri.com.

 

This is an existing production project, NOT a new project.

 

Current project status:

Phases 1 to 4 are already completed.

 

Completed phases:

1. Strategy schema and Indicator Registry foundation

2. Entry / Exit / Risk engines

3. Deterministic Backtesting Engine

4. Reliability / Trust Score Engine

 

Existing feature:

Tradetri already has an Auto Kill Switch system.

Do NOT rebuild the Auto Kill Switch.

Only integrate with it where required.

 

Your task:

Continue from Phase 5 onward and integrate the remaining features carefully, phase-by-phase, without breaking existing Tradetri functionality.

 

============================================================

GLOBAL RULES

============================================================

 

1. Do NOT rewrite the whole project.

2. Do NOT delete existing functionality.

3. Do NOT break existing routes/pages/features.

4. Do NOT modify completed Phase 1–4 engines unless absolutely necessary.

5. Do NOT rebuild the existing Auto Kill Switch.

6. Do NOT place real broker orders by default.

7. Do NOT push to remote automatically.

8. Do NOT promise guaranteed profit.

9. Do NOT allow AI to calculate backtest results.

10. Backtest, reliability, and truth score results must come from deterministic code only.

11. AI can explain, warn, suggest, diagnose, improve, and compare strategies.

12. Work phase-by-phase.

13. After every phase:

   - list changed files

   - explain why each file changed

   - run tests

   - run typecheck if available

   - run lint if available

   - run build

   - provide manual verification steps

   - suggest Git commit message

   - stop and wait for approval

 

If any phase requires a major architecture change:

STOP and explain before implementing.

 

If any live broker-related behavior is touched:

STOP and ask for approval first.

 

============================================================

FINANCIAL SAFETY LANGUAGE RULES

============================================================

 

Never use:

- guaranteed profit

- sure-shot strategy

- 100% profitable

- risk-free trading

 

Use:

- risk-controlled execution

- disciplined trading

- strategy verification

- reliability score

- truth score

- paper trading recommended

- no strategy guarantees future performance

 

============================================================

AI ROLE RULES

============================================================

 

AI can:

- explain strategies

- suggest indicators

- warn about risks

- diagnose strategy problems

- suggest improvements

- generate strategy explanation

- explain backtest results

- explain trust/truth score

- explain market regime mismatch

- explain live vs backtest deviation

- convert supported Pine subset into safe Tradetri JSON

 

AI must NOT:

- calculate backtest results

- fabricate performance numbers

- promise profits

- execute arbitrary code

- bypass Pine Script protections

- place live broker orders

 

============================================================

GIT AND CHECKPOINT RULES

============================================================

 

Before each phase:

1. Check git status.

2. Do not proceed if there are unexpected uncommitted changes unless explained.

 

After each phase:

1. Run tests/build/lint/typecheck where available.

2. Show changed files.

3. Suggest Git commit message.

4. Provide exact Git commands.

5. Stop and wait for approval.

 

Suggested branch:

feature/tradetri-phase5-plus

 

Do not push to remote automatically.

 

============================================================

OUTPUT FORMAT AFTER EACH PHASE

============================================================

 

Use this exact output format:

 

1. Phase completed

2. Files created/updated

3. Why each file changed

4. Tests added/updated

5. Commands run

6. Results of commands

7. Manual verification steps

8. Risks / TODOs

9. Suggested Git commit message

10. Exact Git commands

11. Next phase recommendation

 

============================================================

PHASE 5 — ADAPTIVE STRATEGY BUILDER UI

============================================================

 

Goal:

Integrate adaptive strategy builder UI into the existing Tradetri project.

 

Important:

Phase 1–4 engines already exist.

Use them.

Do not duplicate calculation logic in UI.

 

Build or extend these UI modules:

 

------------------------------------------------------------

1. Strategy Dashboard

------------------------------------------------------------

 

Include:

- Saved strategies list or placeholder

- Create New Strategy button

- Import Pine Script placeholder

- Mode selector:

  - Beginner

  - Intermediate

  - Expert

- Trust Score badge

- Strategy Truth Score placeholder

- Backtest status

- Paper/live status if available

- Auto Kill Switch status summary if available

 

------------------------------------------------------------

2. Guided Beginner Builder

------------------------------------------------------------

 

Beginner flow:

 

Step 1:

User selects goal:

- Intraday

- Swing

- Scalping

- Safe learning mode

 

Step 2:

System recommends simple setup:

- EMA

- RSI

- Stop Loss

- Target

 

Step 3:

Show generated simple strategy preview.

 

Step 4:

Run Backtest button.

 

Step 5:

Show:

- Backtest result

- Trust Score

- Strategy Truth Score placeholder

- Simple explanation

 

Beginner UI rules:

- Do not show 100+ indicators.

- Do not show JSON editor.

- Do not expose complex controls.

- Use simple language.

- Use large buttons.

- Keep choices minimal.

 

------------------------------------------------------------

3. Intermediate Builder

------------------------------------------------------------

 

Include:

- Indicator category browser

- Indicator search

- Add indicator form

- Entry condition builder

- Exit condition builder

- Risk settings builder

- Run Backtest button

- Strategy JSON preview collapsed by default

- Trust Score panel

- Strategy Truth Score placeholder

 

------------------------------------------------------------

4. Expert Builder

------------------------------------------------------------

 

Include:

- Full active indicator library

- Advanced entry conditions

- AND / OR grouping

- Partial exits

- Trailing stop

- Time-based exits

- Square-off time

- JSON preview/editor if feasible

- Robustness test controls

- Strategy Truth Engine result placeholder

- Market Regime Test placeholder

- Live vs Backtest Deviation placeholder

 

------------------------------------------------------------

5. Indicator Library UI

------------------------------------------------------------

 

Include:

- Category filter

- Search

- Difficulty badge

- Active / Coming Soon / Experimental status

- Simple explanation

- Coming Soon indicators disabled

- Beginner mode shows only recommended indicators

- Intermediate mode shows active indicators

- Expert mode can show active + experimental indicators

 

Rules:

- coming_soon indicators must not be selectable for execution.

- experimental indicators must not be allowed for live trading.

 

------------------------------------------------------------

6. Entry Builder UI

------------------------------------------------------------

 

Support:

- Indicator condition

- Candle condition

- Time condition

- Price condition

 

Operators:

- >

- <

- >=

- <=

- crossover

- crossunder

 

Logic:

- AND

- OR

 

------------------------------------------------------------

7. Exit Builder UI

------------------------------------------------------------

 

Support:

- Target %

- Stop Loss %

- Trailing Stop %

- Partial Exit

- Indicator exit placeholder

- Square-off time

 

------------------------------------------------------------

8. Risk Builder UI

------------------------------------------------------------

 

Support:

- Max daily loss %

- Max trades per day

- Max loss streak

- Max capital per trade %

 

If existing Auto Kill Switch settings are already present:

- show read-only summary or link to existing kill switch configuration

- do not rebuild it

 

------------------------------------------------------------

9. Backtest Result Panel

------------------------------------------------------------

 

Display:

- Total PnL

- Return %

- Win rate

- Loss rate

- Total trades

- Max drawdown

- Profit factor

- Expectancy

- Equity curve

- Trade logs

- Warnings

- Cost-adjusted result

 

------------------------------------------------------------

10. Trust / Reliability Panel

------------------------------------------------------------

 

Display:

- Score

- Grade

- Verdict

- Passed checks

- Failed checks

- Warnings

- Suggestions

- Out-of-sample summary

- Parameter sensitivity summary

- Walk-forward summary placeholder

 

------------------------------------------------------------

11. Strategy Truth Panel Placeholder

------------------------------------------------------------

 

Add placeholder UI for Strategy Truth Engine:

- Truth Score

- Fake Backtest Warnings

- Overfitting Risk

- Reality Check

- Recommended Next Action

 

Actual engine implementation happens in Phase 6.

 

============================================================

Phase 5 Testing

============================================================

 

Add UI/component tests if existing setup supports it:

 

1. Mode selector renders.

2. Beginner builder hides advanced options.

3. Expert builder shows advanced options.

4. Indicator library filters active indicators.

5. Coming Soon indicators are disabled.

6. Backtest result panel renders.

7. Trust Score panel renders.

8. Strategy Truth placeholder renders.

 

============================================================

Phase 5 Output

============================================================

 

Run:

- tests

- typecheck if available

- lint if available

- build if available

 

Suggested commit:

feat(builder-ui): add adaptive strategy builder and trust panels

 

Stop after Phase 5.

Do not continue to Phase 6 until approved.

 

============================================================

PHASE 6 — STRATEGY TRUTH ENGINE

============================================================

 

Goal:

Add Strategy Truth Engine.

 

Purpose:

Detect misleading or fake-looking backtests.

 

This feature should answer:

"Is this backtest actually reliable, or is it giving false confidence?"

 

Important:

Do not replace existing Reliability / Trust Score Engine.

Build Strategy Truth Engine on top of existing Phase 4 reliability data.

 

Strategy Truth Engine should inspect:

 

1. High win rate risk

2. Low trade count

3. Poor risk/reward

4. Average loss much bigger than average win

5. High max drawdown

6. Profit factor weakness

7. Out-of-sample degradation

8. Parameter sensitivity weakness

9. Cost/slippage impact

10. Same-candle ambiguity impact

11. Overfitting risk

12. Unrealistic execution assumptions

 

Input:

- strategy JSON

- backtest result

- reliability report

- out-of-sample result

- parameter sensitivity result

- cost settings

- ambiguity mode result

 

Output:

 

{

  "truthScore": 0,

  "grade": "A | B | C | D | F",

  "verdict": "Ready for paper trading | Needs improvement | Not ready",

  "riskLevel": "low | medium | high | extreme",

  "fakeBacktestWarnings": [],

  "overfittingWarnings": [],

  "executionWarnings": [],

  "costWarnings": [],

  "strengths": [],

  "weaknesses": [],

  "recommendedNextActions": []

}

 

Example warning:

"Win rate is high, but average loss is much larger than average win. This strategy may look good but can fail badly in live conditions."

 

Example warning:

"Training result is strong, but out-of-sample result dropped significantly. Overfitting risk is high."

 

Example warning:

"Cost-adjusted performance is weak. Charges and slippage may remove most profits."

 

UI:

Connect Strategy Truth Engine to Strategy Truth Panel created in Phase 5.

 

Beginner explanation:

Use simple language:

"Backtest looks good, but this does not guarantee future performance. Tradetri detected some reliability risks."

 

Expert explanation:

Show detailed metrics and warnings.

 

Tests:

1. 95% win rate but poor risk/reward should produce warning.

2. Low trade count should reduce truth score.

3. Out-of-sample degradation should trigger overfitting warning.

4. Cost impact should trigger cost warning.

5. Good strategy should get better truth score.

6. Truth Engine should not mutate backtest results.

 

After Phase 6:

Run tests, typecheck, lint, build.

 

Suggested commit:

feat(strategy-truth): add fake backtest detection and truth score

 

Stop after Phase 6.

 

============================================================

PHASE 7 — BASE AI ADVISOR + AI STRATEGY DOCTOR

============================================================

 

Goal:

Add Base AI Advisor and AI Strategy Doctor.

 

Important:

The AI Advisor must work without external LLM/API.

Start with deterministic rule-based advisor.

Optional LLM interface can be pluggable, but base app must work without API key.

 

------------------------------------------------------------

1. Base AI Advisor

------------------------------------------------------------

 

Inputs:

- strategy JSON

- selected indicators

- backtest result

- reliability report

- strategy truth report

- user mode

- risk config

- market regime if available

- deviation report if available

 

Advisor should provide:

- indicator suggestions

- missing stop loss warnings

- missing exit warnings

- high win-rate caution

- low trust score warning

- strategy truth warning

- overfitting warning

- paper trading recommendation

- market regime mismatch warning

- live deviation warning

 

Rules:

- only EMA -> suggest RSI/MACD

- only RSI -> suggest EMA

- no stop loss -> warn

- no exit -> warn

- too many indicators -> warn

- high win rate -> reliability/truth warning

- low trust score -> paper trading recommendation

- high drawdown -> reduce risk suggestion

- weak out-of-sample -> overfitting warning

- poor truth score -> do not recommend live trading

 

Example messages:

"Only EMA shows trend. Add RSI or MACD for confirmation."

 

"Stop loss is missing. Add stop loss before paper or live trading."

 

"95% win rate looks attractive, but reliability and truth checks are required."

 

------------------------------------------------------------

2. AI Strategy Doctor

------------------------------------------------------------

 

Purpose:

Diagnose strategy problems and suggest safe improvements.

 

Important:

AI Strategy Doctor must not promise profit.

AI Strategy Doctor must not fabricate backtest results.

AI Strategy Doctor can suggest improvements and compare deterministic results after the engine runs.

 

Inputs:

- strategy JSON

- selected indicators

- backtest result

- reliability report

- strategy truth report

- user mode

- risk settings

 

AI Strategy Doctor should provide:

 

1. Diagnosis

2. Detected problems

3. Root causes

4. Suggested fixes

5. Risk warnings

6. Apply Fix & Compare workflow

7. Original vs Improved comparison placeholder

 

Diagnosis examples:

 

Problem:

"Entry is too late."

 

Possible fix:

"Add pullback condition or earlier confirmation."

 

Problem:

"Strategy performs poorly in sideways markets."

 

Possible fix:

"Add market regime filter."

 

Problem:

"Stop loss is too wide."

 

Possible fix:

"Test ATR-based stop loss."

 

Problem:

"Too many indicators from the same category."

 

Possible fix:

"Use one trend indicator, one momentum confirmation, and one risk rule."

 

Output format:

 

{

  "diagnosisSummary": "",

  "problems": [

    {

      "type": "entry | exit | risk | overfit | cost | regime | complexity",

      "severity": "info | warning | critical",

      "message": "",

      "suggestedFix": "",

      "autoFixAvailable": true

    }

  ],

  "recommendedFixes": [],

  "canAutoImprove": true,

  "improvedStrategyDraft": {}

}

 

Apply Fix & Compare flow:

1. Generate improved strategy draft.

2. Show changes before applying.

3. User approves.

4. Run deterministic backtest again.

5. Compare original vs improved:

   - PnL

   - win rate

   - drawdown

   - profit factor

   - truth score

   - reliability score

 

Important:

Do not auto-apply changes without user approval.

 

------------------------------------------------------------

3. Strategy Explainability Engine

------------------------------------------------------------

 

Generate:

1. Strategy type

2. Indicators used

3. Entry logic

4. Exit logic

5. Risk controls

6. Backtest explanation

7. Reliability explanation

8. Truth score explanation

9. When strategy may work better

10. When strategy may fail

11. Beginner-friendly explanation

 

------------------------------------------------------------

4. Trade Quality Score

------------------------------------------------------------

 

Create score 0–100 based on:

- trend filter

- confirmation

- stop loss

- exit

- risk limit

- realistic costs

- out-of-sample

- truth score

- paper trading placeholder

 

------------------------------------------------------------

5. Optional LLM Provider Interface

------------------------------------------------------------

 

Create pluggable provider interface:

- explainStrategy()

- improveStrategy()

- explainBacktest()

- generateLearningTip()

- explainReliability()

- explainTruthScore()

 

Do not require API key for base functionality.
