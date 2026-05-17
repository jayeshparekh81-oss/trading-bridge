# BLOCKERS — Marketing Kit v2

**Branch:** `docs/marketing-kit-v2`
**Date:** 2026-05-17 → 2026-05-18
**Builds on:** `docs/marketing/BLOCKERS_MARKETING.md` (v0 questions)

---

## Open product-positioning questions

### Q1. Public P&L disclosure — yes / no / limited?

LinkedIn post v2 hardcodes "₹2.3 lakh lost across 6 algo subscriptions
in 2024." Concrete numbers are persuasive but commit founder publicly.

Three positions:

- **(A) Full disclosure** — keep the ₹2.3 lakh figure + the
  6-subscription count. Maximum credibility, also most public surface
  for legal counter-action by named-or-implied competitors.
- **(B) Range** — "₹1-3 lakh across multiple subscriptions." Less
  specific, less attackable.
- **(C) Anonymized** — "Six figures across multiple subscriptions"
  (technically 6 figures includes ₹100,000 → ₹999,999 in INR).

Recommendation: **(A)** for LinkedIn (B2B / regulator audience values
specificity); **(C)** for Twitter (broad audience, less legal exposure).

Decision needed.

### Q2. Affiliate commission % + structure

WhatsApp v2 introduces `?ref={{handle}}` tracking links. The
`referrer_handle` column + commission engine isn't built yet. Three
models:

- **(A) Flat per-signup** — ₹50-100 per signup that converts to paid
  tier
- **(B) Revenue share** — 10-15% of year-1 paid subscriptions
- **(C) Combined** — ₹50 flat per signup + 10% rev share for first year

Recommendation: **(B)** — aligns long-term incentives. Founder picks
the % (10 or 15).

Decision needed: % + duration + clawback policy (subs cancelled within
30 days → no commission).

### Q3. Specific finfluencers to tag publicly in launch tweet

The v2 Twitter thread does NOT name any finfluencer. Public tagging
amplifies reach but commits the relationship. Two strategies:

- **(A)** No public tags in launch tweet. Privately invite 10-20
  high-trust finfluencers via the affiliate kit. They post
  independently with their ref link.
- **(B)** Tag 3-5 high-trust names in a follow-up tweet 12 hours
  after the launch thread (after founder's own audience has had
  first crack).

Recommendation: **(A)** for v1 launch; **(B)** at 30-day milestone if
affiliate program has clear early winners.

Founder needs to identify the 3-5 names if going with (B).

### Q4. SEBI conversation framing — assertive vs hedged

LinkedIn v2 reduced hedging language. The new wording:

> "SEBI Investment Advisor application filed Q1 2026."

is factual + specific. Risk: if SEBI rejects or delays, the public
post becomes inaccurate. Mitigation: post links to
`tradetri.com/compliance` which can be updated as status evolves —
the LinkedIn post itself doesn't need editing.

Decision needed: confirm Q1 2026 is the correct filing date.

### Q5. Twitter Variant C — Gujarati audience real?

Twitter v2 ships a Gujarati-localised tweet 1 variant. The reasoning:
high Mumbai/Gujarat retail trader concentration. But:

- The founder's existing Twitter audience is Hinglish-primary
- A Gujarati tweet might confuse non-Gujarati followers
- The Gujarati phrasing has not been native-speaker reviewed

Recommendation: **defer Variant C** to v2.1 after we have:
1. A native Gujarati copy reviewer
2. Engagement metrics on Variant A (the Hinglish primary) showing
   Mumbai/Gujarat under-indexing

Decision needed: ship Variant C as scheduled second-post, or hold?

### Q6. Founder-reply commitment scope

v2 Waitlist email + Onboarding tour both promise "pehle 500 sign-ups
ko personal reply." This commits ~500 reply-cycles in the founder's
inbox over the first 1-2 weeks.

Realistic ratio: ~30% of waitlist signups reply to the welcome email
(industry average). So 500 sign-ups → ~150 personal replies. That's
~10 replies/day for 2 weeks. Manageable.

