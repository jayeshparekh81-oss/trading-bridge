You are a senior full-stack architect, trading systems engineer, quantitative backtesting engineer, AI product designer, QA lead, and codebase integration expert.

 

I already have an existing live project called "Tradetri" at www.tradetri.com.

 

This is an existing production project, NOT a new project.

 

Your job is to carefully inspect the existing Tradetri codebase and integrate a complete AI-powered no-code trading system into the existing architecture.

 

You must work with extreme caution.

 

============================================================

CRITICAL OPERATING RULES

============================================================

 

1. Do NOT recreate the entire app from scratch.

2. Do NOT delete existing functionality.

3. Do NOT break existing routes/pages/features.

4. Do NOT replace the architecture unless absolutely necessary.

5. Do NOT make massive unrelated changes.

6. Do NOT modify live broker execution behavior without explicit approval.

7. Do NOT introduce unnecessary dependencies.

8. Do NOT skip tests.

9. Do NOT claim financial guarantees.

10. Do NOT let AI calculate backtest results.

 

You may understand the full scope at once, but you must implement it internally phase-by-phase.

 

After every phase:

- run tests if available

- run type check if available

- run lint if available

- run build if available

- list changed files

- explain why each file changed

- create or recommend a Git checkpoint commit

- stop and wait for approval if anything risky is found

 

If any phase requires a major architecture change:

STOP and explain before implementing.

 

If you are unsure about existing code behavior:

STOP and ask before changing it.

 

============================================================

PRODUCT VISION

============================================================

 

Transform Tradetri into an AI-powered no-code trading platform where users can:

 

1. Add indicators from a scalable 100+ indicator architecture

2. Build strategies without coding

3. Use Beginner, Intermediate, and Expert modes

4. Import supported open-source/user-provided Pine Script subset

5. Convert supported Pine logic into safe Tradetri internal JSON

6. Backtest strategies deterministically

7. Validate strategies using reliability/trust score

8. Use out-of-sample testing

9. Use walk-forward testing architecture

10. Use parameter sensitivity testing

11. Use realistic cost/slippage modeling

12. Use AI advisor for explanation and improvement

13. Use risk/discipline engine

14. Use paper trading before live trading

15. Prepare safe broker-ready execution architecture

 

The final product should feel like:

 

"Whether the user is a beginner or expert, Tradetri helps them build, understand, test, verify, and safely execute strategies with intelligent guidance."

 

============================================================

FINANCIAL SAFETY LANGUAGE RULES

============================================================

 

Never use:

- guaranteed profit

- sure-shot strategy

- 100% profitable

- risk-free trading

- guaranteed win rate

 

Use:

- disciplined trading

- risk-controlled execution

- better decision support

- educational guidance

- reliability score

- robustness check

- paper trading recommended

- no strategy guarantees future performance

 

AI advisor must always be risk-aware.

 

============================================================

AI ROLE RULES

============================================================

 

AI can:

- explain strategies

- suggest improvements

- warn users

- simplify complex logic

- generate educational guidance

- explain backtest/reliability results

- convert supported Pine subset into internal JSON

 

AI must NOT:

- calculate backtest results

- fabricate performance numbers

- make live trading decisions without deterministic engine + risk checks

- promise profits

- execute arbitrary user code

- bypass Pine Script protections

 

Backtest results must come only from deterministic code.

 

============================================================

PINE SCRIPT LEGAL AND SAFETY RULES

============================================================

 

1. Do NOT copy protected/private/paid TradingView scripts.

2. Do NOT bypass hidden/protected Pine code.

3. Do NOT build a full Pine Script interpreter.

4. Only support:

   - user-provided Pine Script

   - open-source Pine Script

   - simple supported subset

5. Do NOT execute arbitrary Pine code.

6. Convert supported Pine subset into safe Tradetri internal JSON.

7. Unsupported constructs must produce clear warnings.

8. Partial conversion is allowed only with explicit warning.

 

Unsupported examples:

- request.security

- arrays/matrices

- complex loops

- custom functions beyond simple mapping

- labels/tables/boxes

- unsupported strategy functions

- protected/private unavailable code

 

============================================================

GIT AND CHECKPOINT RULES

============================================================

 

Before starting:

1. Check current Git status.

2. Do not proceed if there are unexpected uncommitted changes unless you explain them.

