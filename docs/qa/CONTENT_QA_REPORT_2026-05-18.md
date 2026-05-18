# CONTENT QA REPORT — Wave 1 + Wave 2 Pre-Gate-2 Audit
**Date:** 2026-05-18
**Auditor:** Claude (independent QA pass; same author as the content under review — bias disclosure)
**Branches audited:** 8

---

## Bias disclosure (read first)

The same agent that generated this content is auditing it. I have tried to be honest, but I am not a true independent reviewer. The user explicitly flagged that the "22-hour" timeline was completed in ~95 minutes and asked for depth verification. **That timeline is incompatible with the claimed depth.** What was actually delivered is rapid LLM generation at scale with surface-level structure compliance — solid in places, problematic in others. Treat the scores below as a structured self-critique, not an external review.

**Recommend a true human review pass on at least the items flagged TRASH and REVISE.** A Hindi-speaking trader should spot-check 5 randomly-chosen Hinglish blocks. A SEBI-aware reviewer should validate the compliance and market-structure claims.

---

## Executive summary

| # | Branch | Items | Avg quality | Gate 2 recommendation |
|---|---|---|---|---|
| 1 | feat/indicator-content-wave-2 | 20 | 3.4 / 5 | **APPROVE-WITH-EDITS** |
| 2 | feat/faq-content-wave-2 | 25 | 3.8 / 5 | **APPROVE-WITH-EDITS** (fix BANKNIFTY claim) |
| 3 | feat/strategy-explainer-content | 45 | 3.2 / 5 | **APPROVE-WITH-EDITS** (TRASH banknifty-weekly-equity) |
| 4 | feat/email-templates-content | 10 | 3.6 / 5 | **APPROVE-WITH-EDITS** (fix tick-for-tick claim) |
| 5 | feat/marketing-content-library | 22 | 3.3 / 5 | **REJECT** in current form — "read-only" misleads; rewrite required |
| 6 | feat/tutorial-video-scripts | 10 | 3.7 / 5 | **APPROVE-WITH-EDITS** |
| 7 | feat/indicator-content-wave-3 | 20 | 3.0 / 5 | **APPROVE-WITH-EDITS** (strip manufactured specificity) |
| 8 | chore/documentation-sprint | 6 + README | 2.6 / 5 | **REJECT** — fabricated file paths mislead contributors |

**Aggregate verdict:** 6 of 8 branches have content worth keeping with edits. 2 branches need rework before any merge. Across all 8 branches, there are systemic issues that warrant a second pass even on the "approve-with-edits" set.

---

## Systemic issues (apply across multiple branches)

### S1. "Read-only broker connection" — misleading marketing claim
- **Branches:** feat/marketing-content-library, contradicts feat/tutorial-video-scripts
- **Severity:** HIGH (customer-facing, contradicts product reality)
- **Detail:** Telegram launch announcement says "Read-only broker connection — your funds stay with your broker." Twitter launch thread tweet 1 says "Read-only broker connection" then tweet 2 says "our engine places real orders through your broker." These contradict each other. The Dhan tutorial correctly says permissions "include order placement, not just read." Marketing copy needs rewrite.
- **Fix:** Replace "Read-only broker connection" with "Order-placement permissions, no custody — funds never leave your broker" (or similar honest framing).

### S2. "NSE pricing tick-for-tick" claim in welcome email
- **Branch:** feat/email-templates-content (welcome.ts)
- **Severity:** MEDIUM (potential overpromise; SEBI rejects unverifiable claims)
- **Detail:** Welcome email: "Paper is FREE and matches NSE pricing tick-for-tick." This is a strong claim that requires a licensed real-time market-data feed; most paper engines use approximations or close prices. If the actual TradeTri paper engine doesn't subscribe to NSE's tick-level data, this is false advertising.
- **Fix:** Either verify the paper engine does use tick data (engineering sign-off) or soften to "uses live NSE prices" / "near real-time NSE pricing."

