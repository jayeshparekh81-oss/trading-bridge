/**
 * GUARD (guided-path walk, 26 Sep 2026): an error a customer can read never says what failed INSIDE the
 * system — "is the backend running?", "internal error", "HTTP 500", "Backend returned …". It says what
 * happened, what it means and what to do (the never-stuck rule).
 *
 * Found by the walk: the live Brokers modal showed the scrubbed 5xx body "internal error"
 * (SensitiveDataFilterMiddleware), the API client fell back to "HTTP <status>", and the public showcase
 * said "is the backend running?". This scans every string literal and JSX text in src/ (comments stripped).
 */
import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { REQUEST_FAILED_HI, SCRUBBED_5XX_DETAIL, SERVER_TROUBLE_HI, NETWORK_TROUBLE_HI } from "@/shared/api/client";

const SRC = join(process.cwd(), "src");

function walk(dir: string, out: string[] = []): string[] {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.tsx?$/.test(n)) out.push(p);
  }
  return out;
}

/** Strip // and /* *\/ comments so a comment that DOCUMENTS the old wording does not trip the guard. */
function code(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`])\/\/.*$/gm, "$1");
}

const BANNED: RegExp[] = [
  /is the backend running/i,
  /Backend returned/,
  /`HTTP \$\{/,                         // "HTTP ${res.status}" shown as a message
  /["'`]internal error["'`]/,           // rendering the scrubbed body as copy
];

describe("customer-visible errors never speak engineer", () => {
  it("no banned phrase in any src string", () => {
    const hits: string[] = [];
    for (const f of walk(SRC)) {
      const c = code(readFileSync(f, "utf8"));
      for (const re of BANNED) {
        // the client may NAME the scrubbed body once, as the constant it detects
        if (f.endsWith("shared/api/client.ts") && re.source.includes("internal error")) continue;
        if (re.test(c)) hits.push(`${f.slice(SRC.length + 1)}: ${re}`);
      }
    }
    expect(hits).toEqual([]);
  });

  it("the client's replacement lines are plain words with a next step, and name no code", () => {
    expect(SCRUBBED_5XX_DETAIL).toBe("internal error");
    for (const line of [SERVER_TROUBLE_HI, NETWORK_TROUBLE_HI, REQUEST_FAILED_HI]) {
      expect(line).toMatch(/(dobara|try)/i);
      expect(line).not.toMatch(/\d{3}|backend|error|HTTP/i);
    }
  });
});