3. Recommend creating a branch:

 

   feature/ai-trading-system

 

For every phase:

1. Make small modular changes.

2. Run checks.

3. Show changed files.

4. Recommend a Git commit message.

5. Do not continue to next phase until current phase is stable.

 

Recommended commit format:

 

Phase 0:

chore(audit): inspect existing Tradetri architecture

 

Phase 1:

feat(strategy-core): add strategy schema and indicator registry

 

Phase 2:

feat(strategy-engine): add entry exit position and risk engines

 

Phase 3:

feat(backtest): add deterministic backtesting engine

 

Phase 4:

feat(reliability): add strategy trust score and robustness checks

 

Phase 5:

feat(builder-ui): add strategy builder UI and result panels

 

Phase 6:

feat(ai-advisor): add rule-based AI advisor and explainability

 

Phase 7:

feat(pine-import): add safe Pine subset importer

 

Phase 8:

feat(execution): add paper trading and broker abstraction

 

Phase 9:

feat(indicators): expand indicator registry toward 100+ indicators

 

Phase 10:

chore(hardening): add documentation tests and final verification

 

Do NOT push to remote automatically unless explicitly instructed.

Instead, provide the exact git commands.

 

============================================================

QUALITY GATES AFTER EVERY PHASE

============================================================

 

After each phase, run all available commands if they exist:

 

1. Dependency check:

   - npm install only if needed

   - do not add dependencies unless justified

 

2. Tests:

   - npm test

   - pnpm test

   - yarn test

   - or existing test command

 

3. Type check:

   - npm run typecheck

   - pnpm typecheck

   - or existing command

 

4. Lint:

   - npm run lint

   - pnpm lint

   - or existing command

 

5. Build:

   - npm run build

   - pnpm build

   - or existing command

 

If command does not exist:

- clearly say command not found

- do not invent results

 

If any check fails:

- stop

- explain failure

- fix only related issue

- rerun checks

 

============================================================

OUTPUT FORMAT AFTER EVERY PHASE

============================================================

 

Use this exact output format:

 

1. Phase completed

2. Files inspected

3. Files created/updated

4. Why each file changed

5. Tests added/updated

6. Commands run

7. Results of commands

8. Manual verification steps

9. Risks / TODOs

10. Suggested Git commit message

11. Exact Git commands

12. Next phase recommendation

 

============================================================

PHASE 0 — CODEBASE AUDIT ONLY

============================================================

 

Do not modify any files in Phase 0.

 

Audit the existing repository and summarize:

 

1. Frontend framework

2. Backend framework

3. Current folder structure

4. Current routing system

5. Current charting implementation

6. Current auth/user system

7. Current database/models

8. Current API structure

9. Existing trading/chart/strategy code

10. Existing backtesting code if any

11. Existing broker integration if any

12. Current environment/config setup

13. Current testing framework

14. Current deployment/build commands

15. Best integration points for new modules

16. Risky areas

17. Recommended implementation order

 

Also check:

- package manager

- existing scripts in package.json

- TypeScript or JavaScript

- state management approach

- component library/style system

- API conventions

- database conventions

 

Output:

- architecture summary

- recommended module structure

- risk assessment

- safe implementation plan

- Phase 1 file plan

 

Do NOT edit files during Phase 0.

 

Quality gate:

- run no modifying commands

- only inspect

 

Suggested Git commit:

No commit required unless audit documentation file is created with explicit approval.

 

============================================================

PHASE 1 — CORE STRATEGY FOUNDATION

============================================================

 

Goal:

Create the core foundation for strategy building.

 

Implement:

 

1. Strategy JSON schema/types

 

The internal strategy JSON must become the single source of truth for:

- UI builder

- backtest engine

- paper trading

- broker execution

- AI advisor

- Pine conversion

- reliability engine

 

Example strategy format:

 

