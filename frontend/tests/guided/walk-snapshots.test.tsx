/**
 * Rendered SNAPSHOTS of every screen the scripted first-timer met on the throwaway
 * stack (founder, 26 Sep 2026, item 5). No browser on the box (SETTLED 20 Sep): these
 * are the real components rendered with the SERVER'S real answers from the walk, written
 * out as HTML — text + markup, not pixels. Pixels at 390×844 are the Mac's job.
 *
 * Runs only when GUIDED_WALK_DIR points at a walk's artefact directory
 * (…/journey_walk_artefacts/<walk>); otherwise it is skipped and says so.
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { existsSync, readdirSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const DIR = process.env.GUIDED_WALK_DIR ?? "";

const guidedApi = vi.hoisted(() => ({
  publicStart: vi.fn(), state: vi.fn(), choose: vi.fn(), back: vi.fn(), broker: vi.fn(), ask: vi.fn(),
  confirm: vi.fn(), running: vi.fn(), stopPreview: vi.fn(), stop: vi.fn(), signup: vi.fn(), restart: vi.fn(),
}));
vi.mock("@/lib/guided-path", async (orig) => ({ ...(await orig<typeof import("@/lib/guided-path")>()), guidedApi }));

import { ErrorCard } from "@/components/guided/guided-parts";
import { GuidedPath } from "@/components/guided/guided-path";
import { RunningDashboard } from "@/components/guided/guided-running";

interface Rec { n: number; label: string; status: number; response: Record<string, unknown> }

function recs(): Rec[] {
  return readdirSync(DIR).filter((f) => /^\d\d-.*\.json$/.test(f)).sort()
    .map((f) => JSON.parse(readFileSync(join(DIR, f), "utf8")) as Rec);
}

/** GUIDED_CSS_HREF: the app's own compiled stylesheet (saved from the served /start page), so a
 *  snapshot opened on a phone shows the real tokens — still not a pixel measurement. */
function page(title: string, body: string): string {
  const css = process.env.GUIDED_CSS_HREF ? `<link rel="stylesheet" href="${process.env.GUIDED_CSS_HREF}">` : "";
  return `<!doctype html><html lang="hi" class="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">`
    + `<title>${title}</title>${css}</head><body class="bg-background text-foreground" style="max-width:390px;margin:0 auto;padding:16px">`
    + `${body}</body></html>\n`;
}

describe.skipIf(!DIR || !existsSync(DIR))("walk snapshots", () => {
  it("renders every screen and every error the customer met", async () => {
    const out = join(DIR, "snapshots");
    mkdirSync(out, { recursive: true });
    const index: string[] = [];
    for (const r of recs()) {
      const res = r.response as { step?: string; screen?: unknown; error?: unknown; strategy?: unknown };
      let html = "";
      if (res.error) {
        const { container, unmount } = render(<ErrorCard err={res.error as never} onAction={() => {}} onBack={() => {}} />);
        html = container.innerHTML;
        unmount();
      } else if (res.screen && res.step && res.step !== "RUNNING") {
        localStorage.setItem("tb_access_token", "t");
        guidedApi.state.mockResolvedValue(res);
        guidedApi.publicStart.mockResolvedValue(res);
        if (res.step === "SIGNUP") localStorage.clear();
        const { container, unmount } = render(<GuidedPath />);
        await screen.findByTestId(res.step === "SIGNUP" ? "screen-SIGNUP" : "guided");
        html = container.innerHTML;
        unmount();
      } else if (r.label.startsWith("running") || r.label.includes("running-")) {
        guidedApi.running.mockResolvedValue(res);
        const { container, unmount } = render(<RunningDashboard onGoto={() => {}} />);
        await screen.findByTestId("running");
        html = container.innerHTML;
        unmount();
      } else {
        continue;
      }
      const name = `${String(r.n).padStart(2, "0")}-${r.label}.html`;
      writeFileSync(join(out, name), page(r.label, html));
      index.push(name);
      expect(html.length).toBeGreaterThan(50);
    }
    writeFileSync(join(out, "INDEX.txt"), index.join("\n") + "\n");
    expect(index.length).toBeGreaterThan(5);
  }, 60_000);
});
