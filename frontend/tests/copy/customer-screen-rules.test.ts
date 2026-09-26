/**
 * THE FOUNDER'S TEN-POINT RULE for customer screens (26 Sep 2026, RULES #50),
 * the parts a machine can check. The rest (the 5-second test, one decision per
 * screen) are judged by a person and written in kb/customer/LIVE_WALK_PROOF.md.
 *
 *  3. PLAIN HINGLISH, no jargon            → jargon lint over every customer file
 *  7. THUMB-FRIENDLY ON PHONE              → the tap + text tokens exist, the shared
 *                                             Button honours them on phones, no text
 *                                             below 12px on any customer screen and
 *                                             below 14px on the first-timer path,
 *                                             no fixed width wider than a 375px phone
 * 10. NOTHING THAT LOOKS LIKE DATA BUT ISN'T → no bare "—" / "?" standing in for a
 *                                             value we do not have
 *  8. ERRORS IN HUMAN WORDS                → no raw engineer error words on screen
 *  2. ONE THING PER SCREEN (guided path)   → rendered separately in guided-one-primary.test.tsx
 *
 * Source-level checks, deliberately: the box has no browser (SETTLED 20 Sep). What the
 * pixels look like at 375×812 is the Mac's walk (kb/mac_outbox/live_walk_375/).
 */

