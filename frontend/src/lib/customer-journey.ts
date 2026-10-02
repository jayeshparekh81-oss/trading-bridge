/**
 * The customer journey — pay → strategy → Long/Short/Both → even-lot quantity with
 * the capital line live → broker connect → daily one-tap → 09:07 readiness → trade.
 *
 * Founder (25 Sep 2026, Track C item 6): mobile first, the 4-question walk (wapas one
 * tap · what's next visible · works on a FRESH account · works on an EXISTING account
 * with real data), plain Hinglish, ONE next step per screen, three states, design
 * tokens, FSD.
 *
 * ONE SOURCE PER FACT: this file holds no fact of its own. It reads the surfaces the
 * screens already read (`/marketplace/subscriptions/me`, `/billing/me`, `/brokers`,
 * `/customer-lane/me/status`, `/customer-lane/dashboard/truth`,
 * `/customer-lane/vehicles/capital`) and turns them into ONE answer: which step is
 * next, and why. A surface that is not mounted (its backend flag OFF) or that failed
 * is NOT MEASURED — the step says so and never guesses a state.
 *
 * FLAG: `NEXT_PUBLIC_CUSTOMER_JOURNEY` — unset/"0" = OFF = the route renders the
 * honest "not switched on" line and nothing else.
 */

import { appCopy } from "@/lib/i18n/copy/app";
import { currentLang, fill, type Lang } from "@/lib/i18n/core";

export const JOURNEY_FLAG = "NEXT_PUBLIC_CUSTOMER_JOURNEY";

/** OFF unless the env var is exactly "1". Read at call time so tests can flip it. */
export function customerJourneyEnabled(): boolean {
  // Literal spelling on purpose: the only form Next's docs promise to inline.
  return process.env.NEXT_PUBLIC_CUSTOMER_JOURNEY === "1";
}

export const JOURNEY_STEPS = [
  "PAY",
  "STRATEGY",
  "DIRECTION",
  "QUANTITY",
  "BROKER",
  "DAILY_CONNECT",
  "READINESS",
  "TRADE",
] as const;
export type JourneyStep = (typeof JOURNEY_STEPS)[number];

/** Plain words, one line each: what the step IS and the ONE thing to do on it — in the customer's language. */
export function stepCopy(lang: Lang = currentLang()): Record<JourneyStep, { title: string; what: string; cta: string }> {
  const c = appCopy.pick(lang);
  return {
    PAY: { title: c.jr_pay_t, what: c.jr_pay_w, cta: c.jr_pay_c },
    STRATEGY: { title: c.jr_strategy_t, what: c.jr_strategy_w, cta: c.jr_strategy_c },
    DIRECTION: { title: c.jr_direction_t, what: c.jr_direction_w, cta: c.jr_direction_c },
    QUANTITY: { title: c.jr_quantity_t, what: c.jr_quantity_w, cta: c.jr_quantity_c },
    BROKER: { title: c.jr_broker_t, what: c.jr_broker_w, cta: c.jr_broker_c },
    DAILY_CONNECT: { title: c.jr_daily_t, what: c.jr_daily_w, cta: c.jr_daily_c },
    READINESS: { title: c.jr_ready_t, what: c.jr_ready_w, cta: c.jr_ready_c },
    TRADE: { title: c.jr_trade_t, what: c.jr_trade_w, cta: c.jr_trade_c },
  };
}
/** The Hinglish set by name (tests pin it). */
export const STEP_COPY = stepCopy("hinglish");

// ── the inputs (each may be NOT MEASURED: surface unmounted / failed) ─────

export type Measured<T> = { value: T; measured: true } | { value: null; measured: false; why: string };

export function measured<T>(v: T): Measured<T> {
  return { value: v, measured: true };
}
export function notMeasured<T>(why: string): Measured<T> {
  return { value: null, measured: false, why };
}

export interface JourneySubscription {
  id: string;
  status: string;
  execution_mode?: string | null;
  direction_filter?: string | null;
  lots?: number | null;
  is_paper?: boolean | null;
  listing_title?: string | null;
  open_position?: { symbol: string; quantity: number; side?: string | null } | null;
}

export interface JourneyInputs {
  /** `/billing/me` — plan_status / is_active. `charging` = the lane's charging switch (OFF today). */
  billing: Measured<{ plan_status: string; is_active: boolean }>;
  charging_enabled: boolean;
  subscriptions: Measured<JourneySubscription[]>;
  /** `/brokers` — any connected broker at all (the one-time setup). */
  brokers: Measured<{ name: string; status: string }[]>;
  /** `/customer-lane/me/status` — TODAY's connect (the daily one-tap). */
  lane: Measured<{ connected: boolean; reason: string; eligibility: string; message: string }>;
  /** `/customer-lane/dashboard/truth` — the broker-verified stop. */
  truth: Measured<{ verdict: string; line: string; next_step_hi: string }>;
}

export interface StepState {
  step: JourneyStep;
  /** DONE = the customer has this; NEXT = the one thing to do now; LATER = after NEXT; UNKNOWN = NOT MEASURED */
  state: "DONE" | "NEXT" | "LATER" | "UNKNOWN";
  /** the plain line for the card — a measured fact or the NOT MEASURED reason */
  line: string;
  /** where the ONE tap goes */
  href: string;
}

export interface JourneyResolution {
  next: JourneyStep;
  steps: StepState[];
  /** the whole thing in one line, for the top of the screen */
  headline: string;
}

const NOT = "NOT MEASURED";

function activeSub(subs: JourneySubscription[]): JourneySubscription | null {
  return subs.find((s) => s.status === "active" && !s.is_paper) ?? subs.find((s) => s.status === "active") ?? null;
}

