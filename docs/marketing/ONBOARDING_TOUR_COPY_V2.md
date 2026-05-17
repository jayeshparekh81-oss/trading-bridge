# Onboarding Tour Copy V2 — TRADETRI

**Draft status:** v0 — needs founder voice review, then react-joyride wiring.
**Audience:** First-time TRADETRI users running the in-app product tour.
**Tone:** Hinglish bhai-tone, light. Each step ≤ 50 words. The tour is a guide, not a lecture.
**Format:** designed for `react-joyride` step objects (see `frontend/src/components/onboarding/OnboardingTour.tsx` — already imports the lib; tour steps live in a separate copy file currently).

---

## What this refresh changes vs V1

V1 of the tour was written before:
- The Strategy Templates gallery shipped (now 45+ templates browsable)
- The Phase 5 Strategy Builder scaffold landed
- The Phase 5 roadmap was published with explicit Phase 7-8 options
- The Strategy Detail Page got cloned-from-template UX fixes

V2 refresh:
- 4 new steps walking through the templates gallery → clone flow
- "Available with Strategy Builder" honest messaging in tour copy
  (matches the actual UI's Phase 5 framing)
- Removes 1 step about "Expert Builder live trading" because live
  trading is paper-mode-only for the first 30 days now
- Renames "Backtest" step to "Strategy Tester" matching the
  current navigation label

---

## Tour step copy (V2)

### Step 0 — Welcome (page: `/dashboard`)

```
Bhai, TRADETRI mein swagat hai.

Yeh tour ~2 minute lega. Skip kar sakte ho, but pehli baar usefull hai —
113 templates, 230 indicators, ek paper-mode-first runtime, sab kuch
samajh aa jayega.

[Skip] [Start tour →]
```

### Step 1 — Dashboard overview (target: `.dashboard-summary-card`)

```
Yeh aap ka dashboard.

Numbers strict factual hain — paper-mode trades, live trades, P&L
attribution. AI nahi kar raha — Python compute kar raha hai.

Click anywhere outside the tooltip to keep exploring. Tour aage badhega.
```

### Step 2 — Strategy Templates gallery (target: nav `/strategies/templates`)

```
113 strategy templates yahan se browse karo.

— 45 active (preview only — full trading Phase 5 mein unlock)
— 5 coming soon
— 63 options (Phase 7-8 ke saath unlock)

Categories: Trend, Momentum, Mean Reversion, Breakout, Pattern, Volume.

Filters left mein hain.
```

### Step 3 — Template card (target: `[data-testid^=template-card]:first-child`)

```
Har card pe 3 cheez dikhao:

— Indicator stack (kis kis ka use ho raha hai)
— Risk level + complexity
— "Clone (preview only)" button

Clone karne se template aap ki strategies list mein chala jata hai
— bookmark karne ke liye.
```

### Step 4 — Clone CTA (target: `[data-testid=template-clone-button]`)

```
"Clone (preview only)" click karo.

Aap ki strategies list mein ek nayi strategy ban jayegi. Template ka
config (indicators, SL %, TP %, trading hours) preview mein dikhega.

Live trading auto-enable nahi hota — Phase 5 Strategy Builder ke
saath aayega.
```

### Step 5 — Strategies list (target: nav `/strategies`)

```
Aap ki strategies list.

Filhal 2 type ho sakte hain:

— Template-cloned (purple badge "Cloned from template")
— Hand-built (Phase 5 supervised work mein activate hoga)

Click karke detail page khol sakte ho.
```

### Step 6 — Strategy detail — template badge (target: `.strategy-template-origin-badge`)

```
Template-cloned strategies pe yeh badge dikhega.

Niche template ke defaults preview honge: SL %, TP %, indicators,
trading hours.

"Available with Strategy Builder" — yeh button Phase 5 ship hote hi
backtest run karne lagega.
```

### Step 7 — Indicator Library (target: nav `/strategies/indicators`)

```
230+ indicators ka catalogue.

Filter by:
— Category (Trend, Momentum, Volatility, Volume, Pattern, S/R)
— Difficulty (beginner / intermediate / expert)
— Pine alias (TradingView se aane wale ko khilane ke liye)

Click karke detail modal khulta hai — formula + AI explanation +
parameter ranges.
```

### Step 8 — Strategy Builder scaffold (target: nav `/strategies/builder`)

```
Yeh Phase 5 ka no-code visual builder.

Filhal scaffold hai — drag-drop activate hoga jab supervised work
land karega.

Left side indicator library, middle canvas, right inspector.

Beta access first 500 waitlist sign-ups ko.
```

### Step 9 — Strategy Tester (target: nav `/strategies/[id]/backtest`)

```
Live tester. Ek strategy chuno, candles range pick karo, backtest run karo.

3 reports milte hain:

— Equity curve + trade-by-trade P&L
— Reliability score (overfitting check)
— Strategy Coach card (Hinglish health summary)

Phase 9 mein truth score + walk-forward + paper-vs-live deviation
add hoga.
```

### Step 10 — Compliance + Disclaimer (target: footer)

```
Footer mein har page pe disclaimer:

— "Backtest is not Proof"
— SEBI IA registration status (in flight)
— Public Tradetri Truth Score doc link

Compliance as feature, not afterthought. Yeh aapke liye hai —
hum nahi chahte ke aap "guaranteed returns" sun ke aaye ho.
```

### Step 11 — Wrap (target: top nav)

```
Tour khatam.

Next steps:

1. Ek template clone karo (yes, abhi)
2. Paper-trade run karo (NIFTY 5-min default fine hai)
3. 24 ghante baad dashboard pe report dekho

Reply karke batao kya feel hua. Inbox: hello@tradetri.com.

[Done]
```

---

## Implementation notes for the engineer wiring this

- `react-joyride` ships with TypeScript types but the existing
  `OnboardingTour.tsx` has typecheck errors against the lib's
  current API. Bridge those before wiring — see `tsc --noEmit` output.
- Each step's `target` selector above is a hint — verify against
  actual DOM in the live app (some classNames may have changed
  since V1 wrote them).
- The tour copy uses Hinglish at a "comfortable for an Indian retail
  trader who reads Twitter daily" register. If your user-research
  shows a more formal register is preferred, V2 has room to dial
  down — but don't lose the warmth.
- All 12 steps total ≤ 600 words → reads in ~3 min if user actually
  reads vs ~1 min if they skim. That's the right load.

---

## Open questions for review

1. **Tone calibration — bhai vs neutral.** V2 leans heavier on
   bhai-tone than V1 did. For first-time users from non-Hinglish
   audiences this can read as alienating. Two options:
   - (A) Ship one tour, bhai-tone (current draft)
   - (B) Ship two tours, locale-detect, default to bhai-tone
   Recommendation: (A) for v2.0; revisit if onboarding-completion
   metrics drop. Decision needed.

2. **Strategy Builder step (8) — keep or skip?** The builder is
   scaffold-only at launch. Some users tour it, find it dead, and
   conclude the whole product is half-finished. Two options:
   - Keep step 8 with "scaffold preview" framing (current)
   - Skip step 8 entirely until PR-D lands
   Recommendation: KEEP. Honest signaling > hiding the truth.

3. **Skip / restart affordance.** Currently shown only on step 0
   (Skip) and step 11 (Done). Users mid-tour can't easily exit.
   Add an X button to every step? Standard react-joyride pattern.
   Decision needed.

4. **Step count — 12 too many?** Microsoft research suggests
   onboarding tours past 7-8 steps see steep drop-off. We're at 12.
   Trim candidates:
   - Step 0 + 1 can merge (welcome + dashboard)
   - Step 5 + 6 can merge (strategies list + detail page)
   - Step 10 (compliance footer) is important but maybe an
     end-of-tour summary card not a separate step
   Recommendation: trim to 8-9 steps in v2.1 after measuring
   v2.0 completion rate.

5. **Translation strategy.** Hindi-only variant for the Hindi-
   reading retail trader segment? V1 was English-only; V2 is
   Hinglish-only. Pure Hindi (Devanagari) is a separate
   translation pass. Decision needed: do it for v2.0 or wait?
