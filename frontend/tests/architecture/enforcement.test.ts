/**
 * ADR 0001 §7 — "A rule that has never been proven to fail is not enforcement."
 *
 * These tests lint deliberately-bad code through the PROJECT'S REAL ESLint
 * config and fail if ESLint stays quiet. That matters more than it sounds:
 * eslint-plugin-boundaries silently passes everything if its element patterns
 * stop matching or the `@/` alias stops resolving, so a green build would
 * otherwise be indistinguishable from a disabled rule.
 *
 * The bad code is linted via `lintText` with a pretend file path, so no
 * broken fixture files exist on disk to confuse the build or the next reader.
 */
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { ESLint } from "eslint";
import fs from "node:fs";
import path from "node:path";

const cwd = process.cwd();
const eslint = new ESLint({ cwd });

/**
 * Cross-slice isolation can only be proven against a target that RESOLVES —
 * boundaries cannot classify an import it fails to resolve, and stays silent.
 * So the test writes two throwaway slices for the duration of the run and
 * removes them again, rather than asserting against whatever slices happen to
 * exist today.
 */
const PROBE_A = path.join(cwd, "src/entities/__probe_a__");
const PROBE_B = path.join(cwd, "src/entities/__probe_b__");

beforeAll(() => {
  fs.mkdirSync(PROBE_B, { recursive: true });
  fs.writeFileSync(path.join(PROBE_B, "thing.ts"), "export const other = 1;\n");
  fs.mkdirSync(PROBE_A, { recursive: true });
});

afterAll(() => {
  fs.rmSync(PROBE_A, { recursive: true, force: true });
  fs.rmSync(PROBE_B, { recursive: true, force: true });
});

/** Lint a string as if it lived at `rel`, and return the rule IDs that fired. */
async function rulesFiredFor(rel: string, code: string): Promise<string[]> {
  const [result] = await eslint.lintText(code, {
    filePath: path.join(cwd, rel),
    warnIgnored: false,
  });
  return (result?.messages ?? []).map((m) => m.ruleId ?? "");
}

const LAYERS = "boundaries/element-types";
const TOKENS = "no-restricted-syntax";

describe("ADR 0001 §1 — the layer rule actually fires", () => {
  it("BLOCKS an upward import (entities -> app)", async () => {
    const fired = await rulesFiredFor(
      "src/entities/probe/upward.ts",
      `import { metadata } from "@/app/layout";\nexport const x = metadata;\n`,
    );
    expect(fired).toContain(LAYERS);
  }, 30_000);

  it("BLOCKS a cross-slice import (entities/a -> entities/b)", async () => {
    const fired = await rulesFiredFor(
      "src/entities/__probe_a__/cross.ts",
      `import { other } from "@/entities/__probe_b__/thing";\nexport const x = other;\n`,
    );
    expect(fired).toContain(LAYERS);
  }, 30_000);

  it("BLOCKS a widget reaching into the unmigrated legacy tree", async () => {
    // Route files may still reach into legacy while the migration runs; a
    // migrated slice may not. That is what stops the tangle re-forming.
    const fired = await rulesFiredFor(
      "src/widgets/probe/legacy.ts",
      `import { cn } from "@/lib/utils";\nexport const x = cn;\n`,
    );
    expect(fired).toContain(LAYERS);
  }, 30_000);

  it("ALLOWS a legal downward import (entities -> shared)", async () => {
    const fired = await rulesFiredFor(
      "src/entities/probe/legal.ts",
      `import { cn } from "@/shared/lib/utils";\nexport const x = cn;\n`,
    );
    expect(fired).not.toContain(LAYERS);
  }, 30_000);

  it("ALLOWS a route file reaching into legacy (the migration escape hatch)", async () => {
    const fired = await rulesFiredFor(
      "src/app/(dashboard)/probe/page.tsx",
      `import { cn } from "@/lib/utils";\nexport default function P() { return cn("x"); }\n`,
    );
    expect(fired).not.toContain(LAYERS);
  }, 30_000);
});

describe("ADR 0001 §3 — the design-token rule actually fires", () => {
  const at = (code: string) => rulesFiredFor("src/components/probe/bad.tsx", code);

  it("BLOCKS a hardcoded hex colour", async () => {
    expect(await at(`export const c = "bg-[#0F1629]";\n`)).toContain(TOKENS);
  }, 30_000);

  it("BLOCKS a raw rgb()/rgba() colour", async () => {
    expect(await at(`export const c = { color: "rgba(0,255,136,0.4)" };\n`)).toContain(TOKENS);
  }, 30_000);

  it("BLOCKS a hex colour hidden in a template literal", async () => {
    expect(await at("export const c = `border-[#FFD700]`;\n")).toContain(TOKENS);
  }, 30_000);

  it("BLOCKS a raw font size", async () => {
    expect(await at(`export const c = "text-[10px]";\n`)).toContain(TOKENS);
  }, 30_000);

  it("BLOCKS raw pixel spacing", async () => {
    expect(await at(`export const c = "p-[3px]";\n`)).toContain(TOKENS);
  }, 30_000);

  it("BLOCKS a raw pixel value on a token-governed property", async () => {
    expect(await at(`export const c = "rounded-[2px]";\n`)).toContain(TOKENS);
  }, 30_000);

  // The negatives matter as much: a rule that flags everything would be
  // switched off within a week.
  it("ALLOWS scale utilities and token-backed classes", async () => {
    expect(await at(`export const c = "p-4 h-16 rounded-lg gap-3 text-sm bg-profit/10 text-10";\n`)).not.toContain(TOKENS);
  }, 30_000);

  it("ALLOWS an arbitrary value that already references a token", async () => {
    expect(await at(`export const c = "rounded-[min(var(--radius-md),12px)]";\n`)).not.toContain(TOKENS);
  }, 30_000);

  it("ALLOWS one-off layout constraints (ADR 0001 §3: not design tokens)", async () => {
    expect(await at(`export const c = "h-[200px] max-w-[320px] grid-cols-[260px,1fr] left-[256px]";\n`)).not.toContain(TOKENS);
  }, 30_000);
});
