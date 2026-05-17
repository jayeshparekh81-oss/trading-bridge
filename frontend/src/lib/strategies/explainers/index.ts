/**
 * Strategy explainer registry — single import surface for pages and
 * components that need the layman-language content for an active
 * equity strategy template.
 *
 * Looks up by slug. Returns `null` for unknown slugs so callers can
 * fall back gracefully (e.g. show only the `config_json` shape on
 * templates that haven't been explainer-authored yet).
 *
 * Adding a new explainer:
 *   1. Create `<slug>.ts` exporting a `const <SLUG>: StrategyExplainer`.
 *   2. Import + add to the EXPLAINERS map below.
 *   3. The test (`explainers-registry.test.ts`) auto-asserts shape.
 */

import type { StrategyExplainer } from "./_types";

export type { StrategyExplainer, ExampleTrade } from "./_types";

// Imports added as each explainer file lands. Empty initial state
// so the file compiles even when authored over many commits.
const EXPLAINERS_MAP: Record<string, StrategyExplainer> = {};

export const EXPLAINERS: Readonly<Record<string, StrategyExplainer>> =
  EXPLAINERS_MAP;

export const EXPLAINER_COUNT = Object.keys(EXPLAINERS).length;

export function getExplainer(slug: string): StrategyExplainer | null {
  return EXPLAINERS[slug] ?? null;
}

export function listExplainers(): StrategyExplainer[] {
  return Object.values(EXPLAINERS);
}
