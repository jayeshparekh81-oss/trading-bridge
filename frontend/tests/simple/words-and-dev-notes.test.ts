/**
 * C3 + C10B lint: no jargon in any Simple-level string (all four languages),
 * no lesson leaks jargon, and no developer/roadmap text on customer pages.
 */
import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { JARGON_BLOCKLIST, allSimpleStrings } from "@/lib/simple/copy";
import { allLessons } from "@/lib/simple/lessons";

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.tsx?$/.test(name) && !/\.test\./.test(name)) out.push(p);
  }
  return out;
}

const stripComments = (s: string) =>
  s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "").replace(/\{\/\*[\s\S]*?\*\/\}/g, "");

describe("C3 — Simple-mode words have no jargon (hinglish, hi, gu, en)", () => {
  it("every string in every language passes the blocklist", () => {
    const bad = allSimpleStrings().filter(({ text }) => JARGON_BLOCKLIST.some((re) => re.test(text)));
    expect(bad, JSON.stringify(bad.slice(0, 5))).toEqual([]);
  });
  it("NO LOCKS: no Simple string mentions a lock or something opening later", () => {
    // Lock phrases only — "bazaar khulega" (the market opens) is ordinary language.
    const bad = allSimpleStrings().filter(({ text }) => /🔒|phir yeh khulega|फिर यह खुलेगा|પછી આ ખુલશે|then this opens|\bunlock|\blocked\b/i.test(text));
    expect(bad.map((b) => `${b.lang}:${b.key}`)).toEqual([]);
  });
  it("every language has every key (no tile can render blank)", () => {
    const byLang = new Map<string, number>();
    for (const s of allSimpleStrings()) byLang.set(s.lang, (byLang.get(s.lang) ?? 0) + 1);
    const counts = [...byLang.values()];
    expect(byLang.size).toBe(4);
    expect(new Set(counts).size).toBe(1);
  });
  it("Aaj ka sabak never leaks jargon", () => {
    const lessons = allLessons();
    expect(lessons.length).toBeGreaterThan(20);
    const hard = [/\bNRML\b/, /\bwebhook/i, /\bHMAC\b/, /execution mode/i, /\bdeploy/i];
    const bad = lessons.filter(({ text }) => hard.some((re) => re.test(text)));
    expect(bad.map((b) => `${b.lang}:${b.id}`)).toEqual([]);
  });
});

describe("C10B — no developer or roadmap text on customer pages", () => {
  const files = [...walk(join(process.cwd(), "src/app")), ...walk(join(process.cwd(), "src/components")), join(process.cwd(), "src/lib/algomitra-faqs.ts")];
  const forbidden = [/not built/i, /\bscheduled\b(?![^<]*schedule)/i, /\btonight\b/i, /\bsprint\b/i, /coming in a later/i, /\bPhase\s?\d/, /\bTODO\b/, /wire-?up/i];
  it("no page or component ships the forbidden phrases in rendered text", () => {
    const hits: string[] = [];
    for (const f of files) {
      const src = stripComments(readFileSync(f, "utf8"));
      for (const re of forbidden) {
        const m = src.match(re);
        if (m) hits.push(`${f.replace(process.cwd() + "/", "")}: ${m[0]}`);
      }
    }
    // The public roadmap section is deliberate product copy (no dates, no promises);
    // /admin/* is the founder's console, not a customer page.
    const allowed = hits.filter((h) => !h.includes("marketing/RoadmapSection") && !h.includes("(dashboard)/admin/"));
    expect(allowed, allowed.join("\n")).toEqual([]);
  });
});
