/**
 * The ONE place that turns the kill switch's backend state into words.
 *
 * ⚠️ READ BEFORE CHANGING ANY STRING HERE.
 *
 * The backend publishes exactly two members — ACTIVE and TRIPPED
 * (app/schemas/kill_switch.py) — plus a separate `enabled` flag. Three screens
 * read that same field and, until this module existed, each one invented its
 * own word at the render site: /kill-switch printed "NORMAL", the /strategies
 * summary printed "Active.", the Overview printed "Chalu hai". "NORMAL" was
 * never a backend word at all — it was a literal living inside one JSX
 * ternary. Nothing could notice the drift because nothing owned it. Now every
 * surface asks here, so two screens can never describe one switch with two
 * different words.
 *
 * THREE states, not two. `enabled` is not decoration: a switch that is ACTIVE
 * on the wire but has no limits configured protects nothing. Folding that into
 * "Chalu hai" tells a customer a safety net is watching their money when none
 * is — so "no limits set" gets its own state, and a visibly non-green tone.
 *
 * NEVER name a state that has not been read. A null status returns null, not a
 * cheerful default: "we could not load it" and "it is fine" are different
 * facts, and only one of them is safe to print.
 *
 * The words are Hinglish because the product is. Note that "Chalu hai" here
 * means the SWITCH is armed — it is never used on a kill-switch surface for
 * anything else. (The /strategies page already spends the English word
 * "Active" on `strategy.is_active`; one word for two facts on one screen is
 * the defect this module exists to end.)
 */

/** Mirrors the wire shape. "TRIPPED"/"ACTIVE" survive ONLY as wire values. */
export interface KillSwitchWireState {
  state: "ACTIVE" | "TRIPPED";
  enabled: boolean;
}

export type KillSwitchKind = "tripped" | "armed" | "off";
export type KillSwitchTone = "loss" | "profit" | "warn";

export interface KillSwitchLabel {
  kind: KillSwitchKind;
  /** The word every surface prints for this state. */
  word: string;
  tone: KillSwitchTone;
}

/** Tone → Tailwind colour, so three screens cannot colour one state three ways. */
export const KILL_SWITCH_TONE_CLASS: Record<KillSwitchTone, string> = {
  loss: "text-loss",
  profit: "text-profit",
  warn: "text-amber-400",
};

export function killSwitchLabel(
  s: KillSwitchWireState | null | undefined,
): KillSwitchLabel | null {
  if (!s) return null; // never name a state you have not read
  if (s.state === "TRIPPED") return { kind: "tripped", word: "Sab band hai", tone: "loss" };
  if (!s.enabled) return { kind: "off", word: "Limit set nahi", tone: "warn" };
  return { kind: "armed", word: "Chalu hai", tone: "profit" };
}
