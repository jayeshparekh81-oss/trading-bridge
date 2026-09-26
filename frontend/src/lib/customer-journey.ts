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

export const JOURNEY_FLAG = "NEXT_PUBLIC_CUSTOMER_JOURNEY";

/** OFF unless the env var is exactly "1". Read at call time so tests can flip it. */
export function customerJourneyEnabled(): boolean {
  return process.env[JOURNEY_FLAG] === "1";
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

/** Plain Hinglish, one line each: what the step IS and the ONE thing to do on it. */
export const STEP_COPY: Record<JourneyStep, { title: string; what: string; cta: string }> = {
  PAY: { title: "1 · Plan", what: "Pehle plan. Abhi paisa nahi kat raha (charging band hai) — aage badho.", cta: "Aage badho" },
  STRATEGY: { title: "2 · Strategy", what: "Ek strategy chuno jo aapke liye trade karegi.", cta: "Strategy chuno" },
  DIRECTION: { title: "3 · Direction", what: "Long, Short ya dono — strategy ke kaunse signal aapke account me chalenge.", cta: "Direction set karo" },
  QUANTITY: { title: "4 · Quantity", what: "Kitna bada sauda (lot) — hamesha jodi me: 2, 4, 6… kyunki strategy aadha hissa pehle bechti hai. Neeche \"kitna paisa chahiye\" dikhta hai.", cta: "Size set karo" },
  BROKER: { title: "5 · Broker", what: "Apna Dhan account jodo. Jodna ek baar hai; uske baad roz sirf Dhan ki nayi chabi (token) daalni hoti hai.", cta: "Broker jodo" },
  DAILY_CONNECT: { title: "6 · Aaj ka connect", what: "Har trading din ek tap: 09:15 se pehle connect. Yahi ek kaam roz ka hai.", cta: "Aaj connect karo" },
  READINESS: { title: "7 · 09:07 readiness", what: "Market se pehle sab check: connect, stop broker par, capacity. Kuch laal ho to yahi batayega kya karna hai.", cta: "Check dekho" },
  TRADE: { title: "8 · Trade", what: "Sab tayyar. Ab strategy chalegi; position aur stop yahin dikhega.", cta: "Dashboard" },
};

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
export function resolveJourney(i: JourneyInputs): JourneyResolution {
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
    push("PAY", true, "Abhi koi paisa nahi kat raha (charging switch band). Plan ka page dekh sakte ho.", "/pricing");
  } else if (!i.billing.measured) {
    push("PAY", null, `${NOT}: ${i.billing.why}`, "/pricing");
  } else {
    const ok = i.billing.value.is_active;
    push("PAY", ok, ok ? `Plan active (${i.billing.value.plan_status}).` : `Plan ${i.billing.value.plan_status} — pehle plan lo.`, "/pricing");
  }

  // 2 STRATEGY
  const sub = i.subscriptions.measured ? activeSub(i.subscriptions.value) : null;
  if (!i.subscriptions.measured) push("STRATEGY", null, `${NOT}: ${i.subscriptions.why}`, "/marketplace");
  else push("STRATEGY", !!sub, sub ? `Strategy: ${sub.listing_title ?? "chuni hui"}.` : "Koi strategy nahi chuni.", "/marketplace");

  // 3 DIRECTION — a stored direction_filter on the active subscription
  if (!sub) push("DIRECTION", i.subscriptions.measured ? false : null, "Strategy ke baad.", "/marketplace/me");
  else {
    const d = (sub.direction_filter ?? "").toLowerCase();
    const ok = ["long", "short", "both"].includes(d);
    push("DIRECTION", ok, ok ? `Direction: ${d.toUpperCase()}.` : "Direction set nahi hai.", `/marketplace/me?highlight=${sub.id}`);
  }

  // 4 QUANTITY — even lots, >= 2
  if (!sub) push("QUANTITY", i.subscriptions.measured ? false : null, "Strategy ke baad.", "/marketplace/me");
  else {
    const lots = sub.lots ?? null;
    const ok = lots != null && lots >= 2 && lots % 2 === 0;
    push("QUANTITY", ok, ok ? `${lots} lot (packet), jodi me — theek.` : lots == null ? "Size abhi set nahi hai." : `${lots} lot (packet) — jodi me chahiye (2, 4, 6…).`,
      `/marketplace/me?highlight=${sub.id}`);
  }

  // 5 BROKER — one-time setup
  if (!i.brokers.measured) push("BROKER", null, `${NOT}: ${i.brokers.why}`, "/brokers");
  else {
    const b = i.brokers.value.find((x) => x.status === "connected" || x.status === "expired");
    push("BROKER", !!b, b ? `${b.name} joda hua (${b.status === "expired" ? "chabi (token) purani — nayi chabi daalo" : "juda hai"}).` : "Koi broker nahi joda.", "/brokers");
  }

  // 6 DAILY CONNECT — today's tap
  if (!i.lane.measured) push("DAILY_CONNECT", null, `${NOT}: ${i.lane.why}`, "/brokers");
  else push("DAILY_CONNECT", i.lane.value.connected, i.lane.value.connected ? `Aaj connected (${i.lane.value.eligibility}).` : i.lane.value.message || `Aaj connect nahi: ${i.lane.value.reason}.`, "/brokers");

  // 7 READINESS — the broker-verified stop (A3 surfaced) + lane eligibility
  if (!i.truth.measured) push("READINESS", null, `${NOT}: ${i.truth.why}`, "/marketplace/me");
  else {
    const v = i.truth.value.verdict;
    const ok = v === "PROTECTED" || v === "FLAT";
    push("READINESS", ok, i.truth.value.line, "/marketplace/me");
  }

  // 8 TRADE
  push("TRADE", false, sub?.open_position ? `Position khuli: ${sub.open_position.side ?? ""} ${sub.open_position.quantity} ${sub.open_position.symbol}.` : "Signal aane par position yahin dikhegi.", "/marketplace/me");

  const next = (s.find((x) => x.state === "NEXT" || x.state === "UNKNOWN") ?? s[s.length - 1]).step;
  const nextState = s.find((x) => x.step === next)!;
  const headline = nextState.state === "UNKNOWN"
    ? `Agla kadam: ${STEP_COPY[next].title} — ${nextState.line}`
    : `Agla kadam: ${STEP_COPY[next].title} — ${STEP_COPY[next].what}`;
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