Beyond 500 — the commitment lapses. Replies become "Hi, thanks for
signing up — we read every email but can't reply individually past
the first 500 cohort."

Decision needed: confirm 500-cap is right; or extend to 1000?

### Q7. Disclosure compliance text on every piece

Every customer-facing piece needs SEBI compliance footer. Current
state per piece:

| Piece | Disclosure text |
|---|---|
| Twitter | No room (280 chars); link to tradetri.com/compliance in bio |
| LinkedIn v2 | In-line in body (SEBI section) |
| WhatsApp v2 | Truncated for char-budget; relies on landing-page footer |
| Waitlist email v2 | Footer block before unsubscribe |
| Onboarding tour v2 | Step 8 dedicated |

Decision needed: legal review of the disclosure text variants. Do
SEBI / IT Rules require a SPECIFIC string? Or is "SEBI IA registration
filed Q1 2026" + landing-page link sufficient?

### Q8. Email service provider choice

Waitlist email v2 references "SES / SendGrid / Postmark — TBD". The
provider determines:
- Merge-var substitution syntax (`{{first_name}}` vs `{first_name}}`
- Unsubscribe-link format
- Throughput limits (500 emails to first 500 sign-ups = small)

Recommendation: **AWS SES** (already in stack for transactional
emails per `app.core.email`). One vendor, one quota, lower friction.

Decision needed: confirm SES, or evaluate SendGrid for marketing
features (A/B subject lines, send-time optimization)?

### Q9. Logo + demo video assets

Both WhatsApp and Twitter kits reference shippable assets:
- `TRADETRI_LOGO_PACK.zip` — 5 logo variants
- `TRADETRI_DEMO_VIDEO_60s.mp4` — 60-second product demo

Neither exists yet. The founder needs to commission these (designer
+ video editor) before launch broadcast.

Decision needed: timeline for asset creation; pick designer/editor.

---

## v2 deliverable list

```
docs/marketing/
    FOUNDER_VOICE_GUIDE.md                 NEW (canonical voice doc)
    TWITTER_LAUNCH_THREAD.md               REFINED (3 voice variants; 11 tweets)
    LINKEDIN_POST.md                       REFINED (real SEBI dates; concrete P&L)
    WHATSAPP_BROADCAST.md                  REFINED (≤200 chars; ?ref={{handle}})
    WAITLIST_EMAIL_INVITE.md               REFINED (personalize-able template + footer)
    ONBOARDING_TOUR_COPY_V2.md             REFINED (matches current UI; 9 steps)
    BLOCKERS_MARKETING_V2.md               NEW (this file)
```

NOT touched: any source code, any product feature, any backend module.

## Hard constraints honoured

- ✅ Hinglish bhai-tone in Hindi-primary pieces; English plain in
  professional pieces
- ✅ "L&T-engineer-built" anchor in 4 of 5 pieces (Twitter, LinkedIn,
  WhatsApp, Email; onboarding tour skips because users are already in-product)
- ✅ "Backtest nahi, Proof" / "Backtest is not Proof" in all 5 pieces
- ✅ SEBI compliance angle explicit on LinkedIn + footer of waitlist email
- ✅ ZERO claims about Phase 6 AI advisor (not yet built)
- ✅ All Phase 5 / Phase 7-8 / Phase 9 references include target dates,
  not "soon"
- ✅ Concrete numbers throughout (45 active templates, 230 indicators,
  113 total, ₹2.3 lakh, Q1/Q3/2027+ dates)

## What needs to happen post-review

1. Founder answers Q1-Q9 above
2. (If Q2 approved) Backend sprint to ship `referrer_handle` column +
   signup-form integration before launch broadcast
3. (If Q4 confirmed) Add `tradetri.com/compliance` page (currently
   referenced but not built)
4. (If Q5 confirmed) Native Gujarati copy review or hold Variant C
5. (If Q8 confirmed) Wire SES merge vars + unsubscribe-link generator
6. (If Q9) Commission logo + demo video assets