{

  "id": "strategy_001",

  "name": "EMA RSI Beginner Strategy",

  "mode": "beginner",

  "version": 1,

  "indicators": [

    {

      "id": "ema_20",

      "type": "ema",

      "params": {

        "period": 20,

        "source": "close"

      }

    },

    {

      "id": "ema_50",

      "type": "ema",

      "params": {

        "period": 50,

        "source": "close"

      }

    },

    {

      "id": "rsi_14",

      "type": "rsi",

      "params": {

        "period": 14,

        "source": "close"

      }

    }

  ],

  "entry": {

    "side": "BUY",

    "operator": "AND",

    "conditions": [

      {

        "type": "indicator",

        "left": "ema_20",

        "op": ">",

        "right": "ema_50"

      },

      {

        "type": "indicator",

        "left": "rsi_14",

        "op": "<",

        "value": 30

      }

    ]

  },

  "exit": {

    "targetPercent": 2,

    "stopLossPercent": 1,

    "trailingStopPercent": 0.5,

    "partialExits": [

      {

        "qtyPercent": 50,

        "targetPercent": 1

      }

    ],

    "squareOffTime": "15:20"

  },

  "risk": {

    "maxDailyLossPercent": 2,

    "maxTradesPerDay": 5,

    "maxLossStreak": 3,

    "maxCapitalPerTradePercent": 10

  },

  "execution": {

    "mode": "backtest",

    "orderType": "MARKET",

    "productType": "INTRADAY"

  }

}

 

2. Indicator Registry architecture

 

Every indicator must have metadata:

 

{

  "id": "ema",

  "name": "EMA",

  "category": "Trend",

  "description": "EMA shows smoothed trend direction.",

  "inputs": [

    {

      "name": "period",

      "type": "number",

      "default": 20

    },

    {

      "name": "source",

      "type": "source",

      "default": "close"

    }

  ],

  "outputs": ["line"],

  "chartType": "overlay",

  "pineAliases": ["ta.ema"],

  "difficulty": "beginner",

  "status": "active",

  "calculationFunction": "ema",

  "aiExplanation": "EMA helps identify trend direction by smoothing price."

}

 

Registry must support:

- id

- name

- category

- description

- inputs

- default values

- outputs

- chart type

- Pine aliases

- difficulty

- status:

  - active

  - coming_soon

  - experimental

- AI explanation

- tags/search terms

 

3. Implement first 10 indicator calculations:

- EMA

- SMA

- WMA

- RSI

- MACD

- Bollinger Bands

- ATR

- VWAP

- OBV

- Volume SMA

 

4. Registry helper functions:

- getIndicatorById

- getIndicatorsByCategory

- getActiveIndicators

- getBeginnerRecommendedIndicators

- validateIndicatorParams

 

5. Tests:

- registry loads correctly

- EMA calculation

- SMA calculation

- RSI calculation

- invalid params rejected

- active indicators filtered correctly

 

Rules:

- Keep calculation functions pure.

- Do not build UI in this phase.

- Do not build backtest in this phase.

- Follow existing project style.

- Use TypeScript if the project uses TypeScript.

- Use JavaScript if the project uses JavaScript.

 

Quality gate:

- tests pass

- typecheck pass if available

- lint pass if available

- build pass if available

 

Suggested Git commit:

feat(strategy-core): add strategy schema and indicator registry

 

============================================================

PHASE 2 — ENTRY, EXIT, POSITION, RISK ENGINES

============================================================

 

Goal:

Create deterministic strategy evaluation engines.

 

Implement:

 

1. Entry Evaluation Engine

 

Support:

- indicator > indicator

- indicator < value

- indicator > value

- crossover

- crossunder

- candle condition

- time condition

- price condition

- AND / OR logic

 

Entry output:

 

{

  "shouldEnter": true,

  "side": "BUY",

  "reasons": [],

  "failedConditions": []

}

 

2. Candle Pattern Engine

 

Support:

- bullish candle

- bearish candle

- engulfing

- doji

- hammer

- shooting star

- previous high breakout

- previous low breakdown

 

3. Time Condition Engine

 

Support:

- exact time

- after time

- before time

- session window

 

4. Price Condition Engine

 

Support:

- price above level

- price below level

- previous high breakout

- previous low breakdown

 

5. Exit Evaluation Engine

 

Support:

- fixed target %

- fixed stop loss %

- trailing stop %

- partial exit

- indicator-based exit

- reverse signal exit

- time-based exit

- square-off time

 

Exit output:

 

{

  "shouldExit": true,

  "exitType": "target",

  "exitPrice": 102,

  "qtyPercent": 50,

  "reason": "Target 1 hit"

}

 

6. Position State Manager

 

Track:

 

