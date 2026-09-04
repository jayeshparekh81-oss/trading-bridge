/**
 * Founder decision (2026-09-04): the AlgoMitra "Calendly" escalation was a
 * dead link on prod (the default calendly.com page answers 404). Every
 * escalation now goes to the founder's WhatsApp or email. This pins it at
 * three levels: the flow tables, the URL map, and the source text.
 */

import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { FLOWS } from "@/lib/algomitra-flows";
import { ALGOMITRA_ESCALATION, FOUNDER_WHATSAPP_NUMBER } from "@/lib/algomitra-personality";
import { ALGOMITRA_FAQS } from "@/lib/algomitra-faqs";

type Opt = { label: string; action?: { kind: string; channel?: string } };

function walk(dir: string, acc: string[] = []): string[] {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) walk(p, acc);
    else if (/\.(tsx?|mdx?)$/.test(e.name)) acc.push(p);
  }
  return acc;
}

describe("AlgoMitra escalation never resolves to Calendly", () => {
  const exits: { flow: string; step: string; opt: Opt }[] = [];
  for (const [flowId, flow] of Object.entries(FLOWS as Record<string, { steps: Record<string, { options?: readonly Opt[] }> }>)) {
    for (const [stepId, step] of Object.entries(flow.steps)) {
      for (const opt of step.options ?? []) if (opt.action?.kind === "escalate") exits.push({ flow: flowId, step: stepId, opt });
    }
  }

  it("every flow exit escalates to whatsapp or email only", () => {
    expect(exits.length).toBeGreaterThan(5);
    for (const e of exits) expect(["whatsapp", "email"], `${e.flow}/${e.step} "${e.opt.label}"`).toContain(e.opt.action?.channel);
  });

  it("the URL map has no calendly key and the WhatsApp URL carries the founder's number", () => {
    expect(Object.keys(ALGOMITRA_ESCALATION)).not.toContain("calendlyUrl");
    for (const url of Object.values(ALGOMITRA_ESCALATION)) expect(url).not.toMatch(/calendly/i);
    expect(ALGOMITRA_ESCALATION.whatsappUrl).toContain(`wa.me/${FOUNDER_WHATSAPP_NUMBER}`);
  });

  it("no chip label or FAQ answer sells a Calendly / slot / 1-on-1 booking", () => {
    for (const e of exits) expect(e.opt.label).not.toMatch(/calendly|slot book|1-on-1|📅/i);
    for (const faq of ALGOMITRA_FAQS as unknown as { answers?: unknown }[]) {
      const text = JSON.stringify(faq.answers ?? faq);
      expect(text).not.toMatch(/calendly/i);
    }
  });

  it("AI suggestions that mention Calendly are filtered before they become chips (the backend prompt may still say 'Book Calendly')", () => {
    const hook = readFileSync(join(process.cwd(), "src/hooks/useAlgoMitra.ts"), "utf8");
    expect(hook).toMatch(/\.filter\(\(label\) => !\/calendly\|slot book\|1-on-1\/i\.test\(label\)\)/);
  });

  it("the word calendly is gone from src/ (the two hook-local exits are not in FLOWS, so this sweep matters)", () => {
    const hits = walk(join(process.cwd(), "src")).filter((f) => {
      const body = readFileSync(f, "utf8")
        .split("\n")
        .filter((line) => !/^\s*\/\//.test(line) && !/^\s*\*/.test(line) && !/\.test\(label\)/.test(line))
        .join("\n");
      return /calendly/i.test(body);
    });
    expect(hits).toEqual([]);
    const hook = readFileSync(join(process.cwd(), "src/hooks/useAlgoMitra.ts"), "utf8")
      .split("\n")
      .filter((line) => !/^\s*\/\//.test(line) && !/\.test\(label\)/.test(line))
      .join("\n");
    expect(hook).not.toMatch(/slot book|📅/);
  });
});
