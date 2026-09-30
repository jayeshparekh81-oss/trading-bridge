/**
 * The practice-mode banner on every customer-path screen (founder, 1 Oct 2026: "paper demo only
 * with the practice banner on every screen"). TRUE for every visitor: the customer path sends no
 * order to any broker while MARKETPLACE_FANOUT_ENABLED / CUSTOMER_LANE_ORDER_ENABLED are OFF —
 * worded about THIS path, so it never tells the founder his own live BSE strategy is paper (INC #12).
 */

export const PRACTICE_PATH_LINE =
  "Practice mode: is raaste par nakli order hote hain, asli paisa nahi lagta — koi order broker tak nahi jaata.";

export function PracticeBanner() {
  return (
    <div
      role="status"
      data-testid="practice-banner"
      className="sticky top-0 z-20 w-full border-b border-accent-gold/40 bg-accent-gold/10 px-4 py-2 text-center text-sm font-medium text-foreground"
    >
      {PRACTICE_PATH_LINE}
    </div>
  );
}