{

  "isOpen": true,

  "side": "BUY",

  "entryPrice": 100,

  "quantity": 100,

  "remainingQuantity": 50,

  "highestPriceSinceEntry": 105,

  "lowestPriceSinceEntry": 98,

  "trailingStopPrice": 102,

  "partialExitsDone": []

}

 

7. Basic Risk Engine

 

Rules:

- max daily loss

- max trades per day

- max loss streak

- missing stop loss warning

- no exit warning

- too many indicators warning

 

Risk output:

 

{

  "allowed": true,

  "severity": "info",

  "messages": [],

  "suggestions": []

}

 

8. Tests:

- indicator entry condition

- crossover

- crossunder

- candle condition

- time condition

- target exit

- stop loss exit

- trailing stop update

- partial exit

- max trades block

- missing stop loss warning

 

Rules:

- Do not build backtest runner yet.

- Do not build UI yet.

- Keep engines pure and reusable.

 

Quality gate:

- tests pass

- typecheck pass if available

- lint pass if available

- build pass if available

 

Suggested Git commit:

feat(strategy-engine): add entry exit position and risk engines

 

============================================================

PHASE 3 — DETERMINISTIC BACKTEST ENGINE

============================================================

 

Goal:

Build reliable deterministic backtesting.

 

Important:

AI must NOT calculate backtest results.

 

Backtest architecture:

1. Data normalizer

2. Active indicator pre-calculation

3. Candle-by-candle simulator

4. Position manager integration

5. Entry evaluation

6. Exit evaluation

7. Risk checks

8. Metrics engine

9. Trade logs

10. Equity curve

 

Backtest rules:

1. Signal is generated on candle close.

2. Entry happens on next candle open by default.

3. Avoid lookahead bias.

4. If target and stop loss both hit in same candle:

   - default conservative mode = stop loss first

 

Add ambiguity modes:

- conservative

- optimistic

- accurate placeholder

 

Backtest input:

 

{

  "candles": [],

  "strategy": {},

  "initialCapital": 100000,

  "quantity": 1,

  "costSettings": {},

  "ambiguityMode": "conservative"

}

 

Backtest output:

 

{

  "totalPnl": 0,

  "totalReturnPercent": 0,

  "winRate": 0,

  "lossRate": 0,

  "totalTrades": 0,

  "averageWin": 0,

  "averageLoss": 0,

  "largestWin": 0,

  "largestLoss": 0,

  "maxDrawdown": 0,

  "profitFactor": 0,

  "expectancy": 0,

  "equityCurve": [],

  "trades": [],

  "warnings": []

}

 

Trade log:

 

{

  "entryTime": "",

  "exitTime": "",

  "side": "BUY",

  "entryPrice": 100,

  "exitPrice": 102,

  "quantity": 100,

  "pnl": 200,

  "exitReason": "target",

  "entryReasons": []

}

 

Realistic cost mode:

Support:

- fixed cost

- percentage cost

- slippage percent

- spread placeholder

 

Tests:

1. simple target hit

2. simple stop loss hit

3. trailing stop hit

4. partial exit

5. max trades per day block

6. daily loss block

7. same candle target/SL conservative behavior

8. no lookahead test

9. cost mode reduces PnL

10. deterministic same input same output

 

Rules:

- Do not build UI in this phase.

- Prioritize correctness over speed.

- AI must not generate performance values.

 

Quality gate:

- tests pass

- typecheck pass if available

- lint pass if available

- build pass if available

 

Suggested Git commit:

feat(backtest): add deterministic backtesting engine

 

============================================================

PHASE 4 — STRATEGY RELIABILITY / TRUST SCORE ENGINE

============================================================

 

Goal:

Do not trust high win rate blindly.

 

Create Strategy Trust Score / Reliability Score from 0 to 100.

 

Trust score must consider:

1. Trade count

2. Win rate

3. Profit factor

4. Max drawdown

5. Average win vs average loss

6. Cost-adjusted result

7. Out-of-sample result

8. Parameter sensitivity

9. Paper trading status placeholder

10. Same-candle ambiguity impact

 

Reliability output:

 

{

  "score": 72,

  "grade": "B",

  "verdict": "Moderately reliable",

  "warnings": [],

  "passedChecks": [],

  "failedChecks": [],

  "suggestions": []

}

 

