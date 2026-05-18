/**
 * Marketing content draft registry. Lookup by slug; null if not found.
 * Content-only — no send/post infrastructure here yet.
 */
import type { MarketingTemplate, Platform } from "./_types";

import { LAUNCH_ANNOUNCEMENT } from "./telegram/launch-announcement";
import { FEATURE_HIGHLIGHT } from "./telegram/feature-highlight";
import { WEEKLY_PAPER_PNL_SHARE } from "./telegram/weekly-paper-pnl-share";
import { STRATEGY_OF_WEEK } from "./telegram/strategy-of-week";
import { BETA_INVITE } from "./telegram/beta-invite";
import { COMPLIANCE_UPDATE as TG_COMPLIANCE_UPDATE } from "./telegram/compliance-update";
import { MILESTONE_CELEBRATION } from "./telegram/milestone-celebration";
import { LIVE_TRADING_ANNOUNCEMENT as TG_LIVE_TRADING_ANNOUNCEMENT } from "./telegram/live-trading-announcement";

import { LAUNCH_THREAD } from "./twitter/launch-thread";
import { STRATEGY_BUILDER_DEMO } from "./twitter/strategy-builder-demo";
import { ALGOMITRA_INTRODUCTION } from "./twitter/algomitra-introduction";
import { GLASS_BOX_AI_EXPLAINER } from "./twitter/glass-box-ai-explainer";
import { PRICING_REVEAL } from "./twitter/pricing-reveal";
import { USER_SUCCESS_STORY_TEMPLATE } from "./twitter/user-success-story-template";

import { CUSTOMER_WELCOME } from "./whatsapp/customer-welcome";
import { STRATEGY_SUGGESTION } from "./whatsapp/strategy-suggestion";
import { TOKEN_ROTATION_REMINDER } from "./whatsapp/token-rotation-reminder";
import { SUPPORT_FOLLOWUP } from "./whatsapp/support-followup";
import { REFERRAL_MESSAGE } from "./whatsapp/referral-message";

import { FEATURE_CAROUSEL_1 } from "./instagram/feature-carousel-1";
import { PNL_STORY_TEMPLATE } from "./instagram/pnl-story-template";
import { EDUCATIONAL_REEL_SCRIPTS } from "./instagram/educational-reel-scripts";

export type { MarketingTemplate, Platform, Audience } from "./_types";

const MARKETING_MAP: Record<string, MarketingTemplate> = {
  "telegram-launch-announcement": LAUNCH_ANNOUNCEMENT,
  "telegram-feature-highlight": FEATURE_HIGHLIGHT,
  "telegram-weekly-paper-pnl-share": WEEKLY_PAPER_PNL_SHARE,
  "telegram-strategy-of-week": STRATEGY_OF_WEEK,
  "telegram-beta-invite": BETA_INVITE,
  "telegram-compliance-update": TG_COMPLIANCE_UPDATE,
  "telegram-milestone-celebration": MILESTONE_CELEBRATION,
  "telegram-live-trading-announcement": TG_LIVE_TRADING_ANNOUNCEMENT,

  "twitter-launch-thread": LAUNCH_THREAD,
  "twitter-strategy-builder-demo": STRATEGY_BUILDER_DEMO,
  "twitter-algomitra-introduction": ALGOMITRA_INTRODUCTION,
  "twitter-glass-box-ai-explainer": GLASS_BOX_AI_EXPLAINER,
  "twitter-pricing-reveal": PRICING_REVEAL,
  "twitter-user-success-story-template": USER_SUCCESS_STORY_TEMPLATE,

  "whatsapp-customer-welcome": CUSTOMER_WELCOME,
  "whatsapp-strategy-suggestion": STRATEGY_SUGGESTION,
  "whatsapp-token-rotation-reminder": TOKEN_ROTATION_REMINDER,
  "whatsapp-support-followup": SUPPORT_FOLLOWUP,
  "whatsapp-referral-message": REFERRAL_MESSAGE,

  "instagram-feature-carousel-1": FEATURE_CAROUSEL_1,
  "instagram-pnl-story-template": PNL_STORY_TEMPLATE,
  "instagram-educational-reel-scripts": EDUCATIONAL_REEL_SCRIPTS,
};

export const MARKETING: Readonly<Record<string, MarketingTemplate>> = MARKETING_MAP;
export const MARKETING_COUNT = Object.keys(MARKETING).length;

export function getMarketing(slug: string): MarketingTemplate | null {
  return MARKETING[slug] ?? null;
}

export function listMarketing(): MarketingTemplate[] {
  return Object.values(MARKETING);
}

export function listMarketingByPlatform(platform: Platform): MarketingTemplate[] {
  return Object.values(MARKETING).filter((t) => t.platform === platform);
}
