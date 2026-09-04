/**
 * P&L attribution tags stamped on a strategy position by the reconciler under
 * the founder's exit rule (2026-09-04, cutover-26). Mirrors
 * backend/app/domains/pnl_reconciler/attribution.py.
 *
 *  - bot_only         priced; every exit fill was the bot's
 *  - account_flat     priced; a manual fill took the account flat
 *  - human_interfered NULL by rule — manual lots on the same contract made the
 *                     bot's exit a guess; the record says so instead of guessing
 *  - unpriceable      no traded bot entry in the broker's book (paper / phantom)
 *  - paper_sim        a paper trip priced from simulated fills; never counted
 *                     by a live ledger
 */
export type PnlAttribution =
  | "bot_only"
  | "account_flat"
  | "human_interfered"
  | "unpriceable"
  | "paper_sim";

/** Founder's wording for a NULL P&L the rule refuses to guess. */
export const HUMAN_INTERFERED_LABEL = "human-interfered — not attributable";

export const HUMAN_INTERFERED_FALLBACK_DETAIL =
  "Manual fills on the same contract made the bot's exit a guess; no P&L is recorded rather than a wrong one.";

/** An `unpriceable` row: no traded bot entry in the broker's book (paper / phantom / rejected). */
export const UNPRICEABLE_FALLBACK_DETAIL =
  "No traded bot entry exists in the broker's book for this row (paper test, phantom or rejected order) — it was never a trade.";