/**
 * The ONE decision: which step is next. Pure. Never guesses: a NOT MEASURED input
 * marks its step UNKNOWN and, if it is the first undecided step, becomes NEXT with
 * the reason — the customer sees what could not be checked, not a green tick.
 */
export function resolveJourney(i: JourneyInputs, lang: Lang = currentLang()): JourneyResolution {
  const c = appCopy.pick(lang);
  const SC = stepCopy(lang);
  const s: StepState[] = [];
  let decided = true; // becomes false at the first NEXT/UNKNOWN; later steps are LATER

  const push = (step: JourneyStep, done: boolean | null, line: string, href: string) => {
    let state: StepState["state"];
    if (!decided) state = "LATER";
    else if (done === null) { state = "UNKNOWN"; decided = false; }
    else if (done) state = "DONE";
    else { state = "NEXT"; decided = false; }
    s.push({ step, state, line, href });
  };

  // 1 PAY — while charging is OFF nothing is owed: DONE with the honest line.
  if (!i.charging_enabled) {
    push("PAY", true, c.jr_pay_off, "/pricing");
  } else if (!i.billing.measured) {
    push("PAY", null, `${NOT}: ${i.billing.why}`, "/pricing");
  } else {
    const ok = i.billing.value.is_active;
    push("PAY", ok, ok ? fill(c.jr_pay_active, { status: i.billing.value.plan_status }) : fill(c.jr_pay_inactive, { status: i.billing.value.plan_status }), "/pricing");
  }

  // 2 STRATEGY
  const sub = i.subscriptions.measured ? activeSub(i.subscriptions.value) : null;
  if (!i.subscriptions.measured) push("STRATEGY", null, `${NOT}: ${i.subscriptions.why}`, "/marketplace");
  else push("STRATEGY", !!sub, sub ? fill(c.jr_strategy_line, { title: sub.listing_title ?? c.jr_strategy_chosen }) : c.jr_strategy_none, "/marketplace");

  // 3 DIRECTION — a stored direction_filter on the active subscription
  if (!sub) push("DIRECTION", i.subscriptions.measured ? false : null, c.jr_after_strategy, "/marketplace/me");
  else {
    const d = (sub.direction_filter ?? "").toLowerCase();
    const ok = ["long", "short", "both"].includes(d);
    push("DIRECTION", ok, ok ? fill(c.jr_direction_line, { d: d.toUpperCase() }) : c.jr_direction_unset, `/marketplace/me?highlight=${sub.id}`);
  }

  // 4 QUANTITY — even lots, >= 2
  if (!sub) push("QUANTITY", i.subscriptions.measured ? false : null, c.jr_after_strategy, "/marketplace/me");
  else {
    const lots = sub.lots ?? null;
    const ok = lots != null && lots >= 2 && lots % 2 === 0;
    push("QUANTITY", ok, ok ? fill(c.jr_qty_ok, { lots: String(lots) }) : lots == null ? c.jr_qty_unset : fill(c.jr_qty_odd, { lots: String(lots) }),
      `/marketplace/me?highlight=${sub.id}`);
  }

  // 5 BROKER — one-time setup
  if (!i.brokers.measured) push("BROKER", null, `${NOT}: ${i.brokers.why}`, "/brokers");
  else {
    const b = i.brokers.value.find((x) => x.status === "connected" || x.status === "expired");
    push("BROKER", !!b, b ? fill(c.jr_broker_line, { name: b.name, state: b.status === "expired" ? c.jr_broker_expired : c.jr_broker_ok }) : c.jr_broker_none, "/brokers");
  }

  // 6 DAILY CONNECT — today's tap
  if (!i.lane.measured) push("DAILY_CONNECT", null, `${NOT}: ${i.lane.why}`, "/brokers");
  else push("DAILY_CONNECT", i.lane.value.connected, i.lane.value.connected ? fill(c.jr_daily_ok, { eligibility: i.lane.value.eligibility }) : i.lane.value.message || fill(c.jr_daily_no, { reason: i.lane.value.reason }), "/brokers");

  // 7 READINESS — the broker-verified stop (A3 surfaced) + lane eligibility
  if (!i.truth.measured) push("READINESS", null, `${NOT}: ${i.truth.why}`, "/marketplace/me");
  else {
    const v = i.truth.value.verdict;
    const ok = v === "PROTECTED" || v === "FLAT";
    push("READINESS", ok, i.truth.value.line, "/marketplace/me");
  }

  // 8 TRADE
  push("TRADE", false, sub?.open_position ? fill(c.jr_trade_open, { side: sub.open_position.side ?? "", qty: sub.open_position.quantity, symbol: sub.open_position.symbol }) : c.jr_trade_wait, "/marketplace/me");

  const next = (s.find((x) => x.state === "NEXT" || x.state === "UNKNOWN") ?? s[s.length - 1]).step;
  const nextState = s.find((x) => x.step === next)!;
  const headline = nextState.state === "UNKNOWN"
    ? fill(c.jr_headline, { title: SC[next].title, what: nextState.line })
    : fill(c.jr_headline, { title: SC[next].title, what: SC[next].what });
  return { next, steps: s, headline };
}

/** Where a customer lands when they open the journey with no state at all. */
export const FRESH_ACCOUNT_INPUTS: JourneyInputs = {
  billing: notMeasured("plan surface not read"),
  charging_enabled: false,
  subscriptions: measured([]),
  brokers: measured([]),
  lane: notMeasured("customer-lane status surface not mounted"),
  truth: notMeasured("truth card surface not mounted"),
};
