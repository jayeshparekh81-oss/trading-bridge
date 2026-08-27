/**
 * How an execution row is LABELLED — simulated, real, or neither.
 *
 * ⚠️ READ BEFORE CHANGING ANY STRING HERE.
 *
 * Every subscriber execution written today is a simulated fill: the confirm
 * path's only fill primitive is `_simulate_fill`, and both fan-out writers are
 * paper. So this screen is, right now, entirely simulated — and it must SAY so,
 * because an execution log that lists symbols, quantities, prices and order ids
 * looks exactly like a broker fill history. A customer who reads it as one
 * believes real money moved.
 *
 * But the label is NOT hardcoded to "simulated". It is derived from each row's
 * own `paper_mode`, which the API derives from the stored `broker_response`.
 * Hardcoding it would mean the day a real fill first appears, this screen
 * confidently mislabels it — the reassurance would have rotted into a lie that
 * no test could catch. Tests in tests/marketplace/execution-log.test.tsx assert
 * a `paper_mode: false` row renders DIFFERENTLY, precisely so it cannot.
 *
 * THREE states, not two. `paper_mode` is tri-state: the API returns `null` when
 * the row carries no usable flag. That is deliberately NOT collapsed:
 *   - unknown → "real" would present a simulated fill as a broker fill, the
 *     one failure this screen exists to prevent;
 *   - unknown → "simulated" would hand out the reassurance without evidence.
 * So unknown gets its own visibly non-claiming state. Absence of evidence is
 * never evidence of absence — the same rule the fan-out's POSITION_UNKNOWN
 * sentinel follows.
 */

/** Mirrors the API's tri-state `paper_mode` (absent ⇒ unknown). */
export type PaperMode = boolean | null | undefined;

export type ExecutionLabelKind = "simulated" | "real" | "unverified";

export interface ExecutionLabel {
  kind: ExecutionLabelKind;
  /** Short chip text. */
  text: string;
  /** Plain-language meaning, shown as a title/aria description. */
  meaning: string;
  /** Tailwind tone. Simulated and real must never look alike. */
  tone: string;
}

export const EXECUTION_LABELS: Record<ExecutionLabelKind, ExecutionLabel> = {
  simulated: {
    kind: "simulated",
    text: "SIMULATED",
    meaning:
      "Yeh ek simulated fill hai — broker ko koi order nahi gaya, aur koi real paisa move nahi hua.",
    tone: "bg-amber-400/12 text-amber-300 border-amber-300/30",
  },
  real: {
    kind: "real",
    text: "REAL",
    meaning: "Yeh ek real broker fill hai — actual paisa move hua hai.",
    tone: "bg-loss/12 text-loss border-loss/30",
  },
  unverified: {
    kind: "unverified",
    text: "UNVERIFIED",
    meaning:
      "Is row pe simulated/real ka flag record nahi hua. Isliye hum dono mein se kuch claim nahi kar rahe — ise broker fill maan ke mat chalo.",
    tone: "bg-white/[0.06] text-muted-foreground border-white/[0.12]",
  },
};

/** Per-row label, derived. Never a constant. */
export function executionLabel(paperMode: PaperMode): ExecutionLabel {
  if (paperMode === true) return EXECUTION_LABELS.simulated;
  if (paperMode === false) return EXECUTION_LABELS.real;
  return EXECUTION_LABELS.unverified;
}

/**
 * The header sentence for the whole log — also derived, for the same reason
 * the row chips are. "All simulated" is only said when every row actually says
 * so; one real or one unverified row downgrades it to a mixed statement.
 */
export function executionLogSummary(
  rows: readonly { paper_mode?: PaperMode }[],
): string {
  if (rows.length === 0) return EMPTY_LOG_NOTE;
  const kinds = new Set(rows.map((r) => executionLabel(r.paper_mode).kind));
  if (kinds.size === 1 && kinds.has("simulated")) return ALL_SIMULATED_NOTE;
  if (kinds.has("real")) return CONTAINS_REAL_NOTE;
  return MIXED_UNVERIFIED_NOTE;
}

export const ALL_SIMULATED_NOTE =
  "Yeh saari entries SIMULATED hain — broker ko koi order nahi gaya aur koi " +
  "real paisa move nahi hua. Yeh broker ka fill history NAHI hai.";

export const CONTAINS_REAL_NOTE =
  "Is log mein REAL broker fills bhi hain. Har row apna label khud carry " +
  "karti hai — row-wise dekho, poore log ko ek jaisa mat maano.";

export const MIXED_UNVERIFIED_NOTE =
  "Kuch rows pe simulated/real ka flag record nahi hua. Un rows ko broker " +
  "fill maan ke mat chalo — unka label UNVERIFIED hai.";

/**
 * Shown when the READ ITSELF failed. Deliberately distinct from
 * EMPTY_LOG_NOTE: an empty list returned by a failed fetch is not evidence
 * that there are no executions, and telling a customer "you have none" when
 * we simply could not find out is a false statement about their money.
 */
export const FETCH_FAILED_NOTE =
  "Execution log load nahi ho paaya. Iska matlab yeh NAHI hai ki koi execution " +
  "nahi hui — abhi hum bata hi nahi paa rahe. Dobara try karo.";

/**
 * Shown while the first read is still in flight. Distinct from
 * EMPTY_LOG_NOTE for the same reason FETCH_FAILED_NOTE is: "you have no
 * executions" is a CLAIM, and before the response lands we have not learned
 * anything to claim.
 */
export const LOADING_LOG_NOTE = "Execution log load ho raha hai…";

/**
 * Appended when the server cut the list short. A silent cap would present a
 * partial log as the whole history.
 */
export const TRUNCATED_LOG_NOTE =
  "Sirf sabse recent entries dikhayi ja rahi hain — is se purani history bhi hai.";

/**
 * The known GAP, stated rather than hidden. The Close button runs
 * KillSwitchService.kill_subscriber, which writes no execution row, so a
 * hand-closed position shows its entry here and no exit. Without this line a
 * customer reads the missing exit as "still running".
 */
export const MANUAL_CLOSE_GAP_NOTE =
  "Note: Close button se manually band ki gayi position ka exit is log mein " +
  "record nahi hota — sirf signal se hui executions yahan aati hain.";

export const EMPTY_LOG_NOTE =
  "Abhi is subscription pe koi execution record nahi hai.";
