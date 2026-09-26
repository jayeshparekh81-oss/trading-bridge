/**
 * THE SUBSCRIPTION SETTINGS SCREEN — one screen, one decision (founder, 26 Sep 2026,
 * after walking the live site; REQUIREMENTS §13).
 *
 *  6. the RED he found: with NEXT_PUBLIC_CUSTOMER_VEHICLES=1 on Vercel the phone still
 *     showed "Abhi band" on Cash/Futures/Options — because (a) every flag was read as
 *     `process.env[CONST]`, which Next does NOT inline into the browser bundle (served
 *     chunk of 2c7b84ab: `"1"===P.default.env.NEXT_PUBLIC_CUSTOMER_VEHICLES`, env = {}),
 *     and (b) the old disabled vehicle block rendered whatever the flag said;
 *  1. one line per vehicle: needs · risk label · worst real day, each with its basis;
 *     every other word kept behind a CLOSED "Aur jaano";
 *  2. one decision on screen: four steps, one visible, exactly one primary button, Back keeps state;
 *  3. "Settings save karo" sticky at the bottom above the phone's own bar, ≥ 44px;
 *  4. the practice banner pinned at the top with his exact words, from the SAVED mode only;
 *  5. nothing that breaks a 375px column: no dropdown with long choices, no nowrap, long
 *     words wrap, rows can shrink.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import staticJson from "@/lib/vehicle-board.static.json";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
const urls: Array<string | null> = [];
vi.mock("@/shared/api/use-api", () => ({
  useApi: (url: string | null) => {
    urls.push(url);
    return { data: null, isLoading: false, error: null, paywalled: false, paywallUrl: null, refetch: vi.fn() };
  },
}));
vi.mock("@/shared/api/client", () => {
  class ApiError extends Error {
    status: number;
    detail: string;
    constructor(s: number, d: string) {
      super(d);
      this.status = s;
      this.detail = d;
    }
  }
  return { api: { get: vi.fn(), patch: vi.fn() }, ApiError };
});

import { api } from "@/shared/api/client";
import {
  PRACTICE_BANNER,
  SETTINGS_STEPS,
  SubscriptionSettings,
} from "@/components/marketplace/subscription-settings";
import { vehicleFacts } from "@/components/marketplace/vehicle-picker";

const get = api.get as ReturnType<typeof vi.fn>;
const ROOT = process.cwd();
const read = (rel: string) => readFileSync(join(ROOT, rel), "utf8");

const SAVED = {
  subscription_id: "s1",
  lots_override: null,
  execution_mode: "offline",
  is_paper: true,
  applied: false,
  pending_fanout_merge: true,
  direction_filter: "all",
};

/** Set the two flags exactly as they are on Vercel today (coordinator, 26 Sep). */
function asOnVercel() {
  process.env.NEXT_PUBLIC_CUSTOMER_VEHICLES = "1";
  process.env.NEXT_PUBLIC_VEHICLE_PICKER_SOURCE = "static";
}

async function renderSettings(saved: object | Error = SAVED) {
  if (saved instanceof Error) get.mockRejectedValueOnce(saved);
  else get.mockResolvedValueOnce(saved);
  render(<SubscriptionSettings subscriptionId="s1" />);
  await waitFor(() => screen.getByTestId("subscription-settings"));
}

/** A step is on screen when neither it nor an ancestor carries `hidden`. */
function onScreen(el: HTMLElement): boolean {
  for (let n: HTMLElement | null = el; n; n = n.parentElement) if (n.hidden) return false;
  return true;
}
/** The primary buttons on screen: the shared Button's default variant carries bg-primary. */
function visiblePrimaries(): HTMLElement[] {
  return screen.getAllByRole("button", { hidden: true }).filter((b) => onScreen(b) && /\bbg-primary\b/.test(b.className));
}

beforeEach(() => {
  vi.clearAllMocks();
  urls.length = 0;
  delete process.env.NEXT_PUBLIC_CUSTOMER_VEHICLES;
  delete process.env.NEXT_PUBLIC_VEHICLE_PICKER_SOURCE;
});
afterEach(() => {
  delete process.env.NEXT_PUBLIC_CUSTOMER_VEHICLES;
  delete process.env.NEXT_PUBLIC_VEHICLE_PICKER_SOURCE;
});

// ═════════════════════════════════════════════════════════════════════════════
// POINT 6 — the flag must reach the phone
// ═════════════════════════════════════════════════════════════════════════════

function walk(dir: string): string[] {
  return readdirSync(join(ROOT, dir)).flatMap((f) => {
    const rel = `${dir}/${f}`;
    return statSync(join(ROOT, rel)).isDirectory() ? walk(rel) : /\.(ts|tsx)$/.test(f) ? [rel] : [];
  });
}
/** A browser flag read through a variable is never inlined by Next (its own docs,
 * environment-variables.md:182-192) — it reads an EMPTY object on the phone. */
