/**
 * Drift notice banner — renders from the API field, and the copy must never
 * read as a failure.
 *
 * The customer closed their own position at their own broker. Nothing failed.
 * Copy that says otherwise would alarm someone who did nothing wrong.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { DriftNoticeBanner } from "@/components/marketplace/drift-notice-banner";
import {
  DRIFT_NOTICE_REASSURANCE,
  DRIFT_NOTICE_TITLE,
  type DriftNotice,
  driftNoticeBody,
} from "@/lib/drift-notice";

const notice: DriftNotice = {
  flipped_at: "2026-08-23T06:30:00Z",
  symbol: "BSE-AUG2026-FUT",
  reason: "broker_flat",
};

// Words that would misrepresent a working-as-designed event as a malfunction.
const FAILURE_WORDS = [
  "failed", "failure", "error", "problem", "issue", "wrong",
  "invalid", "rejected", "unable", "crash", "fault", "warning",
];

function assertNoFailureWords(text: string) {
  const low = text.toLowerCase();
  for (const w of FAILURE_WORDS) {
    // "Kuch galat nahi hua" is the reassurance — it must not trip the check.
    expect(low.includes(w), `copy must not contain "${w}"`).toBe(false);
  }
}

describe("DriftNoticeBanner", () => {
  it("renders nothing when there is no notice", () => {
    const { container } = render(<DriftNoticeBanner notice={null} />);
    expect(container.firstChild).toBeNull();
    expect(screen.queryByTestId("drift-notice-banner")).toBeNull();
  });

  it("renders nothing when the field is undefined (older API payload)", () => {
    const { container } = render(<DriftNoticeBanner notice={undefined} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders the title, body and reassurance when present", () => {
    render(<DriftNoticeBanner notice={notice} />);
    const el = screen.getByTestId("drift-notice-banner");
    const text = el.textContent ?? "";

    expect(text).toContain(DRIFT_NOTICE_TITLE);
    expect(text).toContain("BSE-AUG2026-FUT");
    expect(text).toContain(DRIFT_NOTICE_REASSURANCE);
  });

  it("keeps the two lines the founder specified verbatim", () => {
    render(<DriftNoticeBanner notice={notice} />);
    const text = screen.getByTestId("drift-notice-banner").textContent ?? "";
    expect(text).toContain("Aapne yeh position apne broker par khud band ki thi");
    expect(text).toContain("Kuch galat nahi hua");
  });

  it("points the customer at Settings to re-enable AUTO", () => {
    render(<DriftNoticeBanner notice={notice} />);
    const text = screen.getByTestId("drift-notice-banner").textContent ?? "";
    expect(text).toMatch(/Settings/);
    expect(text).toMatch(/AUTO/);
  });

  it("is styled amber/informational, NOT red/error", () => {
    render(<DriftNoticeBanner notice={notice} />);
    const cls = screen.getByTestId("drift-notice-banner").className;
    expect(cls).toMatch(/amber/);
    // The loss/destructive palette must not be used for this.
    expect(cls).not.toMatch(/text-loss|bg-loss|border-loss|destructive|red-/);
  });

  it("handles a null symbol without an awkward sentence", () => {
    render(<DriftNoticeBanner notice={{ ...notice, symbol: null }} />);
    const text = screen.getByTestId("drift-notice-banner").textContent ?? "";
    expect(text).toContain("yeh position");
    expect(text).not.toContain("null");
    expect(text).not.toContain("undefined");
  });

  it("words a partial close differently from a full close", () => {
    const full = driftNoticeBody(notice);
    const partial = driftNoticeBody({ ...notice, reason: "broker_partial" });
    expect(full).not.toBe(partial);
    expect(partial).toContain("poori tarah");
  });

  it("survives a malformed timestamp", () => {
    render(<DriftNoticeBanner notice={{ ...notice, flipped_at: "not-a-date" }} />);
    const text = screen.getByTestId("drift-notice-banner").textContent ?? "";
    expect(text).toContain(DRIFT_NOTICE_TITLE);
    expect(text).not.toContain("Invalid Date");
  });
});

// ═══════════════════════════════════════════════════════════════════════
// ⚠️ COPY DISCIPLINE
// ═══════════════════════════════════════════════════════════════════════
describe("drift copy contains no failure wording", () => {
  it("title", () => assertNoFailureWords(DRIFT_NOTICE_TITLE));
  it("reassurance", () => assertNoFailureWords(DRIFT_NOTICE_REASSURANCE));

  it.each(["broker_flat", "broker_partial"])("body (%s)", (reason) => {
    assertNoFailureWords(driftNoticeBody({ ...notice, reason }));
  });

  it("the whole rendered banner", () => {
    render(<DriftNoticeBanner notice={notice} />);
    assertNoFailureWords(
      screen.getByTestId("drift-notice-banner").textContent ?? "",
    );
  });

  it("does not blame the customer", () => {
    const all = [
      DRIFT_NOTICE_TITLE,
      DRIFT_NOTICE_REASSURANCE,
      driftNoticeBody(notice),
    ].join(" ").toLowerCase();
    for (const w of ["you should", "you must", "aapko karna chahiye"]) {
      expect(all).not.toContain(w);
    }
  });
});
