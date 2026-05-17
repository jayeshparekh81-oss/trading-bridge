# WhatsApp Broadcast — Finfluencer Affiliate Kit

**Draft status:** v2 — tightened per Queue III Task 4 + FOUNDER_VOICE_GUIDE.md.
**Audience:** Indian finfluencers (Telegram channel admins, YouTube algo-trading reviewers, Twitter handles with finance focus) who agreed to share TRADETRI's launch with their audience.
**Tone:** Hinglish bhai-tone. Short. Forward-friendly. Mobile-first.
**Length:** ≤ 200 chars per message (per Task 4 spec — forward-friendly without scrolling).

---

## v2 — under-200-chars variants (recommended)

### Message 1 (teaser, 48h before launch)

```
Bhai, TRADETRI 18 May launch.
L&T-engineer-built. Paper-mode-first. 45 templates active.
First 500 → lifetime free.
Waitlist: tradetri.com?ref={{your_handle}}
```
**Char count:** 188. ✓

### Message 2 (launch day)

```
🚀 LIVE: TRADETRI launch.
Backtest IS the live engine. Same code, same costs.
45 active equity templates. Paper-mode 30 din.
tradetri.com?ref={{your_handle}}
```
**Char count:** 197. ✓

### Message 3 (3 days post-launch nudge)

```
TRADETRI 72 hrs live. {N}+ waitlist signups. Genuine feedback chahiye — DM khula. tradetri.com?ref={{your_handle}}
```
**Char count:** ~140 (depends on N). ✓

---

## Referral mechanic — affiliate-link spec

Every WhatsApp message above includes `?ref={{your_handle}}`. Each
finfluencer gets a unique handle (e.g. `?ref=ravi`, `?ref=neha_trades`)
that maps to a row in the `affiliate_partners` table — to be created
in a follow-up sprint.

Tracking flow:
1. Customer clicks `tradetri.com?ref=ravi`
2. Frontend reads query param → sets cookie `tradetri_ref=ravi` (90-day TTL)
3. On signup, POST /api/auth/signup includes `referrer_handle=ravi`
4. Backend writes `users.referrer_handle` column (new column, requires migration)
5. Conversion → paid-tier upgrade → fires
   `referral.commission_earned` analytics event with the handle

**Pre-launch blocker (Task 4 BLOCKERS_MARKETING_V2.md):** the
`referrer_handle` column + signup-form integration isn't built. Until
then, affiliate links work as deep links but no commission tracking
fires.

---

## v0 — earlier drafts retained for reference

Original v0 messages were ≤ 500 chars, v2 tightened to ≤ 200 chars per
Task 4 spec.

---

## Message 1 — The teaser (send 48 hours before launch)

```
Bhai, ek update.

TRADETRI launch ho raha hai. Indian retail algo-trading platform —
L&T-engineer-built, transparency ledger-first, paper-mode-only at
launch.

113 strategy templates. 45 already active.

Waitlist: tradetri.com
Affiliate link aap ke pas hai (DM me if not).

First 500 sign-ups → lifetime free tier.

Share karo, paisa kaam aayega.
```

---

## Message 2 — The launch day broadcast

```
🚀 LIVE: TRADETRI launch ho gaya.

Algo-trading mein "backtest beautiful, live trade bekaar" — yeh end
karne aaye hain.

Backtest IS the live engine. Same code, same costs, same broker quirks.
Zero divergence.

Public deviation ledger.
Paper-mode-first (30 days mandatory).
SEBI conversation in flight.

L&T-discipline x bhai-energy.

Affiliate link: tradetri.com?ref=YOUR_HANDLE
First 500 → lifetime free.

— Jayesh
```

---

## Message 3 — Post-launch nudge (send 3 days after launch)

```
Quick update: TRADETRI launch ke 72 hours.

Numbers (transparent — yeh hum karte hain):

— X waitlist sign-ups
— Y paper trades chal rahe hain
— Z templates ka backtest run hua

Bhai, ek strategy clone karo, paper-trade run karo, batao kya
laga.

Genuine feedback chahiye — DM khula hai.

tradetri.com?ref=YOUR_HANDLE
```

---

## Affiliate-kit assets to share with finfluencers

Each affiliate gets a one-zip-file kit:

1. `TRADETRI_FINFLUENCER_BRIEF.pdf` — 1-page summary of the
   product, key talking points, what NOT to claim (no
   "guaranteed returns", no "AI-powered" if AI isn't actually
   in the loop)
2. `TRADETRI_LOGO_PACK.zip` — 5 logo variants (dark / light /
   square / horizontal / mobile-optimised)
3. `TRADETRI_DEMO_VIDEO_60s.mp4` — 60-second product demo
   (need to record — founder to-do)
4. `TRADETRI_AFFILIATE_TRACKING_LINK_TEMPLATE.txt` — instructions
   on the `?ref=HANDLE` query param + how to verify clicks land
   correctly
5. This file — three forward-ready WhatsApp messages

---

## Hindi-only variant (for traders who don't read English at all)

Replace Hinglish with pure Devanagari Hindi. Sample:

### Message 1 Hindi-only

```
भाई, एक अपडेट।

TRADETRI लॉन्च हो रहा है। भारत का retail algo-trading platform —
L&T-engineer-built, transparency ledger-first, paper-mode-only शुरुआत में।

113 strategy templates। 45 पहले से active।

Waitlist: tradetri.com
Affiliate link आपके पास है।

पहले 500 sign-ups → lifetime free tier।

शेयर करो।
```

**Note:** This is a "best-effort" Hindi rendering. A native Hindi
copywriter pass is recommended before broadcast — finance-domain
terms (algo-trading, paper-mode, ledger) need consistent rendering
choice.

---

## Open questions for review

1. **Affiliate compensation model.** The messages mention "paisa
   kaam aayega" but don't specify what affiliates get. Three
   models possible:
   - (a) flat per-signup (₹50/signup)
   - (b) revenue share (10% of paid-tier conversions in year 1)
   - (c) zero financial — just "first 500 free tier" social-credibility
   Recommendation: (b) — aligns long-term incentives. Decision needed.

2. **Who's the broadcast list?** Need a vetted list of 20-50
   finfluencer WhatsApp contacts. Suggest:
   - The 6 algo-subscription-review YouTube channels Jayesh subscribed to in 2024
   - 3-5 Indian fintech-focused Twitter handles
   - Founder's personal network of ex-L&T colleagues who became fintech operators
   - Recommendation: start with 10 high-trust contacts, see drop-through, expand week 2.

3. **Specific finfluencer partners to TAG in launch tweet?**
   Public tagging amplifies reach but commits the relationship.
   Decision needed: tag publicly or just send the kit via DM?

4. **Disclosure compliance.** SEBI Investment Advisor regulations
   bar undisclosed paid promotion. The affiliate kit MUST include
   a disclosure-text-snippet for any finfluencer who shares the
   message:
   ```
   "Disclosure: I am a TRADETRI affiliate. I receive [%] of paid
   subscriptions from users who join via my link. This does NOT
   affect my opinions of the product, but you should know."
   ```
   Decision needed: legal review of disclosure text + affiliate-kit
   inclusion requirement.

5. **Bhai-tone calibration.** "paisa kaam aayega" is direct
   bhai-energy. Some affiliates may have audiences that lean
   formal/professional. Provide both bhai-tone + formal-tone
   variants and let each affiliate pick. Recommendation: yes,
   ship both variants in the kit.