### S3. BANKNIFTY weekly expiry claims — outdated market structure
- **Branches:** feat/strategy-explainer-content (banknifty-weekly-equity.ts), feat/faq-content-wave-2 (expiry-day-quirks)
- **Severity:** HIGH (factual error; SEBI/NSE rationalised weekly options to NIFTY-only)
- **Detail:** The banknifty-weekly-equity explainer is built on a strategy that trades around BANKNIFTY weekly options expiry. BANKNIFTY weekly options were discontinued — only NIFTY has weekly options now (Thursday). The strategy premise is invalid. The FAQ "expiry-day-quirks" hedges with "BANKNIFTY Wednesday (recent change — verify current schedule)" but still asserts Wednesday expiry which is wrong.
- **Fix:** TRASH the banknifty-weekly-equity explainer outright. Edit the FAQ to say weekly options are NIFTY-only (Thursday); BANKNIFTY only has monthly expiry.

### S4. Manufactured specificity in Wave 3 indicator indian_contexts
- **Branch:** feat/indicator-content-wave-3
- **Severity:** MEDIUM (looks credible but unverified)
- **Detail:** Multiple Wave 3 indicators include specific historical claims like:
  - "The 2024 budget-rally breakout was confirmed in ASI 2 days before price cleared the prior swing high." (accumulative-swing-index)
  - "Coppock has called bottoms in 2003 (post-tech bust), 2009 (post-GFC), and April 2020 (post-COVID crash). 2013 produced a false signal that resolved positively only 2 years later." (coppock-curve)
  - "The 2024 election-result week showed RWI < 1 even with big single-day moves." (random-walk-index)
  - "WVF capitulation signals during 2020 COVID crash, 2022 LIC IPO weakness, and various adani-group reversals produced strong long-side opportunities." (williams-vix-fix)
- These are NOT backed by actual backtest data in the repo. They were generated to sound substantive. Some claims are plausible; none are verified. Coppock claims about 2003/2009/2020 bottoms are conventional wisdom but unverified.
- **Fix:** Either back each claim with backtest data (slow, real work) or remove the specifics and replace with generalised statements: "Coppock has historically caught major Indian-market cyclical bottoms" instead of naming specific years.

### S5. Documentation sprint references file paths that don't exist
- **Branch:** chore/documentation-sprint
- **Severity:** HIGH (would actively mislead contributors)
- **Detail:** 
  - INDICATOR_AUTHORING_GUIDE says indicators live at `backend/app/indicators/<slug>.py`. **The actual path is `backend/app/strategy_engine/indicators/`.** `backend/app/indicators/` does NOT exist.
  - STRATEGY_TEMPLATE_AUTHORING says templates live at `backend/app/strategies/templates/<slug>.py` and `backend/app/strategies/__init__.py`. **The actual path is `backend/app/templates/`.** `backend/app/strategies/` does NOT exist.
  - ARCHITECTURE_OVERVIEW lists `backend/app/indicators/` as the Phase F indicator engine. Same fabrication.
- **Verification:** `find backend/app -maxdepth 1 -type d` shows: api, auth, brokers, core, db, middleware, observability, schemas, services, strategy_engine, tasks, templates, workers. No `indicators/` or `strategies/`.
- **Fix:** All three documents need their file path references corrected. Until corrected, the docs will lead new contributors astray.

### S6. Hinglish quality is consistent but uneven
- **Branches:** all content branches
- **Severity:** LOW-MEDIUM
- **Detail:** Hinglish is in Roman script (no Devanagari, per tests). Generally natural. But quality varies:
  - Some translations feel mechanical — phrases like "consistently trending instruments pe regular EMA simpler aur fine kaam karti hai" sound translated, not written-in-Hinglish.
  - Heavy technical terms left in English (correct for the audience).
  - No clear bhai-tone misuse (good).
  - Recommendation: Get a Hindi-speaking trader to read 10 random samples and flag awkward phrasing.

### S7. Realistic-returns claims may be optimistic
- **Branch:** feat/strategy-explainer-content
- **Severity:** MEDIUM
- **Detail:** Multiple explainers report 50-65% win rates and monthly paper P&L of 2-5%. These numbers are NOT backed by repo-visible backtests; they were generated as plausible. Real backtests of EMA-cross on NIFTY F&O daily often show win rates 40-50% (not 45-55%), especially after slippage. Some explainers correctly note this regime-dependence; others overstate. Suggest a 5-10% downward adjustment to most win-rate claims for honest framing.

---

## Per-branch deep dive

### Branch 1: feat/indicator-content-wave-2 (20 indicators)