export function computedEnvReads(src: string): string[] {
  const code = src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`])\/\/[^\n]*/g, "$1");
  return [...code.matchAll(/process\.env\[[^\]]+\]/g)].map((m) => m[0]);
}
/** The one allowed dynamic read, and why: its fallback IS the right number, and turning it
 * literal would switch on a Vercel value nobody has measured (recorded, not changed tonight). */
const COMPUTED_ENV_ALLOW: Record<string, string> = {
  "src/lib/algomitra-personality.ts": "envOrDefault(key): fallback is the correct support number; a literal read would activate an unmeasured Vercel value",
};

describe("point 6 — a Vercel flag reaches the phone", () => {
  it("no browser code reads a flag through a variable (Next leaves it EMPTY on the phone)", () => {
    const hits = walk("src").flatMap((f) =>
      COMPUTED_ENV_ALLOW[f] ? [] : computedEnvReads(read(f)).map((r) => `${f}: ${r}`),
    );
    expect(hits).toEqual([]);
  });
  it("the scan catches the exact shape that shipped in 2c7b84ab (falsification twin)", () => {
    expect(computedEnvReads(`return process.env[VEHICLE_FLAG] === "1";`)).toHaveLength(1);
    expect(computedEnvReads(`return process.env.NEXT_PUBLIC_CUSTOMER_VEHICLES === "1";`)).toEqual([]);
  });
  it("every customer flag getter uses the one spelling Next inlines", () => {
    const want: Record<string, string> = {
      "src/lib/customer-vehicles.ts": "process.env.NEXT_PUBLIC_CUSTOMER_VEHICLES",
      "src/lib/vehicle-cards.ts": "process.env.NEXT_PUBLIC_VEHICLE_PICKER_SOURCE",
      "src/lib/guided-path.ts": "process.env.NEXT_PUBLIC_CUSTOMER_GUIDED_PATH",
      "src/lib/account-truth.ts": "process.env.NEXT_PUBLIC_CUSTOMER_DASHBOARD",
      "src/lib/customer-journey.ts": "process.env.NEXT_PUBLIC_CUSTOMER_JOURNEY",
    };
    for (const [f, spelling] of Object.entries(want)) expect(read(f), f).toContain(spelling);
  });
  it("with both flags as on Vercel, FUTURES is choosable in paper and nothing says 'Abhi band' about it", async () => {
    asOnVercel();
    await renderSettings();
    expect(screen.queryByTestId("vehicle-coming-soon")).toBeNull(); // the old block is gone
    expect(screen.getByTestId("vehicle-picker")).toHaveAttribute("data-source", "static");
    expect(urls.every((u) => u === null)).toBe(true); // static: no server call
    const fut = screen.getByTestId("vehicle-line-FUTURES");
    expect(within(fut).getByTestId("vehicle-selectable-FUTURES").textContent).toBe("Chuno · paper");
    expect(fut).toHaveAttribute("aria-checked", "true"); // the safe default, preselected
    for (const v of ["CASH", "OPTION_BUY", "BULL_CALL_SPREAD", "BEAR_PUT_SPREAD"]) {
      const line = screen.getByTestId(`vehicle-line-${v}`);
      expect(line.textContent).toMatch(/Band/);
      expect(within(line).queryByTestId(`vehicle-selectable-${v}`)).toBeNull();
    }
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// POINT 1 — one line per vehicle; every other word behind a closed "Aur jaano"
// ═════════════════════════════════════════════════════════════════════════════

describe("point 1 — one line per vehicle, the rest behind Aur jaano", () => {
  it("each line carries needs · risk · worst real day, each with its basis marker", () => {
    expect(vehicleFacts("FUTURES")).toMatch(/^Chahiye: .*6\.3.*\(2 lot \(packet\) par, naapa\) · Risk: MEDIUM \(hamara andaaza\) · Sabse bura din: −₹63,105 \(naapa, 2 lot \(packet\) par\)$/);
    for (const v of ["CASH", "OPTION_BUY", "BULL_CALL_SPREAD", "BEAR_PUT_SPREAD"] as const) {
      expect(vehicleFacts(v)).toMatch(/^Chahiye: NOT MEASURED · Risk: (LOW|HIGH) \(hamara andaaza\) · Sabse bura din: NOT MEASURED \(koi record nahi\)$/);
    }
  });
  it("the disclosure is CLOSED by default and keeps every honest word (flags as on Vercel)", async () => {
    asOnVercel();
    await renderSettings();
    const more = screen.getByTestId("vehicle-more");
    expect(more.tagName).toBe("DETAILS");
    expect(more.hasAttribute("open")).toBe(false);
    expect(within(more).getByText("Aur jaano").tagName).toBe("SUMMARY");
    const text = more.textContent ?? "";
    // every waiting sentence of the generated board, word for word
    for (const v of staticJson.vehicles) expect(text).toContain(v.waiting_for);
    // margin method, the 715 trades, the charges basis, the judgement disclaimer
    expect(text).toMatch(/715 trade/);
    expect(text).toMatch(/andaazan charges/);
    expect(text).toMatch(/broker ka rok/i);
    expect(text).toMatch(/founder ka judgement/);
    expect(text).toMatch(/order nahi bhejta/);
  });
  it("with the flag OFF the old wording is kept — collapsed, not shouting", async () => {
    await renderSettings();
    const more = screen.getByTestId("vehicle-more");
    expect(more.hasAttribute("open")).toBe(false);
    expect(within(more).getByTestId("vehicle-coming-soon")).toBeInTheDocument();
    expect(within(more).getByTestId("risk-legend")).toBeInTheDocument();
    expect(screen.getByTestId("vehicle-one-line").textContent).toMatch(/Futures/);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// POINT 2 — one decision on screen, one primary, Back keeps state
// ═════════════════════════════════════════════════════════════════════════════

const STEP_IDS = ["settings-step-vehicle", "settings-step-size", "settings-step-direction", "settings-step-mode"];

describe("point 2 — one screen, one decision", () => {
  it("the steps are his four decisions, in order", () => {
    expect(SETTINGS_STEPS.map((s) => s.key)).toEqual(["vehicle", "size", "direction", "mode"]);
  });
  it("exactly ONE step and exactly ONE primary button on screen, on every step", async () => {
    asOnVercel();
    await renderSettings();
    for (let i = 0; i < STEP_IDS.length; i++) {
      const shown = STEP_IDS.filter((id) => onScreen(screen.getByTestId(id)));
      expect(shown, `step ${i + 1}`).toEqual([STEP_IDS[i]]);
      expect(screen.getByTestId("settings-step-title").textContent).toBe(SETTINGS_STEPS[i].title);
      const primaries = visiblePrimaries();
      expect(primaries.map((b) => b.dataset.testid), `step ${i + 1}`).toEqual(["save-settings"]);
      if (i < STEP_IDS.length - 1) fireEvent.click(screen.getByTestId("settings-next"));
    }
    expect(screen.queryByTestId("settings-next")).toBeNull(); // last step: nothing further
  });
  it("Back never loses a choice (size and direction survive a round trip)", async () => {
    await renderSettings();
    fireEvent.click(screen.getByTestId("settings-next")); // → size
    fireEvent.change(screen.getByTestId("lots-override-input"), { target: { value: "6" } });
    fireEvent.click(screen.getByTestId("settings-next")); // → direction
    fireEvent.mouseDown(screen.getByTestId("direction-short"));
    fireEvent.click(screen.getByTestId("direction-short"));
    fireEvent.click(screen.getByTestId("settings-back")); // → size
    expect(screen.getByTestId("lots-override-input")).toHaveValue(6);
    fireEvent.click(screen.getByTestId("settings-back")); // → vehicle
    fireEvent.click(screen.getByTestId("settings-next"));
    fireEvent.click(screen.getByTestId("settings-next")); // → direction again
    expect(screen.getByTestId("direction-short")).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("lots-override-input")).toHaveValue(6);
  });
  it("the SAVED choices come back into the form — a saved 'Sirf bech' is never shown (and re-saved) as 'Dono'", async () => {
    // Found 26 Sep while rebuilding this screen: the direction state was initialised once,
    // before the GET answered, so the saved side was never loaded and Save overwrote it.
    await renderSettings({ ...SAVED, direction_filter: "short", lots_override: 8, execution_mode: "paper" });
    expect(screen.getByTestId("direction-short")).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("lots-override-input")).toHaveValue(8);
    expect(screen.getByTestId("execution-mode-paper")).toHaveAttribute("aria-checked", "true");
  });
  it("the safe defaults are already chosen: smallest size 2, both directions", async () => {
    await renderSettings();
    expect(screen.getByTestId("lots-override-input")).toHaveValue(2);
    expect(screen.getByTestId("direction-all")).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("execution-mode-offline")).toHaveAttribute("aria-checked", "true");
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// POINT 3 — sticky save, above the phone's bottom bar, thumb-sized, never covering content
// ═════════════════════════════════════════════════════════════════════════════

describe("point 3 — Settings save karo is sticky, visible, thumb-sized", () => {
  it("the save bar is sticky above the phone's own bottom bar and is the LAST thing in the flow", async () => {
    await renderSettings();
    const bar = screen.getByTestId("settings-save-bar");
    expect(bar.className).toMatch(/\bsticky\b/);
    expect(bar.className).toContain("bottom-[var(--bottom-chrome,0px)]");
    expect(bar.className).toContain("env(safe-area-inset-bottom");
    expect(bar.className).not.toMatch(/\bfixed\b/); // in flow: it can never sit on top of the last line
    expect(screen.getByTestId("subscription-settings").lastElementChild).toBe(bar);
    const btn = within(bar).getByTestId("save-settings");
    expect(btn.className).toMatch(/\bmin-h-12\b/); // 48px ≥ the 44px tap floor
    expect(btn.className).toMatch(/\bw-full\b/);
    expect(btn.textContent).toMatch(/Settings save karo/);
  });
  it("save is on screen on every step", async () => {
    await renderSettings();
    for (let i = 0; i < STEP_IDS.length; i++) {
      expect(onScreen(screen.getByTestId("save-settings")), `step ${i + 1}`).toBe(true);
      if (i < STEP_IDS.length - 1) fireEvent.click(screen.getByTestId("settings-next"));
    }
  });
  it("both shells say how tall their fixed phone bar is (the sticky bar reads it)", () => {
    const css = read("src/app/globals.css");
    expect(css).toMatch(/\.chrome-pro\s*\{[^}]*--bottom-chrome:\s*4\.0625rem/);
    expect(css).toMatch(/\.chrome-simple\s*\{[^}]*--bottom-chrome:\s*calc\(/);
    expect(css).toMatch(/\.chrome-simple\s*\{[^}]*--top-chrome:\s*3\.5625rem/);
    expect(read("src/app/(dashboard)/layout.tsx")).toContain('"chrome-pro flex-1 overflow-y-auto');
    expect(read("src/components/simple/simple-shell.tsx")).toContain('<main className="chrome-simple');
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// POINT 4 — the practice banner, his exact words, from the ONE source
// ═════════════════════════════════════════════════════════════════════════════

describe("point 4 — the practice banner", () => {
  it("his exact words", () => {
    expect(PRACTICE_BANNER).toBe("Practice mode: nakli order, asli paisa nahi lagta");
  });
  it("pinned at the top, first thing on the screen, when the SAVED mode is paper", async () => {
    await renderSettings();
    const banner = screen.getByTestId("practice-banner");
    expect(banner.textContent).toBe(PRACTICE_BANNER);
    expect(banner.className).toMatch(/\bsticky\b/);
    expect(banner.className).toContain("top-[var(--top-chrome,0px)]");
    expect(screen.getByTestId("subscription-settings").firstElementChild).toBe(banner);
  });
  it("not shown when the saved mode is real — it is read, never assumed", async () => {
    await renderSettings({ ...SAVED, is_paper: false });
    expect(screen.queryByTestId("practice-banner")).toBeNull();
  });
  it("not shown when the settings could not be read — the red line speaks instead", async () => {
    await renderSettings(new Error("down"));
    expect(screen.getByTestId("settings-load-failed")).toBeInTheDocument();
    expect(screen.queryByTestId("practice-banner")).toBeNull();
  });
  it("a draft change does not move the banner — it shows what is SAVED", async () => {
    await renderSettings();
    fireEvent.click(screen.getByTestId("is-paper-toggle"));
    expect(screen.getByTestId("practice-banner")).toBeInTheDocument();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// POINT 5 — the 375px column (measured from the source; pixels are the Mac's walk)
// ═════════════════════════════════════════════════════════════════════════════

describe("point 5 — nothing breaks a 375px column", () => {
  const settings = read("src/components/marketplace/subscription-settings.tsx");
  const picker = read("src/components/marketplace/vehicle-picker.tsx");
  it("no dropdown with long choices on the settings screen (a closed select cuts them)", () => {
    expect(settings).not.toMatch(/<select\b/);
  });
  it("no forced single-line text on the settings screen", () => {
    expect(settings.replace(/\/\*[\s\S]*?\*\//g, "")).not.toMatch(/\bwhitespace-nowrap\b/);
  });
  it("the long sentences may wrap inside a word only when a word is wider than the phone", () => {
    for (const src of [settings, picker]) {
      expect(src).toMatch(/wrap-break-word/);
      expect(src).not.toMatch(/\bbreak-all\b/); // never chop ordinary words
    }
    // the waiting sentences carry file names like kb/PRE_LAUNCH_CHECKLIST.md — no spaces to break on
    expect(picker).toMatch(/data-testid=\{asInfo \? `vehicle-detail-waiting-\$\{v\.vehicle\}` : `vehicle-waiting-\$\{v\.vehicle\}`\} className="wrap-break-word/);
  });
  it("every row of the one-line vehicle list and the step nav can shrink (min-w-0)", () => {
    expect(picker).toMatch(/data-testid=\{`vehicle-line-\$\{v\.vehicle\}`\}[\s\S]{0,200}min-w-0/);
    expect(settings).toMatch(/data-testid="settings-step-nav" className="flex min-w-0/);
  });
});
