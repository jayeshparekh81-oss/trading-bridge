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
 *  - operator_estimate  priced, but by a HUMAN, not from a broker fill — the
 *                     engine derived an exit that was never dispatched, so the
 *                     exit price is its level, disclosed on the row
 */
export type PnlAttribution =
  | "bot_only"
  | "account_flat"
  | "human_interfered"
  | "unpriceable"
  | "paper_sim"
  | "operator_estimate";

/** Founder's wording for a NULL P&L the rule refuses to guess. */
export const HUMAN_INTERFERED_LABEL = "human-interfered — not attributable";

export const HUMAN_INTERFERED_FALLBACK_DETAIL =
  "Manual fills on the same contract made the bot's exit a guess; no P&L is recorded rather than a wrong one.";

/** An `unpriceable` row: no traded bot entry in the broker's book (paper / phantom / rejected). */
export const UNPRICEABLE_FALLBACK_DETAIL =
  "No traded bot entry exists in the broker's book for this row (paper test, phantom or rejected order) — it was never a trade.";

/**
 * An `operator_estimate` row: the number IS there and IS counted, but part of
 * it was never a broker fill. This label rides alongside the money, because
 * the generic "fills are real, charges are our estimate" tooltip is false here
 * — on this row the FILL is the estimate.
 */
export const OPERATOR_ESTIMATE_LABEL = "estimate — not a broker fill";

export const OPERATOR_ESTIMATE_FALLBACK_DETAIL =
  "Part of this P&L was priced by an operator, not from a broker fill: the engine derived an exit that was never sent, so its level was recorded instead. No order was placed for it and no brokerage was charged on it.";