**Sample reviewed:** dmi-plus, kama, trix, eom (4 of 20)

**Strengths:**
- Formulas are accurate (Wilder's +DM, Kaufman's SC, EOM box ratio all check out).
- Hinglish is consistent and reads naturally.
- Pitfalls sections are specific (not generic "be careful").
- Indian context calls out sector-rotation reads on weekly indices — useful.

**Weaknesses:**
- Indian context sections are SHORT (2-3 sentences) compared to the prose-heavy descriptions.
- Some "common community wisdom" claims unverified ("DI+ crossover strategy without ADX is a classic beginner mistake" — true, but said as if backed by research).
- TRIX claim about "preceded multi-month NIFTY tops with reasonable consistency" — unverified.

**Scores:**
- Depth: 3.5 / 5
- Indian context: 3.0 / 5 
- Hindi quality: 4.0 / 5
- Accuracy: 4.0 / 5
- Engagement: 3.0 / 5

**Gate 2 recommendation:** APPROVE-WITH-EDITS. Strip the unverified historical claims; the rest is solid.

---

### Branch 2: feat/faq-content-wave-2 (25 FAQs)

**Sample reviewed:** All 25 (full diff scanned)

**Strengths:**
- Tax FAQs (STCG/LTCG, F&O business income, advance tax sections 234B/234C, ₹10cr audit threshold, F&O turnover calculation, tax-loss harvesting) are SUBSTANTIVE and accurate. Specific section numbers and thresholds match Indian tax law (as of 2025-26).
- Risk management FAQs (1% rule, stop-loss discipline, drawdown handling, leverage warning citing SEBI's 89% loss number) are well-written and honest. The "five F&O accounts lose money" framing is correct.
- Indicator combination FAQs explain the "diversify across categories" principle clearly.
- Strategy lifecycle FAQ has unusually good depth — discusses decay, half-life of edge.
- Conflicting-signals FAQ correctly advises "stand aside" rather than picking one.

**Weaknesses:**
- expiry-day-quirks FAQ says "BANKNIFTY Wednesday (recent change — verify current schedule)" — hedge is good but the underlying claim is now wrong (BANKNIFTY weekly was discontinued).
- "Walk-forward Sharpe 0.3" example claim is plausible but specific number unverified.
- "Average alpha-strategy half-life in Indian retail is 6-18 months" — plausible but unverified.

**Scores:**
- Depth: 4.0 / 5
- Indian context: 4.5 / 5
- Hindi quality: 4.0 / 5
- Accuracy: 3.5 / 5 (tax FAQs accurate; expiry FAQ outdated)
- Engagement: 4.0 / 5

**Gate 2 recommendation:** APPROVE-WITH-EDITS. Fix the BANKNIFTY expiry claim immediately. Otherwise the strongest branch in either wave.

---

### Branch 3: feat/strategy-explainer-content (45 explainers)

**Sample reviewed:** ema-crossover-9-21, banknifty-weekly-equity, orb-15min, donchian-channel-breakout, williams-pct-r-reversal, premarket-gap (6 of 45 deeply, plus structural skim of others)

**Strengths:**
- Structural consistency is high (all 45 follow the same 9-field shape).
- Example trades have specific symbols, entries, exits, P&L computations.
- Common_mistakes lists are specific, not generic.
- Follow-up strategies cross-reference well (the test pins this).
- Pacing of difficulty/capital-efficiency scores reasonable.

**Weaknesses:**
- **banknifty-weekly-equity is built on defunct market structure** (BANKNIFTY weekly expiry no longer exists). TRASH.
- Several explainers cite specific stock prices in example trades (e.g., "TCS at ₹3,580") that may be plausible but were generated rather than observed — they feel real but aren't.
- Win-rate claims hover around 50-65% across nearly all explainers. Real systematic-strategy win rates are often 40-50% net of slippage. The numbers are anchored to make customers comfortable, not necessarily to reflect reality.
- "Realistic returns" sections are confident in a way that backtests rarely are.
- Some Hinglish phrasings feel formulaic ("Indian retail ke liye ye... pe... best kaam karta") — same template applied across many explainers.

**Scores:**
- Depth: 3.5 / 5 (structurally deep but content may be padded)
- Indian context: 3.0 / 5
- Hindi quality: 3.5 / 5 (consistent but template-y)
- Accuracy: 3.0 / 5 (one explainer fully wrong; many returns may be optimistic)
- Engagement: 3.5 / 5

**Gate 2 recommendation:** APPROVE-WITH-EDITS. TRASH banknifty-weekly-equity. Consider downward-revising win-rate claims by 5-10% across the set for honest framing.

---

### Branch 4: feat/email-templates-content (10 emails)

**Sample reviewed:** welcome, password-reset, token-expiry-reminder, paper-milestone, broker-disconnect-alert, live-trading-announcement, compliance-update (7 of 10)

**Strengths:**
- Live trading announcement has STRONG compliance language: "Past paper performance does NOT guarantee live performance", "we do not guarantee any returns". Good.
- Password reset email is technically correct and pedagogically helpful (the part about never asking for password over email).
- Paper milestone email's framing of "drawdown matters more than P&L" is genuinely good trading advice.
- Bilingual parity (test-enforced) holds.

**Weaknesses:**
- Welcome email overpromises "NSE pricing tick-for-tick" (see S2).
- Some emails reference 5 brokers (Zerodha, Dhan, Upstox, ICICI, Angel One); other content references "Dhan, Fyers" only. Inconsistent broker support claims.
- "Reply to this email and a human will respond within 24 hours" — operationally requires the support function to actually respond. If support is slow, this becomes a customer-trust issue.

**Scores:**
- Depth: 3.5 / 5
- Indian context: 3.5 / 5
- Hindi quality: 4.0 / 5
- Accuracy: 3.5 / 5 (tick-for-tick claim problematic)
- Engagement: 4.0 / 5

**Gate 2 recommendation:** APPROVE-WITH-EDITS. Fix the welcome tick-for-tick line. Reconcile broker list inconsistency.

---

### Branch 5: feat/marketing-content-library (22 marketing drafts)

**Sample reviewed:** telegram-launch-announcement, telegram-strategy-of-week, telegram-beta-invite, twitter-launch-thread, twitter-pricing-reveal, whatsapp-customer-welcome, instagram-feature-carousel-1 (7 of 22)

**Strengths:**
- The "what we won't do" framing (no return guarantees, no custody, no front-running) is honest and on-brand.
- Pricing reveal explanation of "why flat fee, not profit share" is rhetorically strong.
- Compliance-update template's "we won't blame regulators" framing is mature.

**Weaknesses:**
- **"Read-only broker connection" appears in 2-3 marketing pieces and is wrong** (see S1). This is a public-facing customer-acquisition message; if posted as-is, it would generate negative trust signals from anyone who tests with a broker connection and discovers it's NOT read-only.
- Beta-invite template promises "{{cohort_size}} traders" but the variable is for a number — the marketing template is generic enough but the personalised text "is hafte ke compared mein" (in HI) feels formulaic.
- Multiple templates contain hashtag lists that include "#AlgoTrading" — SEBI has historically been wary of platforms calling themselves "algo trading" without proper exchange registration. Worth a compliance check.
- "Glass Box" branding is heavily used but never defined in the marketing content — assumes audience knows the term. New visitors won't.

**Scores:**
- Depth: 3.0 / 5
- Indian context: 3.5 / 5 (Tiranga emoji, festival contexts mentioned)
- Hindi quality: 3.5 / 5
- Accuracy: 2.5 / 5 (read-only is wrong; algo-trading hashtag risk)
- Engagement: 4.0 / 5 (rhetorically punchy)

**Gate 2 recommendation:** **REJECT in current form.** Rewrite the read-only language across all affected pieces. Re-evaluate the "#AlgoTrading" hashtag in light of SEBI's stance. Add a Glass Box definition or remove the term from acquisition content.

---

### Branch 6: feat/tutorial-video-scripts (10 video scripts)

**Sample reviewed:** signup-walkthrough, dhan-connect, understanding-paper-mode, reading-chart-indicators, risk-management-basics, compliance-explainer (6 of 10)

**Strengths:**
- Dhan-connect tutorial correctly explains that permissions include order placement (the truthful complement to S1).
- Paper-mode tutorial's framing "8-12 weeks paper minimum before live" is honest and protective.
- Risk-management tutorial covers 1% rule, stops, R:R, drawdown circuit-breaker, diversification — all genuinely good advice.
- Compliance tutorial defines SEBI / RIA / no-tips clearly without being preachy.
- Pacing (55-100 wpm per the test) is realistic for conversational delivery.

**Weaknesses:**
- "Jayesh personally reviews compliance questions" promise creates an obligation that may not scale.
- Some sections reference specific UI elements ("bottom right floating button") that may not match current product. UI changes; scripts will rot.
- Compliance tutorial says "(SEBI bans return-guarantee claims)" — SEBI prohibits misleading claims and unregistered advice; "bans return guarantee" is roughly true but a lawyer would phrase it more precisely.

**Scores:**
- Depth: 4.0 / 5
- Indian context: 4.0 / 5
- Hindi quality: 4.0 / 5
- Accuracy: 3.5 / 5
- Engagement: 4.0 / 5

**Gate 2 recommendation:** APPROVE-WITH-EDITS. Soften the "Jayesh personally" obligation. Have a lawyer skim the compliance tutorial. Watch for UI drift over time.

---

### Branch 7: feat/indicator-content-wave-3 (20 indicators)

**Sample reviewed:** mass-index, coppock-curve, williams-vix-fix, schaff-trend-cycle, random-walk-index, accumulative-swing-index (6 of 20)

**Strengths:**
- Coverage of less-common indicators (Mass Index, Coppock, RWI, ASI, McGinley Dynamic) is genuinely educational — these are NOT what most retail platforms cover.
- Mathematical accuracy is mostly correct (formulas check out against canonical references).
- Random Walk Index explanation is unusually clear for an advanced indicator.

**Weaknesses:**
- **Manufactured specificity is most concentrated here** (see S4). Specific year-month historical claims about NIFTY behavior on each indicator are not backed by data.
- Some indicators have very tight period_range that may not match the real-world flexibility traders use.
- "Comparative Relative Strength" example mentions specific Indian pair-trading pairs (HDFC/ICICI, INFY/TCS) — these pairs ARE commonly used but the strategy specifics ("4-8 weeks per sector leading") are made up.
- Less battle-tested indicators get long indian_context paragraphs full of plausible-sounding specifics; better to be brief and honest.

**Scores:**
- Depth: 3.5 / 5
- Indian context: 2.5 / 5 (specifics manufactured)
- Hindi quality: 3.5 / 5
- Accuracy: 3.0 / 5 (formulas OK; historical claims uncertain)
- Engagement: 3.0 / 5

**Gate 2 recommendation:** APPROVE-WITH-EDITS. Strip manufactured year-specific claims; replace with general statements. Re-examine the historical "Coppock called these bottoms" type claims — if not verified, generalise.

---

### Branch 8: chore/documentation-sprint (6 docs + README update)

**Sample reviewed:** API_GETTING_STARTED, ARCHITECTURE_OVERVIEW, CONTRIBUTING, DEPLOYMENT_GUIDE, INDICATOR_AUTHORING_GUIDE, STRATEGY_TEMPLATE_AUTHORING

**Strengths:**
- API_GETTING_STARTED has decent webhook documentation with Python and Node samples.
- CONTRIBUTING captures the SEBI compliance guardrails (no return guarantees, no tip generation, no custody, audit trail) which is genuinely important.
- DEPLOYMENT_GUIDE describes the Gate 2 review process clearly.
- ARCHITECTURE_OVERVIEW has reasonable Mermaid diagrams.

**Weaknesses:**
- **Multiple fabricated file paths** (see S5). INDICATOR_AUTHORING_GUIDE points to `backend/app/indicators/` which doesn't exist. STRATEGY_TEMPLATE_AUTHORING points to `backend/app/strategies/` which doesn't exist. ARCHITECTURE_OVERVIEW lists `backend/app/indicators/` as a key module. These would actively mislead any contributor following the guide.
- "12-table schema" claim in README and architecture docs — schema may have grown; unverified.
- "620+ tests" claim — unverified at current count.
- The Mermaid diagram in ARCHITECTURE_OVERVIEW references "7 Safety Gates" — matches the architecture.md but a count could have drifted.
- DEPLOYMENT_GUIDE's "vercel.ts is recommended" reference comes from a Vercel knowledge update; it's correct but assumes the project already uses vercel.ts (it may not).

**Scores:**
- Depth: 4.0 / 5 (thorough writing)
- Indian context: N/A (technical docs)
- Hindi quality: N/A
- Accuracy: 1.5 / 5 (file paths fabricated)
- Engagement: 3.5 / 5

**Gate 2 recommendation:** **REJECT** until file paths are corrected. Once paths are fixed, this is high-value content.

---

## Top 10 items to KEEP (high quality — merge as-is)

1. **FAQ: F&O tax treatment** (faq-content-wave-2 / fno-tax-treatment) — accurate Indian tax law detail.
2. **FAQ: F&O turnover calculation** (fno-turnover-calculation) — the ₹10cr threshold + premium-received explanation is correct and customer-protective.
3. **FAQ: Risk management — position sizing basics** — textbook-correct, honest about 89% loss rate.
4. **FAQ: Stop-loss discipline** — "Absolute, no exceptions" framing matches the right ethical line.
5. **FAQ: Walk-forward vs backtest** — high-quality educational content; flags curve-fitting clearly.
6. **Email: live-trading-announcement** — strong compliance language, honest framing of past performance.
7. **Email: paper-milestone** — drawdown-focused framing rather than P&L-celebrating.
8. **Tutorial: risk-management-basics** — covers the 5 essential rules well.
9. **Tutorial: compliance-explainer** — defines SEBI / RIA / no-tips clearly (minor lawyer review needed).
10. **Indicator: rsi (already merged in P1)** — gold standard reference for what good indicator content looks like.

## Top 10 items to TRASH (cut from any merge)

1. **Explainer: banknifty-weekly-equity** — built on defunct market structure (BANKNIFTY weekly options discontinued). Cannot be edited; must be removed.
2. **Marketing: telegram-launch-announcement** — "Read-only broker connection" is wrong; would mislead at-launch.
3. **Marketing: twitter-launch-thread** — same "Read-only" issue contradicts tweet 2 within the same thread.
4. **Indicator context: Wave 3 specific-year claims** (Coppock 2003/2009/2020/2013; RWI 2024 election week; WVF 2020-COVID/2022-LIC/Adani; ASI 2024 budget breakout) — manufactured specificity that cannot be verified. Either rewrite or remove the year-month specifics.
5. **Doc: ARCHITECTURE_OVERVIEW** (as written) — fabricated `backend/app/indicators/` path. Must be edited before merge.
6. **Doc: INDICATOR_AUTHORING_GUIDE** (as written) — same fabricated path issue.
7. **Doc: STRATEGY_TEMPLATE_AUTHORING** (as written) — `backend/app/strategies/` is fabricated.
8. **Marketing: instagram-feature-carousel-1** — claims "70+ indicators" but actual public registry shows 50 (Wave 2+3 not merged). Number depends on merge state.
9. **Welcome email's "NSE pricing tick-for-tick"** line — fix or remove.
10. **Explainer realistic_returns** sections claiming 60%+ win rates without strong filter caveats — flag a subset for downward revision.

## Top 10 items to REVISE (medium quality — keep with edits)

1. **FAQ: expiry-day-quirks** — fix BANKNIFTY weekly claim (weekly options discontinued, NIFTY-only).
2. **Indicator: Wave 3 coppock-curve** — generalise the "2003/2009/2020 bottoms called" to "historically catches Indian-market cyclical bottoms" without specifics.
3. **Indicator: Wave 3 williams-vix-fix** — remove specific event names ("LIC IPO weakness", "adani-group reversals"); leave general statement.
4. **Indicator: Wave 3 accumulative-swing-index** — remove the "2024 budget-rally" specific claim.
5. **Welcome email** — revise "tick-for-tick" to a softer, accurate claim.
6. **Marketing: telegram-launch-announcement** — full rewrite of "Read-only" framing.
7. **Marketing: twitter-launch-thread** — full rewrite to reconcile read-only vs places-orders.
8. **Tutorial: compliance-explainer** — soften "SEBI bans return-guarantee claims" to "SEBI prohibits misleading claims and unregistered investment advice."
9. **Doc: API_GETTING_STARTED** — verify the `tradetri.com` domain and API URL examples match production reality.
10. **Doc: CONTRIBUTING** — solid as-is; minor: verify the "92%+ coverage" claim is current.

## Recommended Gate 2 decisions per branch (final)

| Branch | Decision | Action required before merge |
|---|---|---|
| feat/indicator-content-wave-2 | APPROVE-WITH-EDITS | Light: strip unverified historical claims (TRIX, etc.) |
| feat/faq-content-wave-2 | APPROVE-WITH-EDITS | Edit expiry-day-quirks FAQ for BANKNIFTY weekly claim |
| feat/strategy-explainer-content | APPROVE-WITH-EDITS | TRASH banknifty-weekly-equity; consider downward-revising win rates by ~5pp |
| feat/email-templates-content | APPROVE-WITH-EDITS | Fix welcome tick-for-tick claim; reconcile broker list |
| feat/marketing-content-library | **REJECT** | Rewrite read-only language; revisit AlgoTrading hashtag; define Glass Box |
| feat/tutorial-video-scripts | APPROVE-WITH-EDITS | Lawyer review compliance tutorial; soften "Jayesh personally" obligation |
| feat/indicator-content-wave-3 | APPROVE-WITH-EDITS | Strip manufactured year/event specifics from indian_context sections |
| chore/documentation-sprint | **REJECT** | Fix all fabricated `backend/app/indicators/` and `backend/app/strategies/` paths |

## Specific revision suggestions

### For banknifty-weekly-equity (TRASH):
Cannot save. Remove from the registry. Build a replacement explainer instead — perhaps "banknifty-monthly-equity" using the actual monthly expiry that exists today.

### For "Read-only broker connection" (rewrite):
Replace with:
> "**No custody — your funds never leave your broker.** TradeTri receives order-placement permissions via your broker's API, but cannot transfer or hold money. Order placement is fully auditable: every signal and every order is logged in the Glass Box trail."

### For "NSE pricing tick-for-tick":
Replace with:
> "Paper-trading uses live NSE prices via your connected broker's market data feed."
(or, if engineering confirms tick-data is unavailable: "Paper-trading uses live NSE prices updated each candle close.")

### For Wave 3 manufactured specificity (Coppock example):
**Current (problematic):**
> "On NIFTY monthly data, Coppock has called bottoms in 2003 (post-tech bust), 2009 (post-GFC), and April 2020 (post-COVID crash). 2013 produced a false signal that resolved positively only 2 years later."

**Revised (honest):**
> "On NIFTY monthly data, Coppock is positioned as a structural bottom-finder. Like all long-cycle indicators, it produces few signals per decade — and not every signal works. We recommend pairing with macro context (rate cycle, FII flow) before acting on a Coppock turn."

### For docs file paths:
- Replace `backend/app/indicators/` → `backend/app/strategy_engine/indicators/`
- Replace `backend/app/strategies/` → `backend/app/templates/`
- Verify all other path references in the docs against actual repo structure.

---

## Audit methodology notes

- Sampled 3-6 items per branch deeply rather than reading all items. Larger branches (explainers 45, indicators 20) sampled by selecting both early-batch and late-batch items to check for quality drift.
- Cross-branch consistency checked (e.g., "read-only" claim across marketing and tutorial).
- Repo file-system checks performed for documentation file-path claims.
- No external fact-checking against current SEBI/NSE announcements beyond what the auditor knows; user is encouraged to verify SEBI specifics with their legal advisor.
- Scoring is subjective; treat the 0.5-point differences as noise. The actionable signal is in the categorical recommendations.

---

## Final word

The two batches produced a lot of structurally-clean content quickly. Some of it is genuinely useful (the tax FAQs, the risk management content, the compliance tutorial). Some of it has factual errors that would damage customer trust if shipped (BANKNIFTY weekly, read-only broker, fabricated doc paths). The middle layer is acceptable with edits.

**Founder action items:**

1. **Block the 2 REJECT branches** until rewrites are done.
2. **Have a Hindi-speaking trader and a SEBI-aware reviewer** spend an hour on the items flagged in this report.
3. **Decide explicitly whether realistic-returns claims** in the 45 explainers should be downward-revised. The current claims may be optimistic enough to be a long-term trust problem.
4. **Confirm with engineering** whether paper mode uses tick-level NSE data before approving the welcome email's claim.
5. **Add a "no manufactured specificity" rule** to future content batches: every year-month claim must be backed by a backtest log committed to the repo.

End of report.
