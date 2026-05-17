import { describe, it, expect } from "vitest";
import {
  EXPLAINERS,
  EXPLAINER_COUNT,
  getExplainer,
  listExplainers,
  type StrategyExplainer,
} from "@/lib/strategies/explainers";

const EXPECTED_COUNT = 45;

const assertShape = (slug: string, e: StrategyExplainer) => {
  expect(e.slug, `${slug}: slug`).toBe(slug);
  expect(e.what_it_does.length, `${slug}: what_it_does non-empty`).toBeGreaterThan(100);
  expect(e.what_it_does_hi.length, `${slug}: what_it_does_hi non-empty`).toBeGreaterThan(100);
  expect(e.best_market_conditions.length, `${slug}: best`).toBeGreaterThan(20);
  expect(e.worst_market_conditions.length, `${slug}: worst`).toBeGreaterThan(20);
  expect(Array.isArray(e.common_mistakes), `${slug}: mistakes array`).toBe(true);
  expect(e.common_mistakes.length, `${slug}: ≥3 mistakes`).toBeGreaterThanOrEqual(3);
  expect(e.realistic_returns.length, `${slug}: returns`).toBeGreaterThan(30);
  expect(e.example_trade.symbol, `${slug}: example symbol`).toBeTruthy();
  expect(e.example_trade.entry, `${slug}: example entry`).toBeTruthy();
  expect(e.example_trade.exit, `${slug}: example exit`).toBeTruthy();
  expect(e.example_trade.pnl, `${slug}: example pnl`).toBeTruthy();
  expect(Array.isArray(e.follow_up_strategies), `${slug}: follow-ups array`).toBe(true);
  expect(e.follow_up_strategies.length, `${slug}: ≥1 follow-up`).toBeGreaterThanOrEqual(1);
  expect(e.difficulty_score, `${slug}: difficulty 1-5`).toBeGreaterThanOrEqual(1);
  expect(e.difficulty_score, `${slug}: difficulty 1-5`).toBeLessThanOrEqual(5);
  expect(e.capital_efficiency_score, `${slug}: cap-eff 1-5`).toBeGreaterThanOrEqual(1);
  expect(e.capital_efficiency_score, `${slug}: cap-eff 1-5`).toBeLessThanOrEqual(5);
};

describe("strategy explainers registry", () => {
  it("registers the expected number of explainers", () => {
    expect(EXPLAINER_COUNT).toBe(EXPECTED_COUNT);
    expect(listExplainers()).toHaveLength(EXPECTED_COUNT);
  });

  it("every registered explainer has a well-formed shape", () => {
    for (const [slug, explainer] of Object.entries(EXPLAINERS)) {
      assertShape(slug, explainer);
    }
  });

  it("getExplainer returns null for unknown slugs", () => {
    expect(getExplainer("does-not-exist")).toBeNull();
    expect(getExplainer("")).toBeNull();
  });

  it("every follow-up slug references an existing explainer", () => {
    for (const [slug, explainer] of Object.entries(EXPLAINERS)) {
      for (const followUp of explainer.follow_up_strategies) {
        expect(
          EXPLAINERS[followUp],
          `${slug} references unknown follow-up: ${followUp}`,
        ).toBeDefined();
      }
    }
  });

  it("registry keys match each explainer.slug field", () => {
    for (const [key, explainer] of Object.entries(EXPLAINERS)) {
      expect(explainer.slug, `Registry key ${key} mismatched slug field`).toBe(key);
    }
  });
});
