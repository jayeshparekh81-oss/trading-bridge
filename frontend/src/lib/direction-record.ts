/**
 * What performance record may be shown beside a DIRECTION choice.
 *
 * ⚠️ READ THIS BEFORE ATTACHING ANY NUMBER TO A DIRECTION TOGGLE.
 *
 * The showcase artifact does publish long-only and short-only figures, and they
 * are tempting: long shows 805 trades, 81.7% win, PF 5.68 — better on every
 * headline than the both-sides 1,149 / 76.8% / 5.01. They are NOT the record of
 * a long-only strategy, and the artifact says so itself:
 *
 *   "Long-only / short-only figures are a SLICE of the full long+short system,
 *    shown for transparency — NOT an independently-validated standalone
 *    strategy. The system was designed and tested as a whole; trading only one
 *    side is not a tested configuration."
 *
 * The mechanism behind that caveat is concrete, not legal boilerplate. Those
 * long trades were taken INSIDE a system that was also trading shorts. While a
 * short was open the engine could not enter a long, and every exit starts a
 * cooldown. A genuinely long-only engine would therefore have taken a
 * DIFFERENT SET OF TRADES — it would have been free during windows the
 * both-sides system was occupied. Slicing the results of one system is not the
 * same as running a different one.
 *
 * So: a customer who picks "long only" is choosing an UNTESTED configuration.
 * We may sell them that choice — it is their money and their call — but we may
 * not hand them a record that was not produced by it. Showing the slice next to
 * the toggle would be precisely the false-claim shape we removed from the
 * marketing copy: a real number, honestly computed, describing something other
 * than what the customer is buying.
 *
 * Producing a TRUE long-only record is possible — the engine has a `use_short`
 * flag — but that is a new backtest requiring its own validation, not something
 * derivable from the published run. Until that exists, the rule is: show none,
 * and say the record is both-sides.
 */

export type Direction = "all" | "long" | "short";

export interface DirectionRecordPolicy {
  /** May we display the published performance figures for this choice? */
  showNumbers: boolean;
  /** What the customer is told instead (or alongside). */
  note: string;
}

export const BOTH_SIDES_NOTE =
  "Yeh record poore long+short system ka hai — jaisa woh design aur test hua.";

export const SINGLE_SIDE_NOTE =
  "Sirf ek side chunne pe koi verified record nahi dikhaya jaata. Humare " +
  "published numbers poore long+short system ke hain; us system ne shorts bhi " +
  "liye the, aur unke chalte kaunse longs mile ye bhi badalta hai. Sirf-long " +
  "ya sirf-short alag se test NAHI hua hai — isliye uska koi apna record nahi hai.";

/**
 * The whole policy, in one function. `all` is the tested configuration and may
 * carry the published record; anything narrower may not.
 */
export function directionRecordPolicy(direction: Direction): DirectionRecordPolicy {
  if (direction === "all") {
    return { showNumbers: true, note: BOTH_SIDES_NOTE };
  }
  return { showNumbers: false, note: SINGLE_SIDE_NOTE };
}

/** Convenience for guarding a render site. */
export function mayShowRecordFor(direction: Direction): boolean {
  return directionRecordPolicy(direction).showNumbers;
}
