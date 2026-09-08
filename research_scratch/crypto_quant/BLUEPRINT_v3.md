# TRADETRI CRYPTO QUANT LAB — MASTER BLUEPRINT v3

**This file replaces v2 entirely.** v2 closed eight structural gaps in v1 and corrected the execution order; everything it got right is kept, including its two best lines: *do not search for profits, search for repeatable market behavior*, and *never optimize for win rate*.

v3 closes five further gaps found on review. Each is marked **[v3-N]** where it appears, and all five are listed here:

1. **[v3-1] Event independence and effective N** — a new rail. Clustered events produce overlapping outcome windows; without this every standard error in the programme is too small.
2. **[v3-2] Minimum detectable effect** — A5 must state, before the run, the smallest effect the sample could see. Without it, "no edge" and "no power" are the same output.
3. **[v3-3] The sealed set is single-use** — A3 now says explicitly that one read burns it and names how the next seal is cut.
4. **[v3-4] Phase 2's gate made symmetric** — a negative stops the build; a positive must now survive its own sealed confirmation before it authorises spend.
5. **[v3-5] Funding is path-dependent** — charged as the discrete 8-hourly stamps each holding path actually crosses, never as an averaged rate.

**Why these five and not others.** Gaps 1 and 2 are the same failure mode that has already closed two studies in this programme's history: the OI accumulation study closed UNPOWERED at MDE 0.758% against a 0.50% gate, and pullback M5-S1 stopped at 62 signals against 339 needed. Both were discovered *after* the work was built. v3 moves that discovery to before the work starts.

---

## PART A — THE RAILS

These are not a phase. They are conditions on all work.

### A1. Pre-registration before observation
Any test that will look at forward outcomes is specified first: features, windows, thresholds, horizons, null, pass bar, cost model. Written to a file, SHA256 printed, committed. Then and only then is the outcome computed. A spec written after an outcome is void.

### A2. The hypothesis ledger
A single running file counts every hypothesis ever tested against this data — across all phases, all runs, all time. Every new test states the cumulative count and applies the corresponding multiple-comparison adjustment. The bar gets stricter as the ledger grows. 15 hypotheses × 7 timeframes is already 105 cells; a feature-combination search runs to thousands, where profit-factor and Sharpe thresholds clear on noise alone.

### A3. Sealed out-of-sample — **single use [v3-3]**
Before discovery begins, the sample is split chronologically — oldest for discovery, newest for confirmation. The confirmation set is quarantined in code: the loader raises if any discovery-stage process requests it, and **the guard is demonstrated firing in a test**. A cell passes only if it clears the bar on discovery *and* holds the same sign with comparable magnitude on confirmation.

**[v3-3] One read burns it.** The sealed set is a single-use resource, not a standing service.

- It is unlocked once, for **one batch of candidates pre-registered before the unlock**. Every candidate in that batch is confirmed in the same read.
- After that read the set is **spent** and is marked so in the ledger. It may never confirm another candidate, including a revision of a candidate it has already seen.
- A later candidate requires a **new seal**, cut only from data that **did not exist at the moment of the previous unlock**. The new seal's start timestamp must be strictly after the previous unlock timestamp, both recorded in the ledger.
- If a candidate arrives and no unspent seal covering fresh data exists, the candidate **waits** for enough new data to accumulate. It does not get confirmed against a spent set, and the wait is not a reason to relax the rule.

### A4. The null model
Nothing is "an edge" against zero. Every result is reported against two baselines:

- **Random-walk theoretical** — for a (stop, target) pair the hit-first rate is `1/(1+ratio)`. A 1:3 setup breaks even at 25%, not 50%. Print this next to every result.
- **Volatility-matched random baseline** — non-event timestamps matched on both hour-of-day and trailing-volatility bucket. Matching on volatility is mandatory, because events cluster in volatile periods and an unmatched baseline confounds the comparison.

Control timestamps are drawn **without replacement** and are subject to A10's spacing rule on the same terms as events, so the baseline cannot be inflated by reusing the same few quiet windows.