import { describe, expect, it } from "vitest";
import { appendFileSync, existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { ALLOW, CUSTOMER_SCREENS, FIRST_TIMER_SCREENS, JARGON } from "./customer-screens";

const ROOT = process.cwd();
/** CUSTOMER_RULES_REPORT=<file>: every hit is also written out in full (vitest truncates long arrays). */
function report(rule: string, hits: string[]): string[] {
  const out = process.env.CUSTOMER_RULES_REPORT;
  if (out) appendFileSync(out, hits.map((h) => `${rule}\t${h}\n`).join("") + `${rule}\tCOUNT ${hits.length}\n`);
  return hits;
}
const read = (rel: string) => readFileSync(join(ROOT, rel), "utf8");

/** Drop comments, keep strings (a `//` inside a URL string is not a comment). */
export function stripComments(src: string): string {
  let out = src.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "));
  out = out.replace(/\{\s*\/\*[\s\S]*?\*\/\s*\}/g, "");
  out = out.replace(/(^|[^:"'`\w])\/\/[^\n]*/g, "$1");
  return out;
}

/** A string that is code, not words a customer reads. */
function looksLikeCode(s: string): boolean {
  const t = s.trim();
  if (!t) return true;
  if (!/\s/.test(t)) return true; // single token: a key, a path, an id, a class
  if (/^(\/|https?:|@\/|\.\/|\.\.\/)/.test(t)) return true;
  if (/(^|\s)(flex|grid|inline-flex|text-|bg-|px-|py-|p-\d|m[tbxy]?-\d|rounded|border|items-|justify-|gap-|w-|h-\d|min-h|max-w|font-|hover:|space-y|sr-only|shrink|truncate|tracking-|leading-|ring-|opacity-|transition|overflow|absolute|relative|sticky|z-\d)/.test(t)) return true;
  if (/^[\w.$]+\(/.test(t) || /=>|===|!==|&&|\|\|/.test(t)) return true;
  return false;
}

/** Every piece of text a customer could read, with its line number. */
export function customerStrings(src: string): { line: number; text: string }[] {
  const clean = stripComments(src);
  const out: { line: number; text: string }[] = [];
  const lineOf = (i: number) => clean.slice(0, i).split("\n").length;
  const lit = /"((?:[^"\\\n]|\\.)*)"|'((?:[^'\\\n]|\\.)*)'|`((?:[^`\\]|\\.)*)`/g;
  let m: RegExpExecArray | null;
  while ((m = lit.exec(clean))) {
    let s = m[1] ?? m[2] ?? m[3] ?? "";
    s = s.replace(/\$\{[^}]*\}/g, " ");
    if (!looksLikeCode(s)) out.push({ line: lineOf(m.index), text: s });
  }
  const jsx = />([^<>{}]*[A-Za-z][^<>{}]*)</g;
  while ((m = jsx.exec(clean))) {
    const s = m[1].replace(/\s+/g, " ").trim();
    if (s && !/[;=]/.test(s)) out.push({ line: lineOf(m.index), text: s });
  }
  return out;
}

/** Remove the EXPLAINED forms: "word (meaning)", "(word)", and a literal 'Label' quoted from another site. */
export function withoutExplained(text: string): string {
  return text
    .replace(/(\S+\s*)?\([^()]*\)/g, " ")
    .replace(/[‘'][^‘’']{2,80}[’']/g, " ")
    .replace(/“[^”]{2,80}”/g, " ");
}

export function jargonIn(file: string, src: string): string[] {
  const hits: string[] = [];
  for (const { line, text } of customerStrings(src)) {
    const plain = withoutExplained(text);
    for (const j of JARGON) {
      if (ALLOW.some((a) => a.file === file && a.word === j.word)) continue;
      if (j.re.test(plain)) hits.push(`${file}:${line} [${j.word}] ${text.slice(0, 110)}`);
    }
  }
  return hits;
}

/** A bare dash or "?" shown where a value should be — reads like data, is not. */
const FAKE_VALUE = [
  /\?\?\s*["'`]—["'`]/, /\|\|\s*["'`]—["'`]/, /:\s*["'`]—["'`]\s*[}\n)]/, /\?\?\s*["'`]\?["'`]/,
  /\|\|\s*["'`]\?["'`]/, /placeholder=["']—["']/, />\s*—\s*</, /\{\s*["'`]—["'`]\s*\}/, /["'`]—["'`]\s*$/m,
];
export function fakeValuesIn(file: string, src: string): string[] {
  const clean = stripComments(src);
  const hits: string[] = [];
  clean.split("\n").forEach((l, i) => {
    for (const re of FAKE_VALUE) if (re.test(l)) { hits.push(`${file}:${i + 1} ${l.trim().slice(0, 110)}`); break; }
  });
  return hits;
}

const ENGINEER_ERROR = /\b(Could not load|Failed to|Retry|Something went wrong|Unexpected error|Error:|Try again)\b/;

const allFiles = [...new Set(Object.values(CUSTOMER_SCREENS).flat())];
const firstTimerFiles = [...new Set(FIRST_TIMER_SCREENS.flatMap((s) => CUSTOMER_SCREENS[s] ?? []))];

describe("the screen list itself", () => {
  it("names only files that exist", () => {
    const missing = report("files", allFiles.filter((f) => !existsSync(join(ROOT, f))));
    expect(missing).toEqual([]);
  });
});

describe("point 3 — plain Hinglish, no jargon on customer screens", () => {
  it("no unexplained jargon word on any customer screen", () => {
    const hits = report("jargon", allFiles.filter((f) => existsSync(join(ROOT, f))).flatMap((f) => jargonIn(f, read(f))));
    expect(hits).toEqual([]);
  });
  it("the lint catches a bare jargon word and passes its explained form (falsification twin)", () => {
    expect(jargonIn("x.tsx", `<p>Execution mode chuno aur lots daalo</p>`).length).toBe(2);
    expect(jargonIn("x.tsx", `<p>Kitna bada sauda: 400 shares (2 lot)</p>`)).toEqual([]);
    expect(jargonIn("x.tsx", `const s = "Dhan ki chabi (access token) yahan daalo";`)).toEqual([]);
    expect(jargonIn("x.tsx", `const s = "Dhan par 'Access DhanHQ Trading APIs' dabao";`)).toEqual([]);
    expect(jargonIn("x.tsx", `const s = "HMAC secret daalo";`).length).toBe(1);
  });
});

describe("point 8 — errors in human words", () => {
  it("no English engineer error line on a customer screen", () => {
    const hits = allFiles.filter((f) => existsSync(join(ROOT, f))).flatMap((f) =>
      customerStrings(read(f))
        .filter(({ text }) => ENGINEER_ERROR.test(text))
        .map(({ line, text }) => `${f}:${line} ${text.slice(0, 100)}`),
    );
    expect(report("errors", hits)).toEqual([]);
  });
});

describe("point 10 — NOT MEASURED says NOT MEASURED, never a bare dash or question mark", () => {
  it("no customer screen renders '—' or '?' in place of a value", () => {
    const hits = report("fake-value", allFiles.filter((f) => existsSync(join(ROOT, f))).flatMap((f) => fakeValuesIn(f, read(f))));
    expect(hits).toEqual([]);
  });
  it("the check catches the shapes it is for (falsification twin)", () => {
    expect(fakeValuesIn("x.tsx", `{p.price ?? "—"}`).length).toBe(1);
    expect(fakeValuesIn("x.tsx", `reason: \${r ?? "?"}`).length).toBe(1);
    expect(fakeValuesIn("x.tsx", `<Input placeholder="—" />`).length).toBe(1);
    expect(fakeValuesIn("x.tsx", `<td>—</td>`).length).toBe(1);
    expect(fakeValuesIn("x.tsx", `{p.price ?? NOT_MEASURED}`)).toEqual([]);
    expect(fakeValuesIn("x.tsx", `const s = "Aaj — kal";`)).toEqual([]);
  });
});

describe("point 7 — thumb-friendly: tokens, the shared Button, no tiny text", () => {
  const css = read("src/app/globals.css");
  const rem = (name: string) => {
    const m = new RegExp(`--${name}:\\s*([0-9.]+)rem`).exec(css);
    return m ? Number(m[1]) * 16 : 0;
  };
  it("design tokens define a 44px tap target and a 14px readable text size", () => {
    expect(rem("spacing-tap")).toBeGreaterThanOrEqual(44);
    expect(rem("text-readable")).toBeGreaterThanOrEqual(14);
  });
  it("every size of the shared Button reaches the tap target on a touch screen", () => {
    const btn = read("src/shared/ui/button.tsx");
    const sizes = /size:\s*\{([\s\S]*?)\n\s*\},/.exec(btn)?.[1] ?? "";
    const entries = [...sizes.matchAll(/^\s*"?([\w-]+)"?:\s*\n?\s*"([^"]*)"/gm)];
    expect(entries.length).toBeGreaterThanOrEqual(8);
    for (const [, name, cls] of entries) {
      expect(cls, `Button size "${name}"`).toMatch(/pointer-coarse:min-h-tap/);
      if (name.startsWith("icon")) expect(cls, `Button size "${name}"`).toMatch(/pointer-coarse:min-w-tap/);
    }
  });
  it("no text below 12px on any customer screen", () => {
    const hits = allFiles.filter((f) => existsSync(join(ROOT, f))).flatMap((f) =>
      stripComments(read(f)).split("\n").flatMap((l, i) =>
        /(?<![\w-])text-(8|9|10|11)(?![\w-])|text-\[(\d|1[01])px\]/.test(l) ? [`${f}:${i + 1}`] : [],
      ),
    );
    expect(report("text<12px", hits)).toEqual([]);
  });
  it("no text below 14px on the first-timer path", () => {
    const hits = firstTimerFiles.filter((f) => existsSync(join(ROOT, f))).flatMap((f) =>
      stripComments(read(f)).split("\n").flatMap((l, i) => (/(?<![\w-])text-xs(?![\w-])/.test(l) ? [`${f}:${i + 1}`] : [])),
    );
    expect(report("text<14px first-timer", hits)).toEqual([]);
  });
  it("no fixed width wider than a 375px phone", () => {
    const hits = allFiles.filter((f) => existsSync(join(ROOT, f))).flatMap((f) =>
      stripComments(read(f)).split("\n").flatMap((l, i) => {
        const out: string[] = [];
        for (const m of l.matchAll(/(?<![\w-])(?:w|min-w)-\[(\d+)px\]/g)) if (Number(m[1]) > 375) out.push(`${f}:${i + 1} ${m[0]}`);
        return out;
      }),
    );
    expect(report("width>375", hits)).toEqual([]);
  });
});
