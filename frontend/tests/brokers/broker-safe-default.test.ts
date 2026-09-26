/**
 * "Broker jodo" opens on the SAFE DEFAULT (founder's rule, 26 Sep 2026, point 4):
 * Dhan — the broker every customer screen names — not Fyers' App ID / App Secret.
 * And Dhan's "Dobara jodo" is ONE tap to the new-key box, not "remove, re-add,
 * select Dhan, paste" (point 5/8: never a dead end).
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const SRC = readFileSync(join(process.cwd(), "src/app/(dashboard)/brokers/page.tsx"), "utf8");

describe("Broker jodo", () => {
  it("the first broker in the dialog is Dhan", () => {
    const list = SRC.slice(SRC.indexOf("const BROKER_SCHEMAS"));
    expect(list.indexOf('value: "dhan"')).toBeGreaterThan(-1);
    expect(list.indexOf('value: "dhan"')).toBeLessThan(list.indexOf('value: "fyers"'));
    expect(SRC).toContain("useState<string>(BROKER_SCHEMAS[0].value)");
  });
  it("Dhan's reconnect opens the new-key box in one tap", () => {
    const fn = SRC.slice(SRC.indexOf("async function handleReconnect"), SRC.indexOf("async function handleRemove"));
    expect(fn).toMatch(/if \(name === "dhan"\) \{[\s\S]{0,200}setUpdateDhanOpen\(true\)/);
    expect(fn).not.toMatch(/Remove this connection/);
  });
});
