/**
 * The Pro chrome speaks ONE language too (founder, 2 Oct 2026). PRO_NAV keeps the Hinglish source;
 * every group title, every page blurb and every page action must have a dictionary key in BOTH
 * languages — a missing key would be a per-key fallback, which the one-language rule forbids.
 * Twin: remove "/settings" from NAV_BLURB_KEY → RED.
 */
import { describe, expect, it } from "vitest";

import { appCopy } from "@/lib/i18n/copy/app";
import { NAV_ACTION_KEY, NAV_BLURB_KEY, NAV_GROUP_KEY, PRO_NAV, navAction, navBlurb, navGroupTitle } from "@/lib/nav/pro-nav";

const en = appCopy.dicts.en as Record<string, string>;
const hi = appCopy.dicts.hinglish as Record<string, string>;

describe("pro-nav words", () => {
  it("every group title has a key, and both languages carry it", () => {
    for (const g of PRO_NAV) {
      const k = NAV_GROUP_KEY[g.title];
      expect(k, g.title).toBeTruthy();
      expect(en[k], k).toBeTruthy();
      expect(hi[k], k).toBeTruthy();
      expect(navGroupTitle(hi, g.title)).toBe(g.title);           // the Hinglish dictionary = the source
    }
  });

  it("every item blurb and action has a key, and the Hinglish dictionary equals the source", () => {
    for (const item of PRO_NAV.flatMap((g) => g.items)) {
      const k = NAV_BLURB_KEY[item.href];
      expect(k, item.href).toBeTruthy();
      expect(en[k], k).toBeTruthy();
      expect(hi[k], k).toBe(item.blurb);
      expect(navBlurb(en, item)).toBe(en[k]);
      if (item.action) {
        const a = NAV_ACTION_KEY[item.action.href];
        expect(a, item.action.href).toBeTruthy();
        expect(hi[a]).toBe(item.action.label);
        expect(navAction(en, item)?.label).toBe(en[a]);
      }
    }
  });

  it("an unknown item never leaks Hinglish into an English page: no blurb at all", () => {
    expect(navBlurb(en, undefined)).toBe("");
  });
});