High win-rate warning:

 

If winRate > 85%, check:

- average loss vs average win

- profit factor

- max drawdown

- trade count

- cost-adjusted PnL

 

If risky, warn:

 

"Win rate is high, but the strategy may still be unreliable. Check average loss, drawdown, cost impact, and out-of-sample result."

 

Implement Out-of-Sample Test:

- 70% training

- 30% testing

- run backtest on both

- compare performance degradation

 

Output:

 

{

  "training": {},

  "testing": {},

  "degradationPercent": 0,

  "warning": ""

}

 

Implement Walk-Forward Testing Architecture:

- configurable train/test windows

- run multiple windows

- summarize consistency score

 

Output:

 

{

  "windows": [],

  "summary": {

    "passedWindows": 0,

    "failedWindows": 0,

    "consistencyScore": 0

  }

}

 

Implement Parameter Sensitivity Test:

 

Test nearby values:

- EMA period nearby values

- RSI threshold nearby values

- SL/target nearby values

 

Output:

 

{

  "stabilityScore": 0,

  "robust": false,

  "warning": "",

  "testedVariants": []

}

 

Tests:

1. high win rate but bad risk-reward warning

2. low trade count warning

3. out-of-sample degradation warning

4. parameter sensitivity warning

5. strong strategy gets better trust score

 

Quality gate:

- tests pass

- typecheck pass if available

- lint pass if available

- build pass if available

 

Suggested Git commit:

feat(reliability): add strategy trust score and robustness checks

 

============================================================

PHASE 5 — UI BUILDER INTEGRATION

============================================================

 

Goal:

Integrate builder UI into existing Tradetri UI safely.

 

Add or extend screens:

 

1. Strategy Dashboard

- saved strategies

- create new strategy

- import Pine button placeholder

- beginner/intermediate/expert mode

- trust score badge

 

2. Guided Beginner Builder

- step-by-step flow

- recommended indicators only

- AI suggestion placeholder

- backtest button

- reliability check button

 

3. Intermediate Builder

- indicator category browser

- condition builder

- entry builder

- exit builder

- risk builder

 

4. Expert Builder

- full indicator library

- advanced conditions

- partial exits

- trailing stop

- time rules

- JSON preview/editor if feasible

 

5. Indicator Library UI

- category filter

- search

- difficulty badge

- active/coming soon status

- simple explanation

 

6. Backtest Result Panel

- PnL

- win rate

- drawdown

- equity curve

- trades table

- cost-adjusted result

- trust score

 

7. Robustness Panel

- out-of-sample result

- walk-forward result

- parameter sensitivity

- reliability score

 

UI principles:

- Beginner mode must not show 100+ indicators.

- Expert mode can show full library.

- Keep mobile responsive.

- Preserve existing design language.

- Do not clutter UI.

- Use existing component library if available.

 

Rules:

- If backend APIs are not ready, use local mock data or service abstraction.

- Do not break existing routes.

- Do not redesign the entire app.

 

Quality gate:

- build passes

- existing pages still load

- no obvious console errors

- UI accessible from existing navigation or clearly documented route

 

Suggested Git commit:

feat(builder-ui): add strategy builder UI and result panels

 

============================================================

PHASE 6 — AI ADVISOR / AI COACH

============================================================

 

Goal:

Add AI advisor system.

 

Important:

System must work without external LLM.

 

Implement 3 layers.

 

Layer 1: Rule-Based Advisor

 

Inputs:

- strategy JSON

- selected indicators

- backtest result

- reliability report

- user mode

 

Rules:

- only EMA -> suggest RSI/MACD

- only RSI -> suggest EMA

- no stop loss -> warn

- no exit -> warn

- too many indicators -> warn

- high win rate -> reliability warning

- low trust score -> paper trading recommendation

- high drawdown -> reduce risk

- weak out-of-sample -> overfitting warning

 

Example messages:

 

"Only EMA shows trend. Add RSI or MACD for confirmation."

 

"Stop loss is missing. Add stop loss for risk control."

 

"95% win rate looks attractive, but reliability checks are still required."

 

Layer 2: Pattern-Based Advisor

 

Detect:

- overtrading

- repeated losses

- high drawdown

- poor risk-reward

- strategy too complex

- low paper readiness

- overfitting risk

- live deviation placeholder

 

