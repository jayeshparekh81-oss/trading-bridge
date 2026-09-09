/**
 * A loss must show its minus sign.
 *
 * `formatCurrency` rendered `Math.abs(amount)` with no leading "-", so the
 * founder's -198,265.66 realised loss on the 04 Jun BSE position printed as
 * "₹1,98,266" — a figure that reads as a gain. Only the red text
 * distinguished it.
 *
 * Colour is not enough on a money surface. It does not survive copy-paste,
 * a grayscale print, a screenshot pasted into a message, a colour-blind
 * reader, or someone scanning a column of numbers for the negative one.
 *
 * The two branches also disagreed with each other: the compact branch divided
 * the SIGNED amount, so the same loss was "-₹1.9L" compact and "₹1,98,266"
 * full. One number, two stories, depending on which screen you were on.
 */

import { describe, it, expect } from "vitest";

import { formatCurrency } from "@/shared/lib/utils";

describe("formatCurrency never hides a loss", () => {
  it("🔴 renders the minus sign for the founder's real -198,265.66 loss", () => {
    const shown = formatCurrency(-198265.66);
    expect(shown.startsWith("-")).toBe(true);
    expect(shown).toBe("-₹1,98,266");
  });

  it("🔴 does not need showSign to render a minus", () => {
    // A plus is a flourish and stays opt-in. A minus is the fact.
    expect(formatCurrency(-500).startsWith("-")).toBe(true);
    expect(formatCurrency(-500, { showSign: false }).startsWith("-")).toBe(true);
  });

  it("🔴 compact and full agree about the sign", () => {
    const full = formatCurrency(-198265.66);
    const compact = formatCurrency(-198265.66, { compact: true });
    expect(full.startsWith("-")).toBe(true);
    expect(compact.startsWith("-")).toBe(true);
    expect(compact).toBe("-₹2.0L");
  });

  it("still keeps + opt-in for gains", () => {
    expect(formatCurrency(16520.2)).toBe("₹16,520");
    expect(formatCurrency(16520.2, { showSign: true })).toBe("+₹16,520");
  });

  it("zero is neither a gain nor a loss and wears no sign", () => {
    expect(formatCurrency(0)).toBe("₹0");
    expect(formatCurrency(0, { showSign: true })).toBe("₹0");
  });

  it("the magnitude itself is unchanged by the fix", () => {
    expect(formatCurrency(-198265.66).slice(1)).toBe(
      formatCurrency(198265.66),
    );
  });
});
