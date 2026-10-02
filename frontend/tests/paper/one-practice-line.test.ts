/**
 * ONE practice line on Positions, not two (founder, 2 Oct 2026: "fix the two yellow practice lines
 * on Positions"). A CUSTOMER account gets the practice banner from the (dashboard) layout above every
 * page; the blanket "all-paper" PaperModeBanner on /positions said the SAME fact again. The admin
 * never gets the layout banner (INC #12), so for him the blanket line stays (and his rows are real,
 * so it renders only if every row were paper). The MIXED note is a different fact and stays for all.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { blanketPaperBannerShown } from "@/lib/paper-mode";

describe("one practice line per screen", () => {
  it("a customer (non-admin) does NOT get the blanket all-paper line — the layout banner already says it", () => {
    expect(blanketPaperBannerShown("all-paper", false)).toBe(false);
    expect(blanketPaperBannerShown("all-paper", null)).toBe(false);
    expect(blanketPaperBannerShown("all-paper", undefined)).toBe(false);
  });
  it("the admin keeps it (he has no layout banner — INC #12)", () => {
    expect(blanketPaperBannerShown("all-paper", true)).toBe(true);
  });
  it("the MIXED note is a different fact and shows for everyone; unknown / none-paper show nothing", () => {
    expect(blanketPaperBannerShown("mixed", false)).toBe(true);
    expect(blanketPaperBannerShown("mixed", true)).toBe(true);
    expect(blanketPaperBannerShown("unknown", false)).toBe(false);
    expect(blanketPaperBannerShown("none-paper", true)).toBe(false);
  });
  it("/positions asks the rule before rendering the banner (source)", () => {
    const src = readFileSync(resolve(__dirname, "../../src/app/(dashboard)/positions/page.tsx"), "utf8");
    expect(src).toMatch(/\{blanketPaperBannerShown\(scope, user\?\.is_admin\) && <PaperModeBanner scope=\{scope\} \/>\}/);
    expect(src).not.toMatch(/^\s*<PaperModeBanner scope=\{scope\} \/>\s*$/m);
  });
});