Layer 3: Optional LLM Interface

 

Create pluggable provider interface:

- explainStrategy()

- improveStrategy()

- explainBacktest()

- generateLearningTip()

- explainReliability()

 

Do not require API key for base functionality.

 

AI language rules:

- simple English/Hinglish-ready text

- educational

- risk-aware

- no profit guarantee

 

Implement Strategy Explainability Engine:

 

Generate:

1. Strategy type

2. Indicators used

3. Entry logic

4. Exit logic

5. Risk controls

6. Backtest explanation

7. Reliability explanation

8. When strategy may work better

9. When strategy may fail

10. Simple beginner explanation

 

Implement Trade Quality Score:

 

Score 0-100 based on:

- trend filter

- confirmation

- stop loss

- exit

- risk limit

- realistic costs

- out-of-sample

- paper trading placeholder

 

Tests:

- EMA only suggestion

- no SL warning

- high-win-rate reliability warning

- low trust score warning

- too many indicators warning

 

Quality gate:

- tests pass

- build passes

- AI advisor works without API key

 

Suggested Git commit:

feat(ai-advisor): add rule-based AI advisor and explainability

 

============================================================

PHASE 7 — PINE SCRIPT SUPPORTED-SUBSET IMPORTER

============================================================

 

Goal:

Add safe Pine Script importer.

 

Legal/safety rules:

1. Do not copy protected/private/paid scripts.

2. Do not bypass hidden code.

3. Do not build full Pine interpreter.

4. Do not execute arbitrary Pine code.

5. Only parse supported user-provided/open-source subset.

6. Unsupported constructs must show warnings.

 

Supported mappings:

- ta.ema -> EMA

- ta.sma -> SMA

- ta.rsi -> RSI

- ta.macd -> MACD

- ta.bb -> Bollinger Bands

- ta.atr -> ATR

- ta.vwap -> VWAP

- ta.crossover -> CROSSOVER condition

- ta.crossunder -> CROSSUNDER condition

- ta.highest -> Highest

- ta.lowest -> Lowest

 

Implement:

1. Pine input validator

2. Basic parser/mapping layer

3. Unsupported feature detector

4. Convert supported Pine subset to Tradetri strategy JSON

5. Explanation generator

6. Pine import UI:

   - paste code

   - convert

   - preview JSON/blocks

   - unsupported warning

   - save strategy placeholder

 

Unsupported features:

- request.security

- arrays/matrices

- complex loops

- custom functions beyond simple mapping

- labels/tables/boxes

- unsupported strategy functions

 

Unsupported response:

 

{

  "success": false,

  "partial": true,

  "converted": {},

  "unsupported": ["request.security"],

  "message": "This Pine Script uses advanced features. Tradetri currently supports only a basic safe subset."

}

 

Supported response:

 

{

  "success": true,

  "strategy": {},

  "explanation": "This strategy uses EMA crossover and RSI filter."

}

 

Tests:

- converts ta.ema

- converts ta.rsi

- converts crossover

- detects request.security unsupported

- partial conversion warning

- does not execute code

 

Quality gate:

- tests pass

- build passes

- no arbitrary code execution

 

Suggested Git commit:

feat(pine-import): add safe Pine subset importer

 

============================================================

PHASE 8 — PAPER TRADING + BROKER ARCHITECTURE

============================================================

 

Goal:

Add paper trading and broker-ready architecture.

 

Default mode must be paper/safe.

 

Implement:

 

1. Execution Modes

- backtest

- paper

- live

 

2. Paper Trading Engine

 

Track:

- simulated signals

- simulated positions

- paper PnL

- rule adherence

- paper readiness status

 

Paper trading output:

 

{

  "completedSessions": 7,

  "paperPnl": 3500,

  "paperWinRate": 57,

  "ruleAdherence": 92,

  "liveReady": true

}

 

3. Broker Service Abstraction

 

Interface:

- connect()

- getProfile()

- getFunds()

- getPositions()

- placeOrder()

- cancelOrder()

- getOrderStatus()

 

If broker integration exists, extend it.

If not, create mock broker service.

 

4. Execution Guard

 

Before live order:

- risk engine must pass

- reliability score must be acceptable

- strategy must have stop loss

- broker must be connected

- max daily loss must not be hit

- paper trading recommended/required

 

