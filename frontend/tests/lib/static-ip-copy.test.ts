/**
 * Static-IP copy (D3): the numbers a customer reads are the numbers the backend
 * enforces — one IP per person, a 7-day lock — and every line says what to DO.
 */

import { describe, it, expect } from "vitest";
import {
  DHAN_IP_LOCK_DAYS,
  DHAN_IPS_PER_PERSON,
  STATIC_IP_COST_BASIS,
  STATIC_IP_COST_INR_BEFORE_GST,
  STATIC_IP_NEXT_STEP_HI,
  STATIC_IP_RULES_HI,
  ipLockRefusalLine,
} from "@/lib/static-ip-copy";

describe("static-ip copy", () => {
  it("pins the rules the backend ip_lock enforces", () => {
    expect(DHAN_IP_LOCK_DAYS).toBe(7);      // backend/app/domains/customer_lane/ip_lock.py BROKER_LOCK_DAYS
    expect(DHAN_IPS_PER_PERSON).toBe(1);
    expect(STATIC_IP_COST_INR_BEFORE_GST).toBe(350);
    expect(STATIC_IP_COST_BASIS).toContain("NOT MEASURED"); // GST is not measured
  });
  it("every rule line carries the number it warns about and an action", () => {
    const joined = STATIC_IP_RULES_HI.join("\n");
    expect(STATIC_IP_RULES_HI.length).toBeGreaterThanOrEqual(3);
    expect(joined).toContain(`${DHAN_IP_LOCK_DAYS} din`);
    expect(joined).toContain("share nahi");
    expect(joined).toContain("confirm karo");
    expect(joined).toContain("GST alag");
    expect(STATIC_IP_NEXT_STEP_HI).toMatch(/dabao/);
  });
  it("a refusal names WHEN the change opens, in IST, or NOT MEASURED", () => {
    expect(ipLockRefusalLine("2026-10-02T04:30:00+00:00")).toMatch(/Agla mauka: .*IST/);
    expect(ipLockRefusalLine("2026-10-02T04:30:00+00:00")).toContain("7 din");
    expect(ipLockRefusalLine(null)).toContain("NOT MEASURED");
    expect(ipLockRefusalLine("garbage")).toContain("NOT MEASURED");
  });
});