### A5. Instrument calibration — **and minimum detectable effect [v3-2]**
Before any real number is trusted, the measuring machine must pass:

- **Synthetic random walk** → must return the theoretical hit-first rate across the grid, within a tolerance derived from the binomial standard error at the actual event count, not chosen by hand.
- **Injected effect** → must be recovered with the right sign and roughly the right size, with censoring handled in the injection.
- **Random events** → must not pass.

If the machine cannot read a known truth, none of its unknown answers count.

**[v3-2] MDE is declared before the run, at the real event count.**

- Every pre-registration states the **minimum detectable effect**: given the actual number of *independent* events (A10's effective N, not the raw count), the null's variance, and the chosen significance and power (state both; default 0.05 / 0.80), what is the smallest deviation from the null this test could detect?
- The MDE is stated **next to the effect size that would be worth having**, net of cost. If `MDE > worth_having`, the test is **underpowered by construction and does not run**. It is recorded in the ledger as NOT RUN — UNDERPOWERED, with both numbers, and no hypothesis count is consumed.
- A null result from a test whose MDE was never stated is **uninterpretable** and may not be written up as "no edge". It is written up as `NOT MEASURED — POWER UNKNOWN`.
- The injected-effect calibration is injected **at the MDE**, not at a comfortably large size. An instrument that only recovers effects far above the MDE has not been shown to work at the size that matters.

### A6. Path, not clock
Forward returns at fixed clock horizons cannot express a stop/target payoff, whose exit is triggered by price touching a level. Compute instead, once per event: first-passage time to ±k·σ across a grid of k, plus MFE and MAE. From that single object the hit-first outcome for any (stop, target) pair is derivable without re-running — which also collapses many separate tests into one.

Right-censoring is never dropped. Events that resolve neither way inside the horizon are counted and reported as a censoring rate. Silently discarding unresolved trades is the standard way a fake win rate is manufactured.

### A7. Units
Results are expressed in σ and R, never in raw price or basis points. A fixed absolute unit averages quiet and volatile periods together and dilutes real effects.

### A8. Cost, stated as crossing or posting — **funding charged per path [v3-5]**
Cost is expressed as a fraction of the stop distance. It must include taker fee (sourced and quoted, never invented), observed spread, slippage, and — for perps — funding. Every result states plainly whether the rule crosses the spread or posts: the same signal can be profitable for the patient side and lossmaking for the impatient side.

**[v3-5] Funding is not a rate; it is a schedule.** Perpetual funding is a discrete payment at fixed stamps (8-hourly on Binance) whose **sign flips**. Averaging it is wrong in both directions at once: it overcharges sub-stamp holds that cross no payment, and undercharges multi-day holds where cumulative funding can exceed the entire edge.

- Each event's cost is computed from the **actual funding stamps its holding path crosses**, between entry and first passage, using the **realised funding rate at each stamp** and the position's sign.
- An event that opens and closes between two stamps is charged **zero** funding. That is a real and material asymmetry between fast and slow rules and must be visible in the results, not smoothed away.
- Because holding time is an outcome of A6's first passage and not known in advance, funding is computed **per event after its path resolves**, and censored events report funding accrued to the censoring boundary with the censoring flagged.
- Funding paid and funding received are reported **separately**, never netted into a single average, so a rule that is short-funding-positive is not confused with one that merely trades less.

### A9. Self-check and receipts
Every stage re-verifies its own output from disk by an independent code path before proceeding. Numbers trace to a printed command. Anything unmeasured is written `NOT MEASURED`, never estimated. Data is archived, never deleted.

### A10. Event independence and effective N — **new rail [v3-1]**
A2 controls how many questions were asked. It does **not** control whether the answers were independent, and they usually are not. Events cluster in volatile periods, and under A6 each event owns a forward window until first passage — so neighbouring events share overlapping future price paths and their outcomes are correlated. Treating N correlated events as N independent trials makes every standard error too small, every confidence interval too narrow, and every significance test too generous.

Therefore:

- **Minimum spacing is pre-registered.** Two events on the same instrument closer together than the pre-registered spacing are collapsed to one. Default: an event is suppressed if it falls inside a prior event's unresolved forward window. Any looser rule must be justified in the pre-registration.
- **Effective N is reported beside raw N**, always, in the same table. Where a spacing rule cannot make events independent — overlapping windows are unavoidable in a dense event family — significance is computed by **block bootstrap** with a block length at least the median first-passage time, not by an i.i.d. formula.
- **The variance ratio is printed**: `effective_N / raw_N`. A ratio far below 1 is not a defect to hide; it is the honest sample size, and it feeds A5's MDE, which uses **effective N**.
- The same rule binds A4's control draws, so the baseline is not built from a handful of repeatedly-sampled quiet windows.

---

## PART B — THE PHASES

### STAGE 1 — ANSWER THE GATING QUESTION FIRST
Before any infrastructure is built.

#### Phase 1 — Universe
BTCUSDT perpetual only. No expansion to ETH or SOL until the BTC work is validated.

#### Phase 2 — The gating study
**Question:** Binance trades carry an explicit aggressor flag. The delta / CVD / absorption family was measured dead on the NSE feed — but that feed could not tag aggressors at all (94.2% of depth intervals had no trade print; volume advanced in only 20.3% of tick intervals; delta sign carried 8–20% irreducible noise). Was that family dead everywhere, or only dead on that feed?

Three features only — CVD divergence, absorption, aggressive-flow imbalance — on free public Binance history, under all Part A rails. No database, no collectors, no infrastructure.

**🔴 [v3-4] The gate is symmetric.**

- **On a negative:** the family is dead with a clean aggressor tag too. Phases 3–5's storage and collection work for order-flow features is not built, and the roadmap re-plans around what survived. This direction was already correct in v2.
- **On a positive:** a positive here is a **discovery-stage result on one study**, and discovery-stage results are exactly what this document exists to distrust. It does **not** by itself authorise Stage 2 spend. Before any collector, schema or storage work begins, the Phase 2 positive must **survive confirmation on its own sealed set** (A3), at the ledger-adjusted bar in force (A2), with effective N and MDE stated (A10, A5).
- **If the positive fails its own confirmation**, Stage 2 does not start, and that failure is written up as the finding.
- **If Phase 2 is underpowered** (A5's MDE test), it returns `NOT MEASURED — POWER UNKNOWN` and gates nothing in either direction. An underpowered null must never be read as a negative, because "we could not see it" and "it is not there" are different sentences and only one of them stops a build.

### STAGE 2 — DATA, ONLY WHAT STAGE 1 JUSTIFIED

#### Phase 3 — Data sources
Primary: Binance futures — trades, order book, open interest, funding. Secondary: liquidations. Tertiary: event calendar.

**Correction carried from v2:** "Spoof Detection Score" requires order-by-order (L3) data. Binance's public feed provides L2 depth diffs. That feature cannot be built as specified — remove it or re-specify it against what L2 can actually show.

#### Phase 4 — Storage
Postgres / TimescaleDB, sized to what Stage 1 justified — not speculatively to 10 years of everything. Storage follows a proven need.

#### Phase 5 — Collectors
Auto-reconnect, gap detection and recovery, duplicate protection, latency and health monitoring, alerts.

#### Phase 6 — Data quality engine
Missing data, corrupted records, timestamp errors, feed gaps, duplicates, collector failure. Add: an arrival-rate report per period, and an aggressor-balance check — a field that reads a perfect 50/50 every period with no variance is a parsing bug, not a market fact.

### STAGE 3 — FEATURES AND CONTEXT

#### Phase 7 — Feature factory
Order-flow, positioning, liquidity and volatility features as originally listed, minus anything Stage 1 proved unreadable, minus L3-dependent features. Each feature is built once and tested under the Part A rails. Features are not strategies.

#### Phase 8 — News engine
FOMC, CPI, PPI, NFP, ETF, SEC, hacks, listings — with timestamp, type, importance, expected and actual impact.

#### Phase 9 — Market reaction engine
Fixed-clock return grids are replaced by the A6 first-passage / MAE-MFE object. Reaction is measured as path, not as a snapshot at 5m/15m/30m. Censoring reported. Event spacing per A10.

#### Phase 10 — Regime engine
Label every timestamp with regime, confidence and risk. The regime labeller **must be causal** — it may use only information available at that timestamp. A labeller that peeks forward will make every downstream result look excellent and every one of them will be false.

#### Phase 11 — Event study database
Store each detected setup with its state variables and its first-passage object (A6), not a fixed-horizon return row. Store its spacing/suppression flag and the funding stamps its path crossed (A10, A8).

### STAGE 4 — RESEARCH, UNDER THE LEDGER

#### Phase 12 — Hypothesis lab
H1–H15. Each hypothesis is pre-registered individually (A1), incremented into the ledger (A2), and carries its effective N and MDE (A10, A5) before it is run. Hypotheses run in a stated priority order — the ledger's bar rises with every test, so cheap shotgunning is self-defeating.

#### Phase 13 — Event study engine
For each hypothesis: every historical occurrence, its first-passage object, and results against both baselines (A4), in σ/R units (A7), with censoring shown, effective N and the variance ratio printed (A10).

Win rate, PF, Sharpe, Sortino and drawdown are reported **on discovery only** and are not a verdict. The verdict comes from confirmation (A3) and cost (A8).

#### Phase 14 — Timeframe discovery
The ledger's largest single consumer. Either pre-register a small timeframe set with a stated reason, or run the full grid and apply the full adjustment. Both are honest; picking the best cell after the fact is not. Note that A6's first-passage object already derives many (stop, target) pairs from one measurement — prefer that to multiplying cells.

#### Phase 15 — Edge discovery
Feature importance, information coefficient, robustness.

**🔴 The combination search is the single most dangerous phase in this document.** Searching "top combinations" across ~50 features runs to thousands of hypotheses, where roughly 1.5% of pure-noise combinations look profitable every year. This phase may only run after a specific pre-registered combination hypothesis exists, on discovery data, with the full ledger adjustment, and confirmed on the sealed set. **An open-ended combination sweep is prohibited.**

### STAGE 5 — BACKTEST AND VALIDATION

#### Phase 16 — Backtest engine
Event-driven, with commission, fees, slippage, latency, partial fills, execution delay, risk rules, position sizing. States whether entries cross the spread or post (A8). **Funding charged per A8's [v3-5] schedule rule — actual stamps crossed, paid and received reported separately.**

#### Phase 17 — Validation engine
In-sample, out-of-sample, walk-forward, Monte Carlo, cross-validation, regime and year robustness, exchange robustness.

**The critical structural fix, carried from v2:** this phase no longer arrives after discovery. Its out-of-sample component is the sealed set defined in A3 before Stage 4 began, and it is read once, per A3's single-use rule. Walk-forward run after an unrestricted search does not undo that search.

#### Phase 18 — Strategy promotion
Bar: trades > 1000, positive expectancy, PF > 1.5, Sharpe > 1, consistent across years and regimes, passes Monte Carlo and walk-forward. Plus, all mandatory:

- Positive expectancy **net of cost in R including funding charged per path**, not gross.
- Passed confirmation on an **unspent** sealed set, same sign, comparable magnitude.
- Cleared the ledger-adjusted bar in force at the time it was tested.
- Instrument calibration (A5) passed for the machine that scored it, **including recovery of an effect injected at the MDE**.
- **Effective N > 1000**, not raw N (A10). A thousand overlapping events is not a thousand trades.
- A named economic reason: who is paying, and why. Risk premium, forced flow, liquidity provision, or a rule change. **If nobody can be named as the payer, the result is a data pattern and does not promote, whatever its Sharpe.**
- A stated forward-sealed window: the rule is sealed and confirmed on data that did not exist when it was written, before any money.

### STAGE 6 — PRODUCTS

#### Phase 19 — Option income lab
Iron condor, iron fly, credit spreads, volatility selling; when premium selling works and fails, by regime. **This does not start from zero.** The existing NSE VRP work — the IV vs realised census, the exit and hedging studies, the paper forward test — is the input. Carry its findings *and its negative results* across rather than rediscovering them on crypto.

#### Phase 20 — Probability engine
The v1 weights (OI 25%, Liquidations 25%, Order Flow 20%, Liquidity 20%, Funding 10%) are invented — no measurement produced them. A prior nine-component weighted stack of exactly this shape has already been run on real data: gross +2.017R, **net −2.842R**, out-of-sample **PF 0.672**. Combining components does not average out their errors; it multiplies the ways to be wrong, and a stack is only as good as its worst sensor.

Therefore: weights are **derived from measured predictive contribution** on discovery data and confirmed on the sealed set, or Phase 20 is not built. No hand-set weights. Any component that failed Stage 1 or Phase 13 is **excluded entirely** rather than given a small weight.

#### Phase 21 — Portfolio engine
Trend, reversal, volatility and income strategies; expected return, drawdown, correlation matrix, allocation, risk budget. The correlation check must be honest about what diversification means: **the same strategy on twenty instruments is one bet in twenty costumes** — it fails everywhere at once in the regime its logic hates. Real diversification is across strategy families, not instrument count.

#### Phase 22 — Live dashboard
Regime, OI state, funding state, liquidation state, liquidity state, news risk, top active edge, confidence, expected return and risk, recommended action. **Every displayed number carries its provenance and its uncertainty** — measured or modelled, on what sample, with what confidence. A dashboard that shows a confident number with no provenance is how a research finding becomes a trading decision without anyone deciding.

---

## PART C — EXECUTION ORDER

1. **Phase 2 gating study** — the aggressor-family question, no infrastructure. Pre-registered with effective N and MDE stated before the first observation.
2. **Read its answer, then confirm it** — a positive is confirmed on its own sealed set before it authorises any spend **[v3-4]**; a negative stops the build; an underpowered result gates nothing.
3. Data sources, storage, collectors, quality engine — sized to that answer.
4. Feature factory, news, reaction, regime, event-study database.
5. Hypothesis ledger opened. Pre-registered hypotheses, in priority order.
6. Event studies against both baselines, in σ/R, with censoring, effective N and variance ratio.
7. Backtest with full cost including per-path funding.
8. Confirmation on an unspent sealed set — once, then it is spent.
9. Promotion only against the full Phase 18 bar, economic reason included.
10. Forward-sealed window before any money.
11. Products: option lab, probability engine, portfolio, dashboard.

**Never skip the rails. Never let validation run after the search it was meant to police. Never promote a result whose payer cannot be named. Never read a null from a test whose power was never stated.**

---

## PART D — OPERATING BOUNDARY FOR THIS PROGRAMME

- **Network:** Binance public market data only — `data.binance.vision` and `api.binance.com`, unauthenticated, GET, read-only. No API key, no secret, no signed endpoint, no `/order` or any trading path, on any host. Enforced in code, with the refusal demonstrated in a test, exactly as the Hyperliquid client does.
- **Disk:** a raw-cache ceiling is declared before the first bulk download and is enforced in code. The pull stops at the ceiling and reports rather than exceeding it. **Ceiling: NOT SET — awaiting the founder's number.** Free space at the time of writing: 68.82 GiB (30.15%).
- **Requests:** a hard request cap is declared before any bulk pull, persisted across processes, and never raised mid-run.
- **Nothing is deleted.** If disk pressure appears it is reported and the run stops.
- **No production contact:** no EC2, no cron, no `config.yaml`, nothing under `data/`, no primary checkout. All work in the `research/crypto-quant-lab` worktree.