Blocked order output:

 

{

  "allowed": false,

  "reason": "Reliability score is low. Paper trading is required before live execution."

}

 

5. Logs:

- paper trades

- live trade attempts

- blocked trades

- risk rejection reason

 

Quality gate:

- tests pass

- build passes

- no real order placement by default

- live mode guarded behind explicit configuration

 

Suggested Git commit:

feat(execution): add paper trading and broker abstraction

 

============================================================

PHASE 9 — 100+ INDICATOR EXPANSION

============================================================

 

Goal:

Expand indicator library toward 100+ indicators.

 

Important:

Do not expose unimplemented indicators as usable.

 

Add more active indicator calculations if feasible:

- ADX

- DMI

- Ichimoku

- Pivot Points

- Aroon

- TRIX

- Ultimate Oscillator

- Chaikin Money Flow

- Force Index

- Linear Regression

 

Add registry stubs for remaining indicators:

- status: coming_soon

- metadata complete

- calculationFunction: null or TODO

- hidden from beginner mode

 

Improve indicator library:

- search

- category filter

- difficulty filter

- active only filter

- tags

 

Performance:

- calculate only active indicators

- cache results

- avoid recalculating full history

- keep chart responsive

 

Tests:

- registry count

- active indicators only

- coming soon hidden from strategy execution

- search/filter works

 

Quality gate:

- tests pass

- build passes

- unimplemented indicators cannot be used in strategy execution

 

Suggested Git commit:

feat(indicators): expand indicator registry toward 100+ indicators

 

============================================================

PHASE 10 — FINAL HARDENING AND DOCUMENTATION

============================================================

 

Goal:

Make sure the full system is stable.

 

Do:

 

1. Run all tests

2. Run build

3. Verify existing Tradetri pages still work

4. Verify strategy builder flow

5. Verify deterministic backtest

6. Verify reliability score

7. Verify AI advisor warnings

8. Verify Pine importer safety

9. Verify paper trading guard

10. Verify live trading guard blocks unsafe execution

11. Check for TypeScript errors

12. Check for lint errors

13. Check for unnecessary dependencies

14. Check for dead code

 

Create documentation:

 

1. Strategy JSON guide

2. Indicator registry guide

3. Backtest engine guide

4. Reliability score guide

5. Pine importer limitations

6. AI advisor rules

7. Broker execution guard guide

8. Developer checklist for adding new indicators

 

Suggested documentation files:

- docs/strategy-json.md

- docs/indicator-registry.md

- docs/backtesting-engine.md

- docs/reliability-score.md

- docs/pine-importer.md

- docs/ai-advisor.md

- docs/broker-execution-guard.md

 

Quality gate:

- all tests pass

- build passes

- existing app manually verified

- documentation added

 

Suggested Git commit:

chore(hardening): add documentation and final verification

 

============================================================

FINAL SUCCESS CRITERIA

============================================================

 

The system is successful when:

 

1. Existing Tradetri still works.

2. User can create strategy using no-code builder.

3. User can add indicators from registry.

4. Beginner sees only recommended indicators.

5. Expert can access advanced logic.

6. Backtest runs deterministically.

7. Backtest includes realistic costs.

8. Same-candle SL/target ambiguity is handled.

9. Reliability score is calculated.

10. High win rate is not blindly trusted.

11. Out-of-sample testing exists.

12. Walk-forward architecture exists.

13. AI advisor gives useful suggestions.

14. Risk engine warns/blocks unsafe actions.

15. Pine supported subset converts into Tradetri JSON.

16. Unsupported Pine shows clear warning.

17. Paper trading mode exists.

18. Broker live execution is protected by risk and reliability checks.

19. 100+ indicator architecture exists.

20. Unimplemented indicators are safely marked coming_soon.

21. Tests/build pass.

22. Git checkpoints are recommended after every phase.





 

============================================================

BEGIN NOW

============================================================

 

Start with Phase 0 audit only.

 

Do not modify code during Phase 0.

 

After Phase 0:

- show the audit

- show integration plan

- show risks

- show Phase 1 file plan

- wait for approval before making code changes

 

Final Advice

Give Claude the full master prompt, but force it to:

Understand full scope.

Implement only one phase at a time.

Stop after every phase.

Run checks.

Recommend Git commit.

Wait for approval.
