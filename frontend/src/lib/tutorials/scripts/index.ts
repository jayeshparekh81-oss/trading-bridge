/**
 * Tutorial video script registry. Lookup by topic; null if not found.
 * Each script has Hindi-only + English-only full versions ready
 * for recording. No video infrastructure plumbed.
 */
import type { TutorialScript } from "./_types";

import { SIGNUP_WALKTHROUGH } from "./signup-walkthrough";
import { DHAN_CONNECT } from "./dhan-connect";
import { FIRST_STRATEGY_TEMPLATE } from "./first-strategy-template";
import { UNDERSTANDING_PAPER_MODE } from "./understanding-paper-mode";
import { READING_CHART_INDICATORS } from "./reading-chart-indicators";
import { BACKTEST_INTERPRETATION } from "./backtest-interpretation";
import { RISK_MANAGEMENT_BASICS } from "./risk-management-basics";
import { ALGOMITRA_INTRO } from "./algomitra-intro";
import { COMPLIANCE_EXPLAINER } from "./compliance-explainer";
import { LIVE_TRADING_PREP } from "./live-trading-prep";

export type { TutorialScript, LanguageScript, ScriptSection } from "./_types";

const SCRIPTS_MAP: Record<string, TutorialScript> = {
  "signup-walkthrough": SIGNUP_WALKTHROUGH,
  "dhan-connect": DHAN_CONNECT,
  "first-strategy-template": FIRST_STRATEGY_TEMPLATE,
  "understanding-paper-mode": UNDERSTANDING_PAPER_MODE,
  "reading-chart-indicators": READING_CHART_INDICATORS,
  "backtest-interpretation": BACKTEST_INTERPRETATION,
  "risk-management-basics": RISK_MANAGEMENT_BASICS,
  "algomitra-intro": ALGOMITRA_INTRO,
  "compliance-explainer": COMPLIANCE_EXPLAINER,
  "live-trading-prep": LIVE_TRADING_PREP,
};

export const SCRIPTS: Readonly<Record<string, TutorialScript>> = SCRIPTS_MAP;
export const SCRIPT_COUNT = Object.keys(SCRIPTS).length;

export function getScript(topic: string): TutorialScript | null {
  return SCRIPTS[topic] ?? null;
}

export function listScripts(): TutorialScript[] {
  return Object.values(SCRIPTS);
}
