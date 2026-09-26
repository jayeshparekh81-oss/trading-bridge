/**
 * The per-account TRUTH card (master C6) — types, the OFF flag, and the pure
 * helpers the card renders with.
 *
 * Founder (25 Sep 2026 master, C6): "the dashboard shows per account the open
 * position, whether a resting stop EXISTS AT THE BROKER right now (from the
 * broker, not our own claim), and when it was last verified."
 *
 * ONE SOURCE PER FACT: nothing here decides anything. The verdict, the
 * position, the stop and the verified time all come from the backend's
 * flag-gated surface `/customer-lane/dashboard/truth`, which itself only reads
 * the broker-side A3 receipt. NOT MEASURED is a first-class verdict — it is
 * shown, never hidden behind a spinner or a green tick.
 *
 * FLAG: `NEXT_PUBLIC_CUSTOMER_DASHBOARD` — unset/"0" = OFF = nothing renders.
 */

export const DASHBOARD_FLAG = "NEXT_PUBLIC_CUSTOMER_DASHBOARD";

/** OFF unless the env var is exactly "1". Read at call time so tests can flip it. */
export function customerDashboardEnabled(): boolean {
  // Literal spelling on purpose: the only form Next's docs promise to inline.
  return process.env.NEXT_PUBLIC_CUSTOMER_DASHBOARD === "1";
}

export const TRUTH_VERDICTS = ["PROTECTED", "UNPROTECTED", "FLAT", "NOT MEASURED"] as const;
export type TruthVerdict = (typeof TRUTH_VERDICTS)[number];

// ── API shapes (mirror backend/app/api/customer_dashboard.py) ─────────────

export interface TruthPosition {
  symbol?: string | null;
  security_id?: string | null;
  side?: string | null;
  quantity?: number | null;
}

export interface TruthStop {
  exists?: boolean | null;
  order_id?: string | null;
  side?: string | null;
  quantity?: number | null;
  trigger_price?: number | null;
  security_id?: string | null;
}

export interface TruthCard {
  account_key: string;
  verdict: TruthVerdict;
  position: TruthPosition | null;
  stop: TruthStop | null;
  verified_at: string | null;
  age_s: number | null;
  source: string;
  reason: string;
  /** the backend's own plain-Hinglish one-liner */
  line: string;
  next_step_hi: string;
}

export interface ManualExitResponse {
  subscription_id: string;
  flipped: boolean;
  previous_mode: string;
  new_mode: string;
  message_hi: string;
  audit_log_id: string | null;
}

// ── pure helpers ──────────────────────────────────────────────────────────

export type TruthTone = "ok" | "danger" | "muted" | "unknown";

/** Colour intent per verdict. UNPROTECTED is the only danger; NOT MEASURED is
 *  never green and never red — it is "we do not know", rendered as such. */
export function truthTone(v: TruthVerdict): TruthTone {
  switch (v) {
    case "PROTECTED":
      return "ok";
    case "UNPROTECTED":
      return "danger";
    case "FLAT":
      return "muted";
    default:
      return "unknown";
  }
}

/** The headline word a customer reads first. Plain Hinglish. */
export function truthHeadline(v: TruthVerdict): string {
  switch (v) {
    case "PROTECTED":
      return "Stop broker par hai";
    case "UNPROTECTED":
      return "Stop NAHI mila — dhyan do";
    case "FLAT":
      return "Koi position khuli nahi";
    default:
      return "Pata nahi (NOT MEASURED)";
  }
}

/** "Xs pehle" / "Xm pehle" from the age the backend measured; NOT MEASURED when absent. */
export function verifiedAgo(age_s: number | null | undefined): string {
  if (typeof age_s !== "number" || age_s < 0) return "NOT MEASURED";
  if (age_s < 90) return `${age_s}s pehle`;
  return `${Math.round(age_s / 60)} min pehle`;
}

/** The one-tap is offered only when there is something to declare an exit on. */
export function oneTapAvailable(card: TruthCard | null): boolean {
  return !!card && card.verdict !== "FLAT" && !!card.position;
}
